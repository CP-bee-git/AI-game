import json
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator, MutableMapping
from typing import Generator
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.services.session import current_session


def _json_default(value: Any) -> str | dict:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (UUID, Path, date, datetime)):
        return str(value)
    raise TypeError(f"Cannot store {type(value).__name__} in application state")


class SQLiteMap(MutableMapping[str, Any]):
    """Small durable map for the single-server MVP; upgrade to a repository when multi-instance."""

    def __init__(self, path: Path, namespace: str) -> None:
        self.path = path
        self.namespace = namespace
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._session() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS app_state (namespace TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(namespace,key))")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("PRAGMA busy_timeout=15000")
        self.path.chmod(0o600)
        return db

    @contextmanager
    def _session(self) -> Generator[sqlite3.Connection, None, None]:
        db = self._connect()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _key(key: Any) -> str:
        return str(key)

    @property
    def _scope(self) -> str:
        return f"{self.namespace}:{current_session.get()}"

    def __getitem__(self, key: Any) -> Any:
        with self._session() as db:
            row = db.execute("SELECT value FROM app_state WHERE namespace=? AND key=?", (self._scope, self._key(key))).fetchone()
        if row is None:
            raise KeyError(key)
        return json.loads(row[0])

    def __setitem__(self, key: Any, value: Any) -> None:
        encoded = json.dumps(value, ensure_ascii=False, default=_json_default)
        with self._session() as db:
            db.execute("INSERT INTO app_state(namespace,key,value) VALUES (?,?,?) ON CONFLICT(namespace,key) DO UPDATE SET value=excluded.value", (self._scope, self._key(key), encoded))

    def __delitem__(self, key: Any) -> None:
        with self._session() as db:
            cursor = db.execute("DELETE FROM app_state WHERE namespace=? AND key=?", (self._scope, self._key(key)))
            if cursor.rowcount == 0:
                raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        with self._session() as db:
            keys = [row[0] for row in db.execute("SELECT key FROM app_state WHERE namespace=?", (self._scope,))]
        return iter(keys)

    def __len__(self) -> int:
        with self._session() as db:
            return db.execute("SELECT count(*) FROM app_state WHERE namespace=?", (self._scope,)).fetchone()[0]

    def clear(self) -> None:
        with self._session() as db:
            db.execute("DELETE FROM app_state WHERE namespace=?", (self._scope,))
