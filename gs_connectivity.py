# gs_connectivity.py
import os
import gspread
from google.oauth2.service_account import Credentials

# Authentication
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_FILE = "gs-credentials.json"

# Your Google Sheet ID
SHEET_ID = "130L79Lz3nRcnb3chI-KR7VX-tTzbHrUAaNg_6EZWSsQ"

HEADER = [
    "Professor Name",
    "Certificate Issue Date",
    "Certificate Number",
    "Course/Exam/Purpose",
    "Grade/Marks",
    "Institution/Issuing Authority",
    "Registration/Roll No",
    "Address",
    "Other Details"
]

_client = None
_sheet = None


def init_sheet():
    """Initialize and return the primary sheet (sheet1)."""
    global _client, _sheet
    if _sheet is not None:
        return _sheet

    if not os.path.exists(SERVICE_FILE):
        raise FileNotFoundError(f"Service account file not found: {SERVICE_FILE}")

    creds = Credentials.from_service_account_file(SERVICE_FILE, scopes=SCOPES)
    _client = gspread.authorize(creds)
    workbook = _client.open_by_key(SHEET_ID)
    _sheet = workbook.sheet1

    # Ensure header exists
    existing = _sheet.get_all_values()
    if len(existing) == 0:
        _sheet.update("A1:I1", [HEADER], value_input_option="USER_ENTERED")
        try:
            _sheet.format("A1:I1", {"textFormat": {"bold": True}})
        except Exception:
            pass

    return _sheet


def append_row(row):
    """
    Append a single row (list of values) to the sheet.
    Pads/truncates to header length.
    """
    sheet = init_sheet()
    ncols = len(HEADER)
    row = list(row)[:ncols] + [""] * max(0, ncols - len(row))
    sheet.append_row(row, value_input_option="USER_ENTERED")


def append_rows(rows):
    """Append multiple rows (list of lists)."""
    for r in rows:
        append_row(r)