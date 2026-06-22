import json
import os
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict

from app.models.schemas import ShareCreateRequest, ShareSnapshot


class JsonShareStore:
    """Small JSON-backed store for public share snapshots."""

    def __init__(self, storage_path: Path | None = None):
        default_path = Path(__file__).resolve().parents[1] / "data" / "shares.json"
        self.storage_path = storage_path or Path(os.getenv("SHARE_STORE_PATH", str(default_path)))
        self._lock = threading.Lock()

    def create_share(self, payload: ShareCreateRequest) -> ShareSnapshot:
        with self._lock:
            shares = self._read_all()
            share_id = self._new_share_id(shares)
            snapshot = ShareSnapshot(
                id=share_id,
                title=payload.title,
                content=payload.content,
                hashtags=payload.hashtags,
                image_url=payload.image_url,
                message=payload.message,
                created_at=datetime.now(UTC),
            )
            shares[share_id] = snapshot.model_dump(mode="json")
            self._write_all(shares)
            return snapshot

    def get_share(self, share_id: str) -> ShareSnapshot | None:
        with self._lock:
            raw_share = self._read_all().get(share_id)
        if not raw_share:
            return None
        return ShareSnapshot.model_validate(raw_share)

    def _read_all(self) -> Dict[str, dict]:
        if not self.storage_path.exists():
            return {}
        try:
            with self.storage_path.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def _write_all(self, shares: Dict[str, dict]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("w", encoding="utf-8") as fp:
            json.dump(shares, fp, ensure_ascii=False, indent=2)

    @staticmethod
    def _new_share_id(existing_shares: Dict[str, dict]) -> str:
        while True:
            share_id = secrets.token_urlsafe(8)
            if share_id not in existing_shares:
                return share_id


share_store = JsonShareStore()
