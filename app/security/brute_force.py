"""Anti-brute force: bloqueo de cuenta por intentos fallidos de login."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase

MAX_ATTEMPTS    = 5
LOCKOUT_MINUTES = 30
TTL_HOURS       = 1   # Los registros se limpian con indice TTL en MongoDB


class AccountLockedError(Exception):
    def __init__(self, locked_until: datetime) -> None:
        self.locked_until = locked_until
        remaining = int((locked_until - datetime.now(UTC)).total_seconds() / 60) + 1
        super().__init__(f"Cuenta bloqueada. Intenta en {remaining} minutos.")


async def is_locked(db: "AsyncIOMotorDatabase", identifier: str) -> bool:
    """Retorna True si el identificador esta bloqueado ahora mismo."""
    record = await db.login_attempts.find_one({"id": identifier})
    if not record:
        return False
    locked_until = record.get("locked_until")
    if locked_until and datetime.now(UTC) < locked_until:
        return True
    return False


async def record_attempt(
    db: "AsyncIOMotorDatabase",
    identifier: str,
    success: bool,
) -> None:
    """Registra un intento de autenticacion.

    - Si es exitoso: elimina el registro de intentos.
    - Si falla: incrementa el contador; bloquea si supera MAX_ATTEMPTS.
    """
    if success:
        await db.login_attempts.delete_one({"id": identifier})
        return

    now = db.client.get_io_loop  # dummy — solo para calcular timestamps
    now = datetime.now(UTC)
    record = await db.login_attempts.find_one({"id": identifier})
    count = (record.get("count", 0) if record else 0) + 1

    update: dict = {
        "id":           identifier,
        "count":        count,
        "last_attempt": now,
    }

    if count >= MAX_ATTEMPTS:
        update["locked_until"] = now + timedelta(minutes=LOCKOUT_MINUTES)

    await db.login_attempts.replace_one(
        {"id": identifier},
        update,
        upsert=True,
    )

    if count >= MAX_ATTEMPTS:
        raise AccountLockedError(update["locked_until"])


async def ensure_ttl_index(db: "AsyncIOMotorDatabase") -> None:
    """Crea el indice TTL que limpia registros viejos automaticamente."""
    await db.login_attempts.create_index(
        "last_attempt",
        expireAfterSeconds=TTL_HOURS * 3600,
        background=True,
    )
