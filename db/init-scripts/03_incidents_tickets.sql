CREATE TABLE IF NOT EXISTS incidents (
    incident_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_type   TEXT CHECK (incident_type IN ('Environmental Issue','Power Issue','Fiber Incident','Interface or Link Issue','Virtualization Incident','Service Unavailability','Infrastructure Damage','Security & Safety Alert','Monitoring Alert','Testing Activity','Migration & Upgrade','Maintenance','Other','Alarms & Triggers','Fiberwatch issue','Network Configuration Issue','Splitter & Passive Components','Transmission')) NOT NULL,
    description     TEXT,
    reported_at     TIMESTAMP DEFAULT now(),
    resolved_at     TIMESTAMP,
    status          TEXT CHECK (status IN ('open','investigating','pending','resolved','closed','aborted')) NOT NULL,
    
    -- Expanded Foreign Keys to tag incidents to ANY level of the network
    route_id        UUID REFERENCES fiber_routes(route_id),
    cable_id        UUID REFERENCES fiber_cables(cable_id),
    core_id         UUID REFERENCES fiber_cores(core_id),
    pfs_id          UUID REFERENCES pfs(pfs_id),
    pfp_id          UUID REFERENCES pfp(pfp_id),
    nap_id          UUID REFERENCES nap(nap_id),
    drop_cable_id   UUID REFERENCES drop_cables(drop_cable_id)
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     UUID NOT NULL REFERENCES incidents(incident_id),
    service_id      UUID REFERENCES services(service_id), -- Made optional: an incident might affect a route before customers are identified
    assigned_to     TEXT,
    priority        TEXT CHECK (priority IN ('low','medium','high','critical')) DEFAULT 'medium',
    created_at      TIMESTAMP DEFAULT now(),
    updated_at      TIMESTAMP DEFAULT now(),
    status          TEXT CHECK (status IN ('open','investigating','pending','resolved','closed','aborted')) DEFAULT 'open'
);