from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from .config import get_settings
from .db import get_clickhouse
from .models import DNSAnswerBatch, FlowBatch


FLOW_COLUMNS = [
    "event_time", "end_time", "exporter_ip", "source_ip", "destination_ip",
    "source_port", "destination_port", "protocol", "bytes", "packets",
    "direction", "subscriber_id", "subscriber_name", "plan_mbps", "access_type", "domain",
    "application", "attribution_confidence", "asn", "country",
]


def require_ingest_key(x_api_key: str | None = Header(default=None)):
    expected = get_settings().ingest_api_key
    if not expected or expected == "disabled":
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid ingestion API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    get_clickhouse.cache_clear()


app = FastAPI(
    title="NetFlow ISP API",
    version="0.1.0",
    description="Analitica NetFlow por abonado, dominio y aplicacion.",
    lifespan=lifespan,
)


@app.get("/health")
def health(client=Depends(get_clickhouse)):
    try:
        client.command("SELECT 1")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="ClickHouse unavailable") from exc
    return {"status": "ok"}


@app.post("/api/v1/flows", status_code=202, dependencies=[Depends(require_ingest_key)])
def ingest_flows(batch: FlowBatch, client=Depends(get_clickhouse)):
    rows = []
    for flow in batch.flows:
        data = flow.model_dump()
        rows.append([
            data[column] if column not in {"exporter_ip", "source_ip", "destination_ip"}
            else str(data[column])
            for column in FLOW_COLUMNS
        ])
    client.insert("flows", rows, column_names=FLOW_COLUMNS)
    return {"accepted": len(rows)}


@app.post("/api/v1/dns-answers", status_code=202, dependencies=[Depends(require_ingest_key)])
def ingest_dns_answers(batch: DNSAnswerBatch, client=Depends(get_clickhouse)):
    columns = ["event_time", "client_ip", "domain", "answer_ip", "ttl", "resolver"]
    rows = []
    for answer in batch.answers:
        data = answer.model_dump()
        rows.append([
            data["event_time"],
            str(data["client_ip"]),
            data["domain"].rstrip(".").lower(),
            str(data["answer_ip"]),
            data["ttl"],
            data["resolver"],
        ])
    client.insert("dns_answers", rows, column_names=columns)
    return {"accepted": len(rows)}


@app.get("/api/v1/analytics/top-subscribers")
def top_subscribers(
    hours: int = Query(default=24, ge=1, le=744),
    limit: int = Query(default=20, ge=1, le=200),
    client=Depends(get_clickhouse),
):
    result = client.query(
        """
        SELECT
            subscriber_id,
            any(subscriber_name) AS subscriber_name,
            sumIf(bytes, direction = 'download') AS bytes_down,
            sumIf(bytes, direction = 'upload') AS bytes_up,
            count() AS flows,
            uniqExact(destination_ip) AS unique_destinations
        FROM flows
        WHERE event_time >= now() - toIntervalHour({hours:UInt32})
          AND subscriber_id > 0
        GROUP BY subscriber_id
        ORDER BY bytes_down + bytes_up DESC
        LIMIT {limit:UInt32}
        """,
        parameters={"hours": hours, "limit": limit},
    )
    return {"hours": hours, "items": [dict(zip(result.column_names, row)) for row in result.result_rows]}


@app.get("/api/v1/analytics/overview")
def overview(
    hours: int = Query(default=24, ge=1, le=744),
    client=Depends(get_clickhouse),
):
    result = client.query(
        """
        SELECT
            sum(bytes) AS total_bytes,
            sumIf(bytes, direction = 'download') AS bytes_down,
            sumIf(bytes, direction = 'upload') AS bytes_up,
            uniqExactIf(subscriber_id, subscriber_id > 0) AS subscribers,
            count() AS flows,
            uniqExact(exporter_ip) AS exporters
        FROM flows
        WHERE event_time >= now() - toIntervalHour({hours:UInt32})
        """,
        parameters={"hours": hours},
    )
    values = dict(zip(result.column_names, result.result_rows[0])) if result.result_rows else {}
    return {"hours": hours, **values}


