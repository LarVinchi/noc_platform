-- 1. Customers Table (Unchanged)
CREATE TABLE IF NOT EXISTS customers (
    customer_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_type       TEXT CHECK (customer_type IN ('METROREACH', 'ISP')) NOT NULL,
    customer_name       TEXT NOT NULL,
    service_id_code     TEXT UNIQUE NOT NULL,
    email               TEXT,
    phone               TEXT,
    address             TEXT,
    created_at          TIMESTAMP DEFAULT now()
);

-- 2. Services Table (Added LAYER2 to constraints)
CREATE TABLE IF NOT EXISTS services (
    service_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         UUID NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    service_type        TEXT CHECK (service_type IN ('DIA', 'DARKFIBER', 'FTTH', 'ISP_FTTH', 'LAYER2')) NOT NULL,
    bandwidth_mbps      INTEGER,
    status              TEXT CHECK (status IN ('active', 'suspended', 'terminated')) NOT NULL DEFAULT 'active',
    created_at          TIMESTAMP DEFAULT now()
);

-- NEW: 3. Logical Configurations for DIA and Layer 2
CREATE TABLE IF NOT EXISTS logical_configurations (
    config_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id         UUID NOT NULL REFERENCES services(service_id) ON DELETE CASCADE,
    vlan_id            INTEGER,
    wan_ip_block       TEXT, -- e.g., '192.168.1.0/30'
    lan_ip_block       TEXT, -- e.g., '10.0.0.0/24'
    mac_address        TEXT, -- Helpful for Layer 2 bindings
    routing_protocol   TEXT CHECK (routing_protocol IN ('STATIC', 'BGP', 'OSPF', 'NONE')) DEFAULT 'NONE',
    bgp_asn            INTEGER,
    created_at         TIMESTAMP DEFAULT now()
);

-- 4. Core Allocations (Unchanged)
CREATE TABLE IF NOT EXISTS core_allocations (
    allocation_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id         UUID NOT NULL REFERENCES services(service_id) ON DELETE CASCADE,
    core_id            UUID NOT NULL REFERENCES fiber_cores(core_id),
    allocation_role    TEXT CHECK (allocation_role IN ('primary', 'backup')) DEFAULT 'primary',
    start_date         DATE DEFAULT CURRENT_DATE,
    end_date           DATE DEFAULT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_core_active_allocation 
ON core_allocations (core_id) 
WHERE end_date IS NULL;

-- 5. Drop Allocations (Unchanged)
CREATE TABLE IF NOT EXISTS drop_allocations (
    allocation_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id         UUID NOT NULL REFERENCES services(service_id) ON DELETE CASCADE,
    drop_cable_id      UUID NOT NULL REFERENCES drop_cables(drop_cable_id),
    nap_port_number    INTEGER,
    is_active          BOOLEAN DEFAULT TRUE,
    created_at         TIMESTAMP DEFAULT now()
);