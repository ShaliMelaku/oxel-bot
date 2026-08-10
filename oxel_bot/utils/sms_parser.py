import re
import logging
from database import SessionLocal, Payment, Order

logger = logging.getLogger(__name__)


def parse_sms_payment_details(raw_input: str, payment_method: str = "telebirr") -> dict:
    """
    Extracts structured payment information from Telebirr / CBE SMS text or transaction codes.
    Checks anti-duplication against database to prevent reuse of transaction references.
    """
    clean_text = raw_input.strip()
    result = {
        'valid': False,
        'transaction_ref': None,
        'recipient': None,
        'amount': None,
        'date_time': None,
        'receipt_url': None,
        'error': None
    }

    method = (payment_method or 'telebirr').lower()

    if 'telebirr' in method:
        # Extract transaction code
        # Pattern 1: "Your transaction number is DE84OYCUWM."
        # Pattern 2: "https://transactioninfo.ethiotelecom.et/receipt/DE84OYCUWM"
        m_ref = re.search(r'transaction\s+number\s+is\s+([A-Za-z0-9]+)', clean_text, re.IGNORECASE)
        m_url = re.search(r'(https?://transactioninfo\.ethiotelecom\.et/receipt/([A-Za-z0-9]+))', clean_text, re.IGNORECASE)

        if m_ref:
            result['transaction_ref'] = m_ref.group(1).upper()
        elif m_url:
            result['receipt_url'] = m_url.group(1)
            result['transaction_ref'] = m_url.group(2).upper()
        else:
            m_code = re.search(r'\b([A-Za-z0-9]{6,20})\b', clean_text)
            if m_code and len(clean_text) < 30:
                result['transaction_ref'] = m_code.group(1).upper()

        if m_url and not result.get('receipt_url'):
            result['receipt_url'] = m_url.group(1)

        # Extract transferred amount
        m_amt = re.search(r'transferred\s+ETB\s+([0-9\.,]+)', clean_text, re.IGNORECASE)
        if m_amt:
            try:
                result['amount'] = float(m_amt.group(1).replace(',', ''))
            except ValueError:
                pass

        # Extract recipient
        m_rec = re.search(r'to\s+([A-Za-z0-9\s\*]+(?:\([0-9\*\+]+\))?)\s+on', clean_text, re.IGNORECASE)
        if m_rec:
            result['recipient'] = m_rec.group(1).strip()

        # Extract date/time
        m_dt = re.search(r'on\s+([0-9/\-\s:]+)\.', clean_text)
        if m_dt:
            result['date_time'] = m_dt.group(1).strip()

    elif 'cbe' in method:
        # Extract CBE transaction code / link
        m_url = re.search(r'(https?://Mbreciept\.cbe\.com\.et/([A-Za-z0-9\-]+))', clean_text, re.IGNORECASE)
        m_ft = re.search(r'\b(FT[A-Za-z0-9\-]+)\b', clean_text, re.IGNORECASE)

        if m_url:
            result['receipt_url'] = m_url.group(1)
            result['transaction_ref'] = m_url.group(2).upper()
        elif m_ft:
            result['transaction_ref'] = m_ft.group(1).upper()
        else:
            if len(clean_text) < 40 and re.match(r'^[A-Za-z0-9\-]{6,35}$', clean_text):
                result['transaction_ref'] = clean_text.upper()

        # Extract received amount
        m_amt = re.search(r'(?:received|transferred)\s+ETB\s+([0-9\.,]+)', clean_text, re.IGNORECASE)
        if m_amt:
            try:
                result['amount'] = float(m_amt.group(1).replace(',', ''))
            except ValueError:
                pass

        # Extract recipient account
        m_rec = re.search(r'to\s+your\s+account\s+([0-9\*]+)', clean_text, re.IGNORECASE)
        if m_rec:
            result['recipient'] = f"Account {m_rec.group(1)}"

    else:
        result['transaction_ref'] = clean_text[:50].upper()

    if not result['transaction_ref']:
        result['error'] = (
            "⚠️ Could not extract transaction reference code from your text.\n\n"
            "Please paste your complete SMS message or enter your reference code."
        )
        return result

    # Check database for transaction reference repetition / duplication
    db = SessionLocal()
    try:
        ref_check = result['transaction_ref']
        existing_payment = db.query(Payment).filter(Payment.transaction_reference == ref_check).first()
        existing_order = db.query(Order).filter(Order.payment_reference == ref_check).first()

        if existing_payment or existing_order:
            result['error'] = (
                f"🚫 <b>DUPLICATE TRANSACTION REJECTED</b>\n\n"
                f"Transaction reference <code>{ref_check}</code> has ALREADY been used for a previous order!\n\n"
                f"Each payment transaction number can only be submitted once."
            )
            return result
    finally:
        db.close()

    result['valid'] = True
    return result
