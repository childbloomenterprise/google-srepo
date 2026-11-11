import json
import os
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class CaseStore(ABC):
    @abstractmethod
    def save(self, case: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, case_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def all(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class SqliteCaseStore(CaseStore):
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.getenv("CB_DB_PATH", "data/claimback.db"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS cases "
                "(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def save(self, case: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO cases (id, created_at, payload) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (case["id"], case["created_at"], json.dumps(case, ensure_ascii=False)),
            )

    def get(self, case_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def all(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM cases ORDER BY created_at DESC"
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]


class FirestoreCaseStore(CaseStore):
    def __init__(self):
        from google.cloud import firestore

        self.client = firestore.Client()
        self.collection = self.client.collection("claimback_cases")

    def save(self, case: dict[str, Any]) -> None:
        self.collection.document(case["id"]).set(case)

    def get(self, case_id: str) -> dict[str, Any] | None:
        snapshot = self.collection.document(case_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def all(self) -> list[dict[str, Any]]:
        return [snapshot.to_dict() for snapshot in self.collection.stream()]


def create_store() -> CaseStore:
    if os.getenv("CB_STORE", "sqlite").lower() == "firestore":
        return FirestoreCaseStore()
    return SqliteCaseStore()
