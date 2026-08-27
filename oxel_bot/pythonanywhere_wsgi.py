# ============================================================
# PythonAnywhere WSGI Configuration File
# ============================================================
#
# INSTRUCTIONS:
# 1. Log into PythonAnywhere → Web tab → your web app
# 2. Click "WSGI configuration file" link
# 3. REPLACE the entire content of that file with this content
# 4. Change YOURUSERNAME to your actual PythonAnywhere username
# 5. Click Save, then Reload your web app
# ============================================================

import sys
import os

# ── 1. Add your project folder to the Python path ─────────────────────────────
#   Replace 'YOURUSERNAME' with your actual PythonAnywhere username
path = '/home/YOURUSERNAME/oxel_bot'
if path not in sys.path:
    sys.path.insert(0, path)

# ── 2. Change working directory so SQLite path resolves correctly ──────────────
os.chdir(path)

# ── 3. Load environment variables from your .env file ─────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(path, '.env'))

# ── 4. Import the Flask application (WSGI entry point) ────────────────────────
from webhook_bot import application
