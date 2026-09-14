from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.db import Base


# ============================================================
# TICKET CATEGORIES
# ============================================================
# These are the high-level categories used to generate TT
# numbers.
#
# Example:
#   FIBER       -> OF
#   POWER       -> PW
#   TECHNICAL   -> TN
#   MAINTENANCE -> MA
#   OTHER       -> OT
#
# Historical TT numbers follow this pattern:
#   OF_IM_...
#   PW_IM_...
#   TN_IM_...
#   MA_IM_...
#   OT_IM_...
# ============================================================

TICKET_CATEGORY_CODES = {
    "FIBER": "OF",
    "POWER": "PW",
    "TECHNICAL": "TN",
    "MAINTENANCE": "MA",
    "OTHER": "OT",
}


VALID_TICKET_CATEGORIES = set(TICKET_CATEGORY_CODES.keys())


# ============================================================
# STATUS
# ============================================================
# The ORIGINAL constraint on this column (db/init-scripts/03_incidents_tickets.sql)
# only allowed: open, investigating, resolved, closed — lowercase.
# The frontend Incident Management page needs a richer lifecycle
# (matching how staff actually track incidents day to day), so this
# extends the same lowercase vocabulary rather than replacing it:
#   in_progress -> investigating's replacement, but we keep
#   'investigating' for continuity and add 'pending' and 'aborted'.
VALID_STATUSES = {"open", "investigating", "pending", "resolved", "closed", "aborted"}


# ============================================================
# INCIDENT TYPES
# ============================================================
# IMPORTANT:
#
# incident_type and ticket_category are DIFFERENT concepts.
#
# Example:
#
#   incident_type    = "Environmental Issue"
#   ticket_category  = "POWER"
#
# Another example:
#
#   incident_type    = "Fiber Incident"
#   ticket_category  = "FIBER"
#
# The incident type describes WHAT happened.
# The ticket category determines HOW the TT number is generated.
# ============================================================

VALID_INCIDENT_TYPES = {
    "Environmental Issue",
    "Power Issue",
    "Fiber Incident",
    "Interface or Link Issue",
    "Virtualization Incident",
    "Service Unavailability",
    "Infrastructure Damage",
    "Security & Safety Alert",
    "Monitoring Alert",
    "Testing Activity",
    "Migration & Upgrade",
    "Maintenance",
    "Other",
    # Added after reviewing the full historical incident log — these are
    # real, legitimate categories that appear in the data (1-6 rows each),
    # not typos of the categories above. Folding them into "Other" would
    # have silently lost that classification.
    "Alarms & Triggers",
    "Fiberwatch issue",
    "Network Configuration Issue",
    "Splitter & Passive Components",
    "Transmission",
}


# Normalization of known historical values.
#
# This should only normalize equivalent values.
# It must NOT convert incident types into ticket categories.
INCIDENT_TYPE_NORMALIZATION = {
    "Environmental": "Environmental Issue",
    "Power": "Power Issue",
    "Fiber": "Fiber Incident",
    "Other": "Other",
}


def normalize_incident_type(value: str | None) -> str:
    """
    Normalize an incident type from the historical spreadsheet.

    Examples:
        Environmental -> Environmental Issue
        Power         -> Power Issue
        Fiber         -> Fiber Incident

    Unknown values are preserved so the importer can explicitly
    validate/report them rather than silently changing them.
    """
    if value is None:
        return "Other"

    value = str(value).strip()

    if not value:
        return "Other"

    return INCIDENT_TYPE_NORMALIZATION.get(value, value)


