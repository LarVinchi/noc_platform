"""Durable normalized PRTG event intake and explicit sensor targets."""
from alembic import op
revision = "f519a30ce842"
down_revision = "e40b32d9f680"
branch_labels = depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE sensor_mappings (
            sensor_id varchar(100) PRIMARY KEY,
            route_id uuid REFERENCES fiber_routes(route_id),
            cable_id uuid REFERENCES fiber_cables(cable_id),
            service_id uuid REFERENCES services(service_id),
            last_state varchar(20), last_observed_at timestamptz,
            incident_id uuid REFERENCES incidents(incident_id),
            CONSTRAINT ck_sensor_one_target CHECK (num_nonnulls(route_id, cable_id, service_id) = 1)
        );
        CREATE TABLE monitoring_events (
            event_id varchar(150) PRIMARY KEY, sensor_id varchar(100) NOT NULL,
            state varchar(20) NOT NULL CHECK (state IN ('down', 'up', 'warning', 'paused', 'unknown')),
            observed_at timestamptz NOT NULL, received_at timestamptz NOT NULL DEFAULT now(),
            disposition varchar(30) NOT NULL, incident_id uuid REFERENCES incidents(incident_id)
        );
        CREATE INDEX ix_monitoring_events_sensor_id ON monitoring_events(sensor_id);
        CREATE TRIGGER audit_change AFTER INSERT OR UPDATE OR DELETE ON sensor_mappings
            FOR EACH ROW EXECUTE FUNCTION noc_capture_change('sensor_id', 'sensor_id,route_id,cable_id,service_id,last_state,last_observed_at,incident_id');
        CREATE TRIGGER audit_change AFTER INSERT ON monitoring_events
            FOR EACH ROW EXECUTE FUNCTION noc_capture_change('event_id', 'event_id,sensor_id,state,observed_at,disposition,incident_id');
    """)


def downgrade():
    op.execute("DROP TABLE monitoring_events; DROP TABLE sensor_mappings;")
