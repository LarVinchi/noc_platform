"""Transactional operational audit with restricted snapshots."""
from alembic import op

revision = "d3a8296f170b"
down_revision = "c1b4a8926e05"
branch_labels = depends_on = None

# Explicit allowlists avoid duplicating customer contacts, request text, notes,
# uploaded geometry, and other sensitive/large fields in the audit store.
TABLES = {
    "service_orders": ("order_id", "status", "nap_id", "pfp_id", "pfs_id", "drop_cable_id", "nap_port", "activated_service_id", "planned_install_date", "completion_date"),
    "install_metrics": ("id", "order_id", "flexscan_result_dbm", "checklist_completed", "acceptance_doc_url"),
    "incidents": ("incident_id", "status", "severity", "reported_at", "resolved_at", "route_id", "cable_id", "core_id", "nap_id", "is_planned"),
    "activity_entries": ("activity_id", "status", "category", "severity", "shift", "incident_id", "order_id", "due_at", "handover"),
    "customers": ("customer_id", "customer_code"),
    "services": ("service_id", "customer_id", "service_type", "bandwidth_mbps"),
    "core_allocations": ("allocation_id", "service_id", "core_id", "allocation_type", "status"),
    "drop_allocations": ("allocation_id", "service_id", "drop_cable_id", "port_number", "status"),
    "nap": ("nap_id", "pfs_id", "nap_code", "total_ports", "status"),
    "drop_cables": ("drop_cable_id", "nap_id", "drop_cable_code", "status"),
    "fiber_routes": ("route_id", "route_name", "status", "length_km"),
    "fiber_cores": ("core_id", "status", "usage_type"),
    "network_map_imports": ("import_id", "sha256"),
    "map_route_links": ("import_id", "feature_index", "route_id"),
}


def upgrade():
    op.execute("""
        CREATE TABLE audit_events (
            audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            actor_id text NOT NULL,
            actor_verified boolean NOT NULL DEFAULT false,
            request_id text NOT NULL,
            entity_type text NOT NULL,
            entity_id text NOT NULL,
            action text NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
            before_state jsonb,
            after_state jsonb
        );
        CREATE INDEX ix_audit_entity ON audit_events(entity_id, audit_id DESC);
        CREATE FUNCTION noc_capture_change() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE old_data jsonb; new_data jsonb; previous jsonb; current_data jsonb; identifier text;
        BEGIN
            IF TG_OP <> 'INSERT' THEN old_data := to_jsonb(OLD); END IF;
            IF TG_OP <> 'DELETE' THEN new_data := to_jsonb(NEW); END IF;
            IF TG_OP = 'UPDATE' AND old_data IS NOT DISTINCT FROM new_data THEN RETURN NEW; END IF;
            IF old_data IS NOT NULL THEN
                SELECT jsonb_object_agg(key, value) INTO previous FROM jsonb_each(old_data)
                WHERE key = ANY(string_to_array(TG_ARGV[1], ','));
            END IF;
            IF new_data IS NOT NULL THEN
                SELECT jsonb_object_agg(key, value) INTO current_data FROM jsonb_each(new_data)
                WHERE key = ANY(string_to_array(TG_ARGV[1], ','));
            END IF;
            identifier := COALESCE(new_data, old_data)->>TG_ARGV[0];
            IF TG_TABLE_NAME = 'map_route_links' THEN
                identifier := identifier || ':' || (COALESCE(new_data, old_data)->>'feature_index');
            END IF;
            INSERT INTO audit_events(actor_id, actor_verified, request_id, entity_type, entity_id,
                                     action, before_state, after_state)
            VALUES (COALESCE(NULLIF(current_setting('noc.actor', true), ''), 'database-unattributed'),
                    COALESCE(NULLIF(current_setting('noc.verified', true), ''), 'false')::boolean,
                    COALESCE(current_setting('noc.request_id', true), ''), TG_TABLE_NAME,
                    identifier, TG_OP, previous, current_data);
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$;
        CREATE FUNCTION noc_protect_audit() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Audit history is append-only'; END $$;
        CREATE TRIGGER protect_audit BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION noc_protect_audit();
        CREATE TRIGGER protect_audit_truncate BEFORE TRUNCATE ON audit_events
            FOR EACH STATEMENT EXECUTE FUNCTION noc_protect_audit();
    """)
    for table, fields in TABLES.items():
        op.execute(f"CREATE TRIGGER audit_change AFTER INSERT OR UPDATE OR DELETE ON {table} "
                   f"FOR EACH ROW EXECUTE FUNCTION noc_capture_change('{fields[0]}', '{','.join(fields)}')")


def downgrade():
    for table in TABLES:
        op.execute(f"DROP TRIGGER audit_change ON {table}")
    op.execute("DROP FUNCTION noc_capture_change(); DROP TABLE audit_events; DROP FUNCTION noc_protect_audit();")
