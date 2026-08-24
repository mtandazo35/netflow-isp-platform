from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.db import get_clickhouse
from app.main import app


@dataclass
class FakeQueryResult:
    column_names: list[str]
    result_rows: list[tuple]


class FakeClickHouse:
    def __init__(self):
        self.insert_calls = []
        self.query_calls = []
        self.command_calls = []
        self.next_result = FakeQueryResult([], [])

    def command(self, query):
        self.command_calls.append(query)
        return 1

    def insert(self, table, rows, column_names):
        self.insert_calls.append((table, rows, column_names))

    def query(self, query, parameters=None):
        self.query_calls.append((query, parameters or {}))
        return self.next_result


@pytest.fixture
def fake_clickhouse():
    return FakeClickHouse()


@pytest.fixture
def client(fake_clickhouse):
    app.dependency_overrides[get_clickhouse] = lambda: fake_clickhouse
    with TestClient(app) as test_client:
        test_client.headers.update({"X-API-Key": "replace-with-a-long-random-value"})
        yield test_client
    app.dependency_overrides.clear()
