"""
One-time import of the historical NOC incident log into the platform database.

Run from backend/ with the virtualenv active:
    python -m scripts.import_incident_history /path/to/Incident_Management_Workbook_IncidentRawData_.csv
"""
import re
import sys
from datetime import datetime

import pandas as pd
from dateutil import parser as dateparser

from app.core.db import SessionLocal
from app.models.incidents import Incident, TicketSequence, normalize_incident_type, VALID_INCIDENT_TYPES

PREFIX_TO_CATEGORY = {
    "OF": "FIBER",
    "PW": "POWER",
    "TN": "TECHNICAL",
    "MA": "MAINTENANCE",
    "OT": "OTHER",
    "TM": "OTHER",
}

RAW_COLUMNS = [
    "Incident Type", "TT NO.", "Short Description", "Category", "Severity", "Notes",
    "Incident Date & Time", "Resolution Date & Time", "Reason For Delay (RFD)",
    "Reason For Outage (RFO) - Root Cause", "Reason For Outage (RFO) - Root Cause Detail",
    "Impact", "Planned/Unplanned", "Network Route", "Network Node/ Facility",
    "Resolution team ", "Resolution Method", "Responsible person ", "Status", "Opened by", "Closed by",
]


def clean_planned_flag(value):
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    if v == "planned":
        return True
    if v == "unplanned":
        return False
    return None 


def clean_status(value):
    # Lowercase to match the actual DB constraint (db/init-scripts/03_incidents_tickets.sql):
    # open, investigating, pending, resolved, closed, aborted.
    if not isinstance(value, str) or not value.strip():
        return "open"
    v = value.strip().lower()
    if "closed" in v:
        return "closed"
    return "open"


def parse_datetime(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return dateparser.parse(value, dayfirst=False)
    except (ValueError, OverflowError):
        return None


def safe_str(value):
    if pd.isna(value):
        return None
    v = str(value).strip()
    return v if v else None


def run_import(csv_path: str):
    df = pd.read_csv(csv_path, encoding="latin1")
    df = df[[c for c in RAW_COLUMNS if c in df.columns]]

    # Real incident rows all have a TT NO. — this drops the ~1,289 blank/report rows.
    df = df.dropna(subset=["TT NO."])

    db = SessionLocal()
    max_sequence = {}  # category_code -> highest sequence number seen
    inserted, skipped = 0, 0

    try:
        for _, row in df.iterrows():
            tt_number = safe_str(row["TT NO."])
            match = re.match(r"^([A-Z]+)_IM_(\d{8})_(\d+)$", tt_number or "")
            if not match:
                skipped += 1
                continue

            prefix, _, seq_str = match.groups()
            category = PREFIX_TO_CATEGORY.get(prefix, "OTHER")
            code = prefix if prefix in ("OF", "PW", "TN", "MA", "OT") else "OT"
            seq_num = int(seq_str)
            max_sequence[code] = max(max_sequence.get(code, 0), seq_num)

            # Get the raw string from the row
            raw_incident_type = safe_str(row.get("Incident Type"))

            # incident_type and ticket_category are different concepts (see
            # the model's own docstring): incident_type is WHAT happened,
            # ticket_category is HOW the TT number was generated. Only
            # normalize spelling variants here (e.g. "Power" -> "Power
            # Issue") — never fold an incident_type into a category code.
            normalized_incident_type = normalize_incident_type(raw_incident_type)
            row_notes = safe_str(row.get("Notes"))

            if normalized_incident_type in VALID_INCIDENT_TYPES:
                cleaned_incident_type = normalized_incident_type
            elif raw_incident_type:
                # Genuinely unrecognized value — don't guess and don't
                # silently reword it. Falls back to "Other" but keeps the
                # original text visible in notes so nothing is lost.
                cleaned_incident_type = "Other"
                tag = f"[Original incident type: {raw_incident_type}]"
                row_notes = f"{row_notes} {tag}".strip() if row_notes else tag
            else:
                cleaned_incident_type = "Other"

            incident = Incident(
                tt_number=tt_number,
                ticket_category=category,
                incident_type=cleaned_incident_type,
                short_description=safe_str(row.get("Short Description")),
                category=safe_str(row.get("Category")),
                severity=safe_str(row.get("Severity")),
                notes=row_notes,
                reported_at=parse_datetime(row.get("Incident Date & Time")) or datetime.utcnow(),
                resolved_at=parse_datetime(row.get("Resolution Date & Time")),
                reason_for_delay=safe_str(row.get("Reason For Delay (RFD)")),
                rfo_root_cause=safe_str(row.get("Reason For Outage (RFO) - Root Cause")),
                rfo_root_cause_detail=safe_str(row.get("Reason For Outage (RFO) - Root Cause Detail")),
                impact=safe_str(row.get("Impact")),
                is_planned=clean_planned_flag(row.get("Planned/Unplanned")),
                network_route=safe_str(row.get("Network Route")),
                network_node=safe_str(row.get("Network Node/ Facility")),
                resolution_team=safe_str(row.get("Resolution team ")),
                resolution_method=safe_str(row.get("Resolution Method")),
                responsible_person=safe_str(row.get("Responsible person ")),
                status=clean_status(row.get("Status")),
                opened_by=safe_str(row.get("Opened by")),
                closed_by=safe_str(row.get("Closed by")),
            )
            db.add(incident)
            inserted += 1

        # Seed sequence counters so the next auto-generated ticket per
        # category continues from the highest historical number.
        for code, seq in max_sequence.items():
            existing = db.get(TicketSequence, code)
            if existing:
                existing.last_sequence = max(existing.last_sequence, seq)
            else:
                db.add(TicketSequence(category_code=code, last_sequence=seq))

        db.commit()
        print(f"Imported {inserted} incidents. Skipped {skipped} rows with unrecognized TT NO. format.")
        print(f"Seeded sequence counters: {max_sequence}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/import_incident_history.py <path_to_csv>")
        sys.exit(1)
    # Extracts the string element directly to bypass pandas list parsing error
    run_import(sys.argv[1])