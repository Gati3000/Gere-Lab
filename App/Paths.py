# Miejsce na sciezki
#  linki do updatuw progreamiw tzrecich

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # Gere-Lab/
APP = ROOT / "App"
BIN = APP / "Bin"
MAIN = ROOT / "Main.py"
MAINTENANCE = APP / "Maintenance"
WHATSAPP = APP / "WhatsApp"
WEB_UI = APP / "Web-Ui"
LANGUAGE = WEB_UI / "Language"
WEB_UI_UI = WEB_UI / "Ui"
WEB_UI_BIN = WEB_UI / "Bin"
USER = ROOT / "User"
WEB_CONFIG = USER / "Web-Config.yml"
INDEXES = USER / "Indexes.yml"
MANIFEST = APP / "Manifest.py"
UPDATE = APP / "Update.py"

# Gere-Drive (drugie repo, obok Gere-Lab)
DRIVE = ROOT.parent / "Gere-Drive"
if not (DRIVE / ".git").is_dir():   # Gere-Drive niepobrane, lokalny zapas w Gere-Lab/Database
    DRIVE = ROOT / "Database"
DRIVE_MESSAGES = DRIVE / "Messeges"
DRIVE_PHOTOS = DRIVE_MESSAGES / "Photos"
DRIVE_CLIENTS = DRIVE / "Clients"
DRIVE_PARTS = DRIVE / "Parts"
DRIVE_INVOICES = DRIVE / "Invoices"
DRIVE_INVOICES_REVIEW = DRIVE_INVOICES / "To-Review"
DRIVE_INVOICES_ACCEPTED = DRIVE_INVOICES / "Accepted"
DRIVE_INVOICES_REJECTED = DRIVE_INVOICES / "Rejected"
WHATSAPP_BUSINESS = WHATSAPP / "WhatsApp-Business.py"
INQUIRIES = APP / "Bin" / "Inquiries.py"
INVOICER = APP / "Bin" / "Invoicer.py"
