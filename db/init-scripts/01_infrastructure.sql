-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2. Physical Routes & Backbone Cables (Unchanged)
CREATE TABLE IF NOT EXISTS fiber_routes (
    route_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route_name      TEXT NOT NULL,
    service_area    TEXT NOT NULL,
    geometry        geometry(LINESTRING, 4326),
    length_km       NUMERIC(10,2),
    status          TEXT CHECK (status IN ('active', 'planned', 'retired')) NOT NULL,
    created_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fiber_cables (
    cable_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route_id        UUID NOT NULL REFERENCES fiber_routes(route_id) ON DELETE CASCADE,
    cable_name      TEXT NOT NULL,
    total_cores     INTEGER NOT NULL CHECK (total_cores > 0),
    cable_type      TEXT CHECK (cable_type IN ('SM', 'MM')) NOT NULL,
    install_date    DATE,
    status          TEXT CHECK (status IN ('active', 'planned', 'retired')) NOT NULL,
    created_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fiber_cores (
    core_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cable_id           UUID NOT NULL REFERENCES fiber_cables(cable_id) ON DELETE CASCADE,
    core_number        INTEGER NOT NULL,
    usage_type         TEXT CHECK (usage_type IN ('DIA', 'DARKFIBER', 'ISP', 'FTTH', 'FREE')) NOT NULL,
    allocation_status  TEXT CHECK (allocation_status IN ('free', 'allocated', 'reserved')) NOT NULL,
    created_at         TIMESTAMP DEFAULT now(),
    UNIQUE (cable_id, core_number)
);

-- 3. ODN Hardware Nodes (Splitters and Access Points)
-- Stage 1: PFP (Primary Flexibility Point) - Fed by Backbone Core
CREATE TABLE IF NOT EXISTS pfp (
    pfp_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    core_id     UUID NOT NULL REFERENCES fiber_cores(core_id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    split_ratio TEXT CHECK (split_ratio IN ('1:2', '1:4', '1:8')) NOT NULL DEFAULT '1:4',
    location    geometry(POINT, 4326),
    created_at  TIMESTAMP DEFAULT now()
);

-- Stage 2: PFS (Primary Fiber Splitter) - Fed by PFP
CREATE TABLE IF NOT EXISTS pfs (
    pfs_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pfp_id      UUID NOT NULL REFERENCES pfp(pfp_id) ON DELETE CASCADE, 
    name        TEXT NOT NULL,
    split_ratio TEXT CHECK (split_ratio IN ('1:4', '1:8', '1:16')) NOT NULL DEFAULT '1:8',
    location    geometry(POINT, 4326),
    created_at  TIMESTAMP DEFAULT now()
);

-- Stage 3: NAP (Network Access Point) - Fed by PFS
CREATE TABLE IF NOT EXISTS nap (
    nap_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pfs_id      UUID NOT NULL REFERENCES pfs(pfs_id) ON DELETE CASCADE, 
    nap_code    TEXT UNIQUE NOT NULL,
    total_ports INTEGER NOT NULL CHECK (total_ports > 0),
    location    geometry(POINT, 4326),
    created_at  TIMESTAMP DEFAULT now()
);

-- 4. ODN Distribution Fibers (The physical cables between your splitters)
CREATE TABLE IF NOT EXISTS distribution_fibers (
    dist_fiber_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cable_name      TEXT NOT NULL, -- e.g., 'DIST-CBL-001'
    source_pfp_id   UUID REFERENCES pfp(pfp_id), -- Starts at a PFP
    dest_pfs_id     UUID REFERENCES pfs(pfs_id), -- Ends at a PFS
    source_pfs_id   UUID REFERENCES pfs(pfs_id), -- OR Starts at a PFS
    dest_nap_id     UUID REFERENCES nap(nap_id), -- OR Ends at a NAP
    
    -- NEW: Track which specific splitter leg/port is sending the light
    source_port     INTEGER NOT NULL, 
    
    fiber_number    INTEGER NOT NULL,
    status          TEXT CHECK (status IN ('free', 'allocated', 'bad')) DEFAULT 'free',
    created_at      TIMESTAMP DEFAULT now(),
    -- Ensure it's either a PFP->PFS link OR a PFS->NAP link, not mixed
    CONSTRAINT chk_dist_link CHECK (
        (source_pfp_id IS NOT NULL AND dest_pfs_id IS NOT NULL AND source_pfs_id IS NULL AND dest_nap_id IS NULL) OR
        (source_pfs_id IS NOT NULL AND dest_nap_id IS NOT NULL AND source_pfp_id IS NULL AND dest_pfs_id IS NULL)
    )
);

-- 5. Drop Cables (Final connection to Customer)
CREATE TABLE IF NOT EXISTS drop_cables (
    drop_cable_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nap_id             UUID NOT NULL REFERENCES nap(nap_id) ON DELETE CASCADE,
    drop_cable_code    TEXT UNIQUE NOT NULL,
    length_m           NUMERIC(10,2),
    status             TEXT CHECK (status IN ('active', 'damaged', 'retired')) NOT NULL,
    created_at         TIMESTAMP DEFAULT now()
);