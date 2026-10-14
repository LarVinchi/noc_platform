"""Include real allocation lifecycle fields in audit snapshots."""
from alembic import op
revision = "e40b32d9f680"
down_revision = "d3a8296f170b"
branch_labels = depends_on = None

FIELDS = {
    "customers": "customer_id,service_id_code,customer_type",
    "services": "service_id,customer_id,service_type,bandwidth_mbps,status",
    "core_allocations": "allocation_id,service_id,core_id,allocation_role,start_date,end_date",
    "drop_allocations": "allocation_id,service_id,drop_cable_id,nap_port_number,is_active",
    "fiber_cores": "core_id,cable_id,core_number,allocation_status,usage_type",
}


def upgrade():
    for table, fields in FIELDS.items():
        op.execute(f"DROP TRIGGER audit_change ON {table}")
        op.execute(f"CREATE TRIGGER audit_change AFTER INSERT OR UPDATE OR DELETE ON {table} "
                   f"FOR EACH ROW EXECUTE FUNCTION noc_capture_change('{fields.split(',')[0]}', '{fields}')")


def downgrade():
    original = {
        "customers": "customer_id,customer_code",
        "services": "service_id,customer_id,service_type,bandwidth_mbps",
        "core_allocations": "allocation_id,service_id,core_id,allocation_type,status",
        "drop_allocations": "allocation_id,service_id,drop_cable_id,port_number,status",
        "fiber_cores": "core_id,status,usage_type",
    }
    for table in FIELDS:
        fields = original[table]
        op.execute(f"DROP TRIGGER audit_change ON {table}")
        op.execute(f"CREATE TRIGGER audit_change AFTER INSERT OR UPDATE OR DELETE ON {table} "
                   f"FOR EACH ROW EXECUTE FUNCTION noc_capture_change('{fields.split(',')[0]}', '{fields}')")
