"""Cliente Motor compartido (misma DB que core/state/mongo.py)."""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import Settings, get_settings

_client: AsyncIOMotorClient | None = None


class Collections:
    EXECUTIONS = "executions"
    PIPELINE_RUNS = "pipeline_runs"
    AGENT_MEMORY = "agent_memory"


async def connect_mongo(settings: Settings) -> AsyncIOMotorDatabase:
    global _client
    _client = AsyncIOMotorClient(settings.mongo_uri)
    await _client.admin.command("ping")
    return _client[settings.mongo_db]


def get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("Mongo no inicializado")
    return _client[get_settings().mongo_db]


async def close_mongo() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def mongo_ping() -> bool:
    try:
        if _client is None:
            return False
        await _client.admin.command("ping")
        return True
    except Exception:
        return False
