from app.core.db import SessionLocal
from app.models.crm import Customer

def test_customer_to_infrastructure_traversal():
    """
    Test that we can traverse from a Customer down to their physical Fiber Route.
    Relies on the seed data for 'Cupcake' from 05_seed_data.sql.
    """
    # Open a database session
    db = SessionLocal()
    
    try:
        # 1. Fetch the Customer
        cupcake = db.query(Customer).filter(Customer.customer_name == "Cupcake").first()
        assert cupcake is not None, "Customer 'Cupcake' not found in DB"
        assert cupcake.customer_type == "METROREACH"

        # 2. Traverse to Services
        assert len(cupcake.services) > 0, "Cupcake has no services"
        dia_service = cupcake.services[0]
        assert dia_service.service_type == "DIA"

        # 3. Traverse to Logical Configuration
        logical_config = dia_service.logical_config
        assert logical_config is not None, "Logical config missing"
        assert logical_config.bgp_asn == 65001
        assert logical_config.vlan_id == 105

        # 4. Traverse to Physical Core Allocation
        assert len(dia_service.core_allocations) > 0, "Service is not allocated to a core"
        allocation = dia_service.core_allocations[0]
        assert allocation.allocation_role == "primary"

        # 5. Traverse the ODN Tree (Core -> Cable -> Route)
        core = allocation.core
        cable = core.cable
        route = cable.route

        # Verify the physical infrastructure matches our seed logic
        assert core.core_number == 6
        assert cable.cable_name == "CABLE-N1"
        assert route.route_name == "North-Zone-Backbone"
        
        print("\n✅ SUCCESS: Successfully traversed from Customer -> Service -> Core -> Cable -> Route!")

    finally:
        # Always close the session
        db.close()