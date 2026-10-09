from datetime import datetime
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.incidents import TicketSequence, TICKET_CATEGORY_CODES


def generate_tt_number(db: Session, ticket_category: str) -> str:
    """
    Generates the next ticket number for a given category, in the same
    format as the historical incident log: {CODE}_IM_{DDMMYYYY}_{SEQUENCE}
    e.g. PW_IM_04092026_0515

    ticket_category must be one of: FIBER, POWER, TECHNICAL, MAINTENANCE, OTHER.
    Falls back to OTHER/OT for anything unrecognized rather than failing the
    incident save — a bad category should never block logging an incident.
    """
    code = TICKET_CATEGORY_CODES.get((ticket_category or "").upper(), "OT")

    # Atomic upsert also handles simultaneous first tickets for a category.
    statement = insert(TicketSequence).values(category_code=code, last_sequence=1)
    next_seq = db.execute(statement.on_conflict_do_update(
        index_elements=[TicketSequence.category_code],
        set_={"last_sequence": TicketSequence.last_sequence + 1},
    ).returning(TicketSequence.last_sequence)).scalar_one()

    date_str = datetime.utcnow().strftime("%d%m%Y")
    return f"{code}_IM_{date_str}_{next_seq:04d}"
