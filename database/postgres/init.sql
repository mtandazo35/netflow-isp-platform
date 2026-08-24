CREATE TABLE IF NOT EXISTS routers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    exporter_ip INET NOT NULL UNIQUE,
    node_name TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subscribers (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT,
    plan_mbps INTEGER NOT NULL CHECK (plan_mbps > 0),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subscriber_ip_assignments (
    id BIGSERIAL PRIMARY KEY,
    subscriber_id BIGINT NOT NULL REFERENCES subscribers(id),
    router_id BIGINT REFERENCES routers(id),
    assigned_ip INET NOT NULL,
    assignment_type TEXT NOT NULL CHECK (assignment_type IN ('pppoe', 'dhcp', 'static')),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    source_system TEXT NOT NULL DEFAULT 'manual',
    calling_station_id TEXT,
    acct_session_id TEXT,
    mac_address MACADDR,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE INDEX IF NOT EXISTS idx_assignments_ip_time
    ON subscriber_ip_assignments (assigned_ip, started_at, ended_at);

CREATE INDEX IF NOT EXISTS idx_assignments_subscriber_time
    ON subscriber_ip_assignments (subscriber_id, started_at, ended_at);
