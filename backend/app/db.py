from functools import lru_cache

import clickhouse_connect

from .config import get_settings


@lru_cache
def get_clickhouse():
    settings = get_settings()
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        database=settings.clickhouse_db,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
    )