class Incident(Base):
    __tablename__ = "incidents"

    # ========================================================
    # TABLE-LEVEL CONSTRAINTS
    # ========================================================
    # Built directly from VALID_INCIDENT_TYPES / VALID_TICKET_CATEGORIES
    # above, so the DB constraint and the Python-side validation are
    # always the same list — extend the sets above, not this directly.
    __table_args__ = (
        CheckConstraint(
            "incident_type IN (" + ", ".join(f"'{t}'" for t in sorted(VALID_INCIDENT_TYPES)) + ")",
            name="incidents_incident_type_check",
        ),
        CheckConstraint(
            "ticket_category IS NULL OR ticket_category IN ("
            + ", ".join(f"'{c}'" for c in sorted(VALID_TICKET_CATEGORIES)) + ")",
            name="incidents_ticket_category_check",
        ),
        CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in sorted(VALID_STATUSES)) + ")",
            name="incidents_status_check",
        ),
    )

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    incident_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # ========================================================
    # INCIDENT INFORMATION
    # ========================================================

    # Actual type of incident.
    #
    # Examples:
    #   Environmental Issue
    #   Power Issue
    #   Fiber Incident
    #   Maintenance
    #   Infrastructure Damage
    incident_type = Column(
        String,
        nullable=False,
    )

    description = Column(
        String,
        nullable=True,
    )

    reported_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    resolved_at = Column(
        DateTime,
        nullable=True,
    )

    status = Column(
        String,
        nullable=False,
        default="open",
    )

    # ========================================================
    # TICKETING
    # ========================================================

    # Historical or automatically generated TT number.
    #
    # Examples:
    #   PW_IM_23012024_0157
    #   OF_IM_04092026_0515
    tt_number = Column(
        String,
        unique=True,
        nullable=True,
        index=True,
    )

    # High-level category used for TT number generation.
    #
    # Valid values:
    #   FIBER
    #   POWER
    #   TECHNICAL
    #   MAINTENANCE
    #   OTHER
    ticket_category = Column(
        String,
        nullable=True,
    )

    # ========================================================
    # HISTORICAL INCIDENT DATA
    # ========================================================

    category = Column(
        String,
        nullable=True,
    )

    severity = Column(
        String,
        nullable=True,
    )

    short_description = Column(
        String,
        nullable=True,
    )

    notes = Column(
        String,
        nullable=True,
    )

    reason_for_delay = Column(
        String,
        nullable=True,
    )

    rfo_root_cause = Column(
        String,
        nullable=True,
    )

    rfo_root_cause_detail = Column(
        String,
        nullable=True,
    )

    impact = Column(
        String,
        nullable=True,
    )

    impact_details = Column(
        String,
        nullable=True,
    )

    is_planned = Column(
        Boolean,
        nullable=True,
    )

    network_route = Column(
        String,
        nullable=True,
    )

    network_node = Column(
        String,
        nullable=True,
    )

    resolution_team = Column(
        String,
        nullable=True,
    )

    resolution_method = Column(
        String,
        nullable=True,
    )

    responsible_person = Column(
        String,
        nullable=True,
    )

    opened_by = Column(
        String,
        nullable=True,
    )

    closed_by = Column(
        String,
        nullable=True,
    )

    # ========================================================
    # PHYSICAL INFRASTRUCTURE REFERENCES
    # ========================================================

    route_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fiber_routes.route_id"),
    )

    cable_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fiber_cables.cable_id"),
    )

    core_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fiber_cores.core_id"),
    )

    pfs_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pfs.pfs_id"),
    )

    pfp_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pfp.pfp_id"),
    )

    nap_id = Column(
        UUID(as_uuid=True),
        ForeignKey("nap.nap_id"),
    )

    drop_cable_id = Column(
        UUID(as_uuid=True),
        ForeignKey("drop_cables.drop_cable_id"),
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    tickets = relationship(
        "Ticket",
        back_populates="incident",
        cascade="all, delete",
    )


class TicketSequence(Base):
    """
    Stores the latest sequence number for each TT category.

    Example:

        PW -> 157
        OF -> 321
        TN -> 98
        MA -> 42
        OT -> 17

    The next generated ticket increments the appropriate
    sequence atomically.
    """

    __tablename__ = "ticket_sequences"

    category_code = Column(
        String,
        primary_key=True,
    )

    last_sequence = Column(
        Integer,
        nullable=False,
        default=0,
    )


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id"),
        nullable=False,
    )

    service_id = Column(
        UUID(as_uuid=True),
        ForeignKey("services.service_id"),
        nullable=True,
    )

    assigned_to = Column(
        String,
        nullable=True,
    )

    priority = Column(
        String,
        default="medium",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    status = Column(
        String,
        default="open",
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    incident = relationship(
        "Incident",
        back_populates="tickets",
    )

    service = relationship("Service")