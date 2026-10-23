"""Roles y acceso temporal.

Solo hay dos roles: **admin** (la persona que administra el sistema, sin vencimiento) e **invitado** (un trabajador al que el admin
le da acceso limitado y temporal). El acceso del invitado dura 24 horas desde que el admin lo da o lo reactiva; al vencer, sus
credenciales se conservan pero no puede entrar hasta que el admin lo reactive. Antes existía el rol «operador»: se trata como invitado."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from utils import clock

ADMIN = "admin"
GUEST = "invitado"
GUEST_HOURS = 24
# Lo que ve un invitado: solo consulta (nada que cree, edite o borre datos). Para darle más pantallas, agrégalas aquí cuando sean de solo lectura.
GUEST_ROUTES = ("Dashboard", "Manual de Usuario", "Sistema")
ROLE_LABELS = {ADMIN: "Administrador", GUEST: "Invitado"}


def normalize_role(role: str | None) -> str:
    """El rol guardado → admin o invitado (el antiguo «operador» y cualquier valor desconocido son invitado)."""
    return ADMIN if role == ADMIN else GUEST


def is_admin(user: dict | None) -> bool:
    return bool(user) and normalize_role(user.get("role")) == ADMIN


def new_expiry(now: datetime | None = None, hours: int = GUEST_HOURS) -> str:
    """Cuándo vence un acceso dado ahora, como texto UTC para guardar en la base."""
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return (moment + timedelta(hours=hours)).isoformat(timespec="seconds")


def expires_at(user: dict | None) -> datetime | None:
    return clock.parse((user or {}).get("access_until"))


def remaining(user: dict | None, now: datetime | None = None) -> timedelta | None:
    """Cuánto le queda de acceso a un invitado (None si no tiene fecha; negativo si ya venció). El admin no vence."""
    until = expires_at(user)
    if until is None:
        return None
    return until - (now or datetime.now(timezone.utc))


def allowed(user: dict | None, now: datetime | None = None) -> bool:
    """¿Puede entrar ahora? El admin siempre; el invitado solo con el acceso activo y sin vencer."""
    if not user or not user.get("active", True):
        return False
    if is_admin(user):
        return True
    left = remaining(user, now)
    return left is not None and left > timedelta(0)


def routes_for(user: dict | None, all_routes: list[str]) -> list[str]:
    """Pantallas del menú que le corresponden a este usuario."""
    return list(all_routes) if is_admin(user) else [r for r in all_routes if r in GUEST_ROUTES]


def _span(delta: timedelta) -> str:
    minutes = max(int(delta.total_seconds() // 60), 0)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min" if hours else f"{minutes} min"


def describe(user: dict | None, now: datetime | None = None) -> str:
    """El estado del acceso en una frase: «Acceso hasta 2026-10-23 15:30 (quedan 5 h 20 min)», «Acceso vencido…» o «Sin acceso activo»."""
    if is_admin(user):
        return "Administrador: sin vencimiento"
    left = remaining(user, now)
    if left is None:
        return "Sin acceso activo: el administrador debe reactivarlo"
    until = clock.local((user or {}).get("access_until"))
    if left > timedelta(0):
        return f"Acceso hasta {until} (quedan {_span(left)})"
    return f"Acceso vencido el {until}: el administrador debe reactivarlo"
