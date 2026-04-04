-- 1. Create 2 Main Backbone Routes
INSERT INTO fiber_routes (route_name, service_area, length_km, status) VALUES 
('North-Zone-Backbone', 'Lagos Mainland', 25.5, 'active'),
('South-Zone-Backbone', 'Lagos Island', 18.2, 'active');

-- 2. Add Cables to those Routes
INSERT INTO fiber_cables (route_id, cable_name, total_cores, cable_type, status)
SELECT route_id, 'CABLE-N1', 48, 'SM', 'active' FROM fiber_routes WHERE route_name = 'North-Zone-Backbone';
INSERT INTO fiber_cables (route_id, cable_name, total_cores, cable_type, status)
SELECT route_id, 'CABLE-S1', 24, 'SM', 'active' FROM fiber_routes WHERE route_name = 'South-Zone-Backbone';

-- 3. Add Cores for the North Cable (Generating 10 cores, mixed usage)
INSERT INTO fiber_cores (cable_id, core_number, usage_type, allocation_status)
SELECT cable_id, generate_series(1, 5), 'FTTH', 'free' FROM fiber_cables WHERE cable_name = 'CABLE-N1';
INSERT INTO fiber_cores (cable_id, core_number, usage_type, allocation_status)
SELECT cable_id, generate_series(6, 8), 'DIA', 'free' FROM fiber_cables WHERE cable_name = 'CABLE-N1';
INSERT INTO fiber_cores (cable_id, core_number, usage_type, allocation_status)
SELECT cable_id, generate_series(9, 10), 'DARKFIBER', 'free' FROM fiber_cables WHERE cable_name = 'CABLE-N1';

-- 4. Build the ODN Tree for FTTH (Using Core 1)
-- Stage 1: PFP attached to Core 1
INSERT INTO pfp (core_id, name, split_ratio)
SELECT core_id, 'PFP-YABA-MAIN', '1:4' FROM fiber_cores WHERE core_number = 1 LIMIT 1;

-- Stage 2: PFS attached to PFP
INSERT INTO pfs (pfp_id, name, split_ratio)
SELECT pfp_id, 'PFS-YABA-01', '1:8' FROM pfp WHERE name = 'PFP-YABA-MAIN' LIMIT 1;

-- Stage 3: NAP attached to PFS
INSERT INTO nap (pfs_id, nap_code, total_ports)
SELECT pfs_id, 'NAP-YABA-001', 8 FROM pfs WHERE name = 'PFS-YABA-01' LIMIT 1;

-- Add physical distribution fibers connecting them
-- Cable from PFP to PFS (Plugging into Splitter Leg 1 of the PFP)
INSERT INTO distribution_fibers (cable_name, source_pfp_id, dest_pfs_id, source_port, fiber_number, status)
SELECT 'DIST-CBL-001', pfp.pfp_id, pfs.pfs_id, 1, 1, 'allocated' 
FROM pfp, pfs WHERE pfp.name = 'PFP-YABA-MAIN' AND pfs.name = 'PFS-YABA-01';

-- Cable from PFS to NAP (Plugging into Splitter Leg 3 of the PFS)
INSERT INTO distribution_fibers (cable_name, source_pfs_id, dest_nap_id, source_port, fiber_number, status)
SELECT 'DIST-CBL-002', pfs.pfs_id, nap.nap_id, 3, 1, 'allocated' 
FROM pfs, nap WHERE pfs.name = 'PFS-YABA-01' AND nap.nap_code = 'NAP-YABA-001';

-- 5. Add Customers
INSERT INTO customers (customer_type, customer_name, service_id_code, email, address) VALUES 
('METROREACH', 'Cupcake', 'SVC-MR-001', 'cupcake@metroreach.com', '123 Fiber St, North Lagos'),
('ISP', 'SwiftNet Solutions', 'SVC-ISP-002', 'ops@swiftnet.ng', '45 Business Row, Ikeja'),
('METROREACH', 'Glo-Tech Hub', 'SVC-MR-003', 'admin@glotech.com', 'Tech Plaza, Yaba');

-- 6. Give Customers DIVERSE Services (Not just FTTH)
-- Cupcake gets DIA (Dedicated Internet)
INSERT INTO services (customer_id, service_type, bandwidth_mbps, status)
SELECT customer_id, 'DIA', 500, 'active' FROM customers WHERE customer_name = 'Cupcake';

-- SwiftNet gets DARK FIBER
INSERT INTO services (customer_id, service_type, bandwidth_mbps, status)
SELECT customer_id, 'DARKFIBER', NULL, 'active' FROM customers WHERE customer_name = 'SwiftNet Solutions';

-- Glo-Tech gets FTTH
INSERT INTO services (customer_id, service_type, bandwidth_mbps, status)
SELECT customer_id, 'FTTH', 100, 'active' FROM customers WHERE customer_name = 'Glo-Tech Hub';

-- 7. Add Logical Configurations for DIA (Cupcake)
INSERT INTO logical_configurations (service_id, vlan_id, wan_ip_block, lan_ip_block, routing_protocol, bgp_asn)
SELECT service_id, 105, '192.168.100.0/30', '10.50.0.0/24', 'BGP', 65001 
FROM services WHERE service_type = 'DIA';

-- 8. Core Allocations (Backbone Layer)
-- Allocate Cupcake (DIA) to Core 6
INSERT INTO core_allocations (service_id, core_id, allocation_role)
SELECT s.service_id, fc.core_id, 'primary'
FROM services s, fiber_cores fc
WHERE s.service_type = 'DIA' AND fc.core_number = 6 LIMIT 1;

-- Allocate SwiftNet (Dark Fiber) to Core 9
INSERT INTO core_allocations (service_id, core_id, allocation_role)
SELECT s.service_id, fc.core_id, 'primary'
FROM services s, fiber_cores fc
WHERE s.service_type = 'DARKFIBER' AND fc.core_number = 9 LIMIT 1;

-- Update the status of those cores to 'allocated'
UPDATE fiber_cores SET allocation_status = 'allocated' WHERE core_number IN (6, 9);

-- 9. FTTH Drop Allocations (For Glo-Tech Hub)
-- Create a drop cable from the NAP
INSERT INTO drop_cables (nap_id, drop_cable_code, length_m, status)
SELECT nap_id, 'DROP-GT-001', 45.5, 'active' FROM nap WHERE nap_code = 'NAP-YABA-001';

-- Allocate Glo-Tech Hub to that drop cable
INSERT INTO drop_allocations (service_id, drop_cable_id, nap_port_number)
SELECT s.service_id, dc.drop_cable_id, 1
FROM services s, drop_cables dc
WHERE s.service_type = 'FTTH' AND dc.drop_cable_code = 'DROP-GT-001' LIMIT 1;

-- 10. Log a Sample Incident (Testing the incident mapping)
-- Let's pretend the North-Zone-Backbone cable was cut
INSERT INTO incidents (incident_type, description, status, cable_id)
SELECT 'fiber_cut', 'Excavator cut the CABLE-N1 near Yaba', 'open', cable_id
FROM fiber_cables WHERE cable_name = 'CABLE-N1' LIMIT 1;