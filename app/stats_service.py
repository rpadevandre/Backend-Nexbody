"""Agregaciones sobre las colecciones de masaas (MongoDB)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import Collections


async def count_executions(db: AsyncIOMotorDatabase) -> int:
    return await db[Collections.EXECUTIONS].count_documents({})


async def count_pipeline_runs(db: AsyncIOMotorDatabase, since: datetime | None = None) -> int:
    filt: dict[str, Any] = {}
    if since is not None:
        filt["finished_at"] = {"$gte": since}
    return await db[Collections.PIPELINE_RUNS].count_documents(filt)


async def count_agent_memory(db: AsyncIOMotorDatabase) -> int:
    return await db[Collections.AGENT_MEMORY].count_documents({})


async def pipeline_success_ratio(
    db: AsyncIOMotorDatabase,
    since: datetime,
) -> tuple[int, int, float]:
    coll = db[Collections.PIPELINE_RUNS]
    filt = {"finished_at": {"$gte": since}}
    total = await coll.count_documents(filt)
    ok = await coll.count_documents({**filt, "success": True})
    rate = (ok / total) if total else 0.0
    return total, ok, rate


async def weekly_success_series(db: AsyncIOMotorDatabase, weeks: int = 4) -> list[dict[str, Any]]:
    """Últimas N semanas calendario (UTC): fracción de pipelines exitosos."""
    coll = db[Collections.PIPELINE_RUNS]
    now = datetime.now(UTC)
    out: list[dict[str, Any]] = []

    for i in range(weeks):
        start = now - timedelta(weeks=(weeks - i))
        end = now - timedelta(weeks=(weeks - i - 1))
        filt = {"finished_at": {"$gte": start, "$lt": end}}
        total = await coll.count_documents(filt)
        ok = await coll.count_documents({**filt, "success": True})
        adherence = (ok / total) if total else 0.0
        out.append({"week": f"S{i + 1}", "adherence": adherence, "runs": total})

    return out


async def sum_tokens(db: AsyncIOMotorDatabase, since: datetime | None = None) -> int:
    coll = db[Collections.PIPELINE_RUNS]
    match: dict[str, Any] = {}
    if since is not None:
        match["finished_at"] = {"$gte": since}

    pipeline = []
    if match:
        pipeline.append({"$match": match})
    pipeline.append({"$group": {"_id": None, "t": {"$sum": "$tokens_spent"}}})

    cur = coll.aggregate(pipeline)
    doc = await cur.to_list(length=1)
    if not doc:
        return 0
    return int(doc[0].get("t") or 0)


async def latest_execution_summary(db: AsyncIOMotorDatabase) -> dict[str, Any] | None:
    doc = await db[Collections.EXECUTIONS].find_one(
        {},
        sort=[("updated_at", -1)],
        projection={
            "execution_id": 1,
            "goal": 1,
            "mode": 1,
            "workspace_path": 1,
            "updated_at": 1,
            "created_at": 1,
            "blockers": 1,
        },
    )
    if not doc:
        return None
    doc.pop("_id", None)
    return doc


async def compute_platform_overview(db: AsyncIOMotorDatabase) -> dict[str, Any]:
    """Payload para `/v1/metrics/overview` desde colecciones masaas."""
    since = datetime.now(UTC) - timedelta(days=28)
    exec_total = await count_executions(db)
    pr_total = await count_pipeline_runs(db)
    pr_window_total, pr_ok, success_rate = await pipeline_success_ratio(db, since)
    mem_total = await count_agent_memory(db)
    tokens_window = await sum_tokens(db, since)
    series_raw = await weekly_success_series(db, weeks=4)

    return {
        "source": "mongodb",
        "range": "28d",
        "adherence_rate": round(success_rate, 4),
        "series": [{"week": s["week"], "adherence": s["adherence"]} for s in series_raw],
        "active_plans": exec_total,
        "workouts_logged": pr_total,
        "meals_tracked": mem_total,
        "pipeline_runs_in_window": pr_window_total,
        "pipeline_runs_success_in_window": pr_ok,
        "tokens_spent_window": tokens_window,
        "series_detail": series_raw,
    }


async def recent_executions(db: AsyncIOMotorDatabase, limit: int = 15) -> list[dict[str, Any]]:
    cursor = (
        db[Collections.EXECUTIONS]
        .find(
            {},
            projection={
                "execution_id": 1,
                "goal": 1,
                "mode": 1,
                "workspace_path": 1,
                "updated_at": 1,
                "created_at": 1,
            },
        )
        .sort([("updated_at", -1)])
        .limit(limit)
    )
    rows = []
    async for doc in cursor:
        doc.pop("_id", None)
        rows.append(doc)
    return rows