@app.get("/api/v1/analytics/top-destinations")
def top_destinations(
    hours: int = Query(default=24, ge=1, le=744),
    limit: int = Query(default=20, ge=1, le=200),
    client=Depends(get_clickhouse),
):
    result = client.query(
        """
        SELECT
            destination_ip,
            anyIf(domain, domain != '') AS domain,
            anyIf(application, application != '') AS application,
            sum(bytes) AS total_bytes,
            uniqExactIf(subscriber_id, subscriber_id > 0) AS subscribers,
            count() AS flows
        FROM flows
        WHERE event_time >= now() - toIntervalHour({hours:UInt32})
        GROUP BY destination_ip
        ORDER BY total_bytes DESC
        LIMIT {limit:UInt32}
        """,
        parameters={"hours": hours, "limit": limit},
    )
    return {"hours": hours, "items": [dict(zip(result.column_names, row)) for row in result.result_rows]}


@app.get("/api/v1/analytics/subscribers/{subscriber_id}/domains")
def subscriber_domains(
    subscriber_id: int,
    hours: int = Query(default=24, ge=1, le=744),
    limit: int = Query(default=50, ge=1, le=500),
    client=Depends(get_clickhouse),
):
    result = client.query(
        """
        SELECT
            if(domain = '', 'unidentified', domain) AS domain_name,
            any(application) AS application,
            min(event_time) AS first_seen,
            max(end_time) AS last_seen,
            sum(bytes) AS total_bytes,
            sumIf(bytes, direction = 'download') AS bytes_down,
            sumIf(bytes, direction = 'upload') AS bytes_up,
            sum(greatest(0, dateDiff('second', event_time, end_time))) AS active_seconds,
            max(attribution_confidence) AS confidence
        FROM flows
        WHERE subscriber_id = {subscriber_id:UInt64}
          AND event_time >= now() - toIntervalHour({hours:UInt32})
        GROUP BY domain_name
        ORDER BY total_bytes DESC
        LIMIT {limit:UInt32}
        """,
        parameters={"subscriber_id": subscriber_id, "hours": hours, "limit": limit},
    )
    return {"subscriber_id": subscriber_id, "hours": hours, "items": [dict(zip(result.column_names, row)) for row in result.result_rows]}


@app.get("/api/v1/analytics/resale-candidates")
def resale_candidates(
    hours: int = Query(default=168, ge=24, le=744),
    limit: int = Query(default=50, ge=1, le=200),
    client=Depends(get_clickhouse),
):
    result = client.query(
        """
        WITH usage AS (
            SELECT
                subscriber_id,
                any(subscriber_name) AS subscriber_name,
                any(plan_mbps) AS plan_mbps,
                sum(bytes) AS total_bytes,
                uniqExact(toStartOfHour(event_time)) AS active_hours,
                uniqExact(destination_ip) AS unique_destinations,
                count() AS flow_count,
                (sum(bytes) * 8.0 / greatest(1, dateDiff('second', min(event_time), max(end_time))) / 1000000) AS avg_mbps
            FROM flows
            WHERE event_time >= now() - toIntervalHour({hours:UInt32})
              AND subscriber_id > 0
            GROUP BY subscriber_id
        )
        SELECT
            *,
            least(100,
                if(plan_mbps > 0, least(40, avg_mbps / plan_mbps * 40), 0) +
                least(25, active_hours / ({hours:UInt32} * 0.8) * 25) +
                least(20, log10(unique_destinations + 1) * 5) +
                least(15, log10(flow_count + 1) * 3)
            ) AS risk_score
        FROM usage
        ORDER BY risk_score DESC
        LIMIT {limit:UInt32}
        """,
        parameters={"hours": hours, "limit": limit},
    )
    return {
        "hours": hours,
        "notice": "Risk is an operational indicator, not proof of resale.",
        "items": [dict(zip(result.column_names, row)) for row in result.result_rows],
    }
