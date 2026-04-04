-- 1. Consolidated Customer View (For the Main Dashboard Search)
CREATE OR REPLACE VIEW v_customer_full_details AS
SELECT 
    c.customer_name,
    c.customer_type,
    c.service_id_code,
    c.email,
    s.service_type,
    s.status AS service_status,
    s.bandwidth_mbps,
    -- Logical Data (For DIA/Layer 2)
    lc.vlan_id,
    lc.wan_ip_block,
    lc.routing_protocol,
    -- Backbone Data (For Dark Fiber & Direct Core Allocations)
    fc.core_number,
    fca.cable_name,
    fr.route_name,
    -- ODN Data (For FTTH)
    n.nap_code,
    ST_AsGeoJSON(n.location)::json AS nap_geom_json
FROM customers c
JOIN services s ON c.customer_id = s.customer_id
LEFT JOIN logical_configurations lc ON s.service_id = lc.service_id
LEFT JOIN core_allocations ca ON s.service_id = ca.service_id AND ca.end_date IS NULL
LEFT JOIN fiber_cores fc ON ca.core_id = fc.core_id
LEFT JOIN fiber_cables fca ON fc.cable_id = fca.cable_id
LEFT JOIN fiber_routes fr ON fca.route_id = fr.route_id
LEFT JOIN drop_allocations da ON s.service_id = da.service_id
LEFT JOIN drop_cables dc ON da.drop_cable_id = dc.drop_cable_id
LEFT JOIN nap n ON dc.nap_id = n.nap_id;

-- 2. Materialized View for Incident Impact (High Performance)
DROP MATERIALIZED VIEW IF EXISTS mv_customer_service_impact;

CREATE MATERIALIZED VIEW mv_customer_service_impact AS
SELECT 
    v.customer_name,
    v.service_id_code,
    v.service_type,
    v.cable_name,
    v.route_name,
    v.nap_code, -- Added NAP to impact tracking
    ca.core_id,
    fca.cable_id,
    da.drop_cable_id
FROM v_customer_full_details v
JOIN customers c ON v.service_id_code = c.service_id_code
JOIN services s ON c.customer_id = s.customer_id
-- We use LEFT joins here so we capture both Backbone cuts (Dark Fiber/DIA) AND ODN cuts (FTTH)
LEFT JOIN core_allocations ca ON s.service_id = ca.service_id AND ca.end_date IS NULL
LEFT JOIN fiber_cores fc ON ca.core_id = fc.core_id
LEFT JOIN fiber_cables fca ON fc.cable_id = fca.cable_id
LEFT JOIN drop_allocations da ON s.service_id = da.service_id;

-- Initial refresh
REFRESH MATERIALIZED VIEW mv_customer_service_impact;