CREATE DATABASE IF NOT EXISTS netflow;

CREATE TABLE IF NOT EXISTS netflow.flows
(
    event_time DateTime64(3, 'UTC'),
    end_time DateTime64(3, 'UTC'),
    exporter_ip IPv6,
    source_ip IPv6,
    destination_ip IPv6,
    source_port UInt16,
    destination_port UInt16,
    protocol UInt8,
    bytes UInt64,
    packets UInt64,
    direction Enum8('unknown' = 0, 'upload' = 1, 'download' = 2),
    subscriber_id UInt64 DEFAULT 0,
    subscriber_name LowCardinality(String) DEFAULT '',
    plan_mbps UInt32 DEFAULT 0,
    access_type Enum8('unknown' = 0, 'pppoe' = 1, 'dhcp' = 2, 'static' = 3),
    domain LowCardinality(String) DEFAULT '',
    application LowCardinality(String) DEFAULT '',
    attribution_confidence Enum8('unknown' = 0, 'low' = 1, 'medium' = 2, 'high' = 3),
    asn UInt32 DEFAULT 0,
    country FixedString(2) DEFAULT '',
    inserted_at DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (toDate(event_time), subscriber_id, event_time, destination_ip)
TTL event_time + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS netflow.dns_answers
(
    event_time DateTime64(3, 'UTC'),
    client_ip IPv6,
    domain String,
    answer_ip IPv6,
    ttl UInt32,
    resolver LowCardinality(String),
    expires_at DateTime64(3, 'UTC') MATERIALIZED event_time + toIntervalSecond(ttl)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (client_ip, answer_ip, event_time)
TTL event_time + INTERVAL 30 DAY DELETE;

CREATE TABLE IF NOT EXISTS netflow.hourly_subscriber_usage
(
    hour DateTime('UTC'),
    subscriber_id UInt64,
    subscriber_name String,
    bytes_up UInt64,
    bytes_down UInt64,
    active_seconds UInt64,
    peak_mbps Float64,
    saturation_ratio Float64
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(hour)
ORDER BY (subscriber_id, hour);
