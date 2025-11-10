from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from pymongo import MongoClient, ASCENDING, DESCENDING  # type: ignore
    from pymongo.collection import Collection  # type: ignore
    HAS_MONGO = True
except Exception:  # pragma: no cover - allow code to import without pymongo
    MongoClient = object  # type: ignore
    Collection = object  # type: ignore
    HAS_MONGO = False


_client: Optional[MongoClient] = None  # type: ignore
_episodes: Optional[Collection] = None  # type: ignore
_messages: Optional[Collection] = None  # type: ignore


def _get_env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v else default


def _ensure_client() -> None:
    """
    Initialize client/collections and indexes if pymongo is available.
    No-op if Mongo is unavailable.
    """
    global _client, _episodes, _messages
    if not HAS_MONGO:
        return
    if _client is not None:
        return

    uri = _get_env("MONGODB_URI", "mongodb://localhost:27017")
    db_name = _get_env("MONGO_DB_NAME", "hf_agent")
    episodes_col = _get_env("MONGO_EPISODES_COLLECTION", "episodes")
    messages_col = _get_env("MONGO_MESSAGES_COLLECTION", "messages")

    _client = MongoClient(uri, serverSelectionTimeoutMS=2000)  # quick fail if not reachable
    db = _client[db_name]
    _episodes = db[episodes_col]
    _messages = db[messages_col]

    # Indexes
    _episodes.create_index([("episode_id", ASCENDING)], unique=True)
    _episodes.create_index([("patient_id", ASCENDING), ("created_at", DESCENDING)])
    _episodes.create_index([("status", ASCENDING)])
    _messages.create_index([("episode_id", ASCENDING), ("ts", DESCENDING)])


def save_episode(payload: Dict[str, Any]) -> None:
    """
    Upsert an episode snapshot document.
    Expected keys (minimal): episode_id, state_version, patient_state, risk_level, risk_flags, status
    Optional: patient_id, created_at/updated_at (auto-filled if absent)
    """
    if not HAS_MONGO:
        return  # silently no-op if mongo not installed
    _ensure_client()
    assert _episodes is not None

    doc = dict(payload)
    now = datetime.now(timezone.utc)
    doc.setdefault("created_at", now)
    doc["updated_at"] = now

    ep_id = doc.get("episode_id")
    if not ep_id:
        raise ValueError("save_episode requires episode_id")

    _episodes.update_one({"episode_id": ep_id}, {"$set": doc}, upsert=True)


def append_message(episode_id: str, message: Dict[str, Any]) -> None:
    """
    Append a conversation message to messages collection.
    Required: episode_id; message should contain role/content; ts auto-added if missing.
    """
    if not HAS_MONGO:
        return
    _ensure_client()
    assert _messages is not None

    msg = dict(message)
    msg.setdefault("ts", datetime.now(timezone.utc))
    msg["episode_id"] = episode_id
    _messages.insert_one(msg)


