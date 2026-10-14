"""Deterministic parsing of copied FTTH requests; no external service required."""
import re

LABELS = {
    "FN NUMBER": "fn_number", "CUSTOMER NAME": "customer_name",
    "SERVICE ADDRESS": "service_address", "SERVICE PACKAGE": "bandwidth",
    "CONTACT PHONE": "phone_number", "EMAIL": "email",
    "WORK ORDER ID": "work_order_id",
    "CUSTOMER INFORMATION": None, "SFC ASSIGNED": None,
    "VIEW ACTIVITIES": None, "REASSIGN INSTALLER": None,
}
LABEL_PATTERN = re.compile(
    r"^(" + "|".join(re.escape(label) for label in LABELS) + r")(?:\s*:\s*(.*))?$", re.I
)
STATUSES = {"OPEN", "PENDING", "CLOSED", "COMPLETED", "CANCELLED"}


def parse_ftth_request(raw_text):
    if not raw_text or len(raw_text) > 20000:
        raise ValueError("Paste a request of up to 20,000 characters.")
    fields, current, parts, source_status = {}, None, [], None

    def flush():
        if current and parts:
            value = " ".join(parts).strip()
            if current in {"fn_number", "work_order_id"}:
                value = value.upper()
            previous = fields.get(current)
            if previous and previous != value:
                raise ValueError(f"Conflicting values for {current.replace('_', ' ')}. Paste one request at a time.")
            fields[current] = value

    for raw_line in raw_text.replace("\r", "").split("\n"):
        line = " ".join(raw_line.split()).strip()
        if not line:
            continue
        match = LABEL_PATTERN.fullmatch(line)
        if match:
            flush()
            current, parts = LABELS[match[1].upper()], []
            if current and match[2]:
                parts.append(match[2])
        elif line.upper() in STATUSES and current in {None, "fn_number"}:
            flush()
            current, parts = None, []
            if source_status and source_status != line.upper():
                raise ValueError("Multiple source statuses found. Paste one request at a time.")
            source_status = line.upper()
        elif current:
            parts.append(line)
    flush()

    required = ("fn_number", "customer_name", "service_address", "bandwidth", "work_order_id")
    missing = [field.replace("_", " ") for field in required if not fields.get(field)]
    if missing:
        raise ValueError("Missing fields: " + ", ".join(missing) + ".")
    if not re.fullmatch(r"FN\d+", fields["fn_number"]):
        raise ValueError("FN number must contain FN followed by digits.")
    if not re.fullmatch(r"[A-Z0-9-]+", fields["work_order_id"]):
        raise ValueError("Work order ID contains unexpected characters.")
    bandwidth = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(Mbps|Gbps)", fields["bandwidth"], re.I)
    if not bandwidth or float(bandwidth[1]) <= 0:
        raise ValueError("Service package must be a positive speed such as 100Mbps.")
    fields["bandwidth"] = bandwidth[1] + ("Mbps" if bandwidth[2].lower() == "mbps" else "Gbps")
    fields["source_status"] = source_status
    warnings = []
    phone = fields.get("phone_number", "")
    if phone and not re.fullmatch(r"\+?[\d ()-]+", phone):
        raise ValueError("Contact phone contains unexpected characters.")
    digits = re.sub(r"\D", "", phone)
    if phone and not 7 <= len(digits) <= 15:
        raise ValueError("Contact phone must contain 7–15 digits.")
    if len(digits) == 10:
        warnings.append("Phone number has 10 digits. Verify whether a leading zero is missing; the supplied value has been preserved.")
    for field in ("email", "phone_number"):
        if not fields.get(field):
            warnings.append(f"No {field.replace('_', ' ')} found. Add it if available.")
    if source_status:
        warnings.append(f"Source status is {source_status}. The local order starts in New Requests until it is allocated and scheduled.")
    return fields, warnings
