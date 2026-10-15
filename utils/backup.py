"""Respaldo y restauración de toda la base (todas las tablas de la app).

El respaldo es un ZIP con un CSV por tabla (UTF-8, para abrir también en Excel) y un
`manifest.json` con la fecha, las tablas y cuántas filas tiene cada una. Si se indica una
contraseña, el ZIP se cifra con AES-256 (recomendado: incluye los hashes de las cuentas).

La restauración (`rows_from_zip` + `scripts/restore_backup.py`) vuelve a cargar las tablas en
orden de dependencia con `upsert` por `id`, así que se puede repetir sin duplicar datos."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime

import pandas as pd

try:  # cifrado AES opcional
    import pyzipper
except Exception:  # pragma: no cover - sin la librería solo se puede respaldar sin contraseña
    pyzipper = None

MANIFEST = "manifest.json"


def to_zip(tables: dict[str, pd.DataFrame], password: str | None = None, app_version: str = "") -> bytes:
    """ZIP con un CSV por tabla y el manifiesto. Con `password`, cifrado AES-256."""
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "app_version": app_version,
        "encrypted": bool(password),
        "tables": {name: int(len(df)) for name, df in tables.items()},
    }
    buffer = io.BytesIO()
    if password:
        if pyzipper is None:
            raise RuntimeError("Falta la librería pyzipper para cifrar el respaldo (pip install pyzipper).")
        archive = pyzipper.AESZipFile(buffer, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES)
        archive.setpassword(password.encode("utf-8"))
    else:
        archive = zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED)
    with archive:
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
        for name, df in tables.items():
            archive.writestr(f"{name}.csv", df.to_csv(index=False).encode("utf-8-sig"))
    return buffer.getvalue()


def _open(data: bytes, password: str | None):
    if password:
        if pyzipper is None:
            raise RuntimeError("Falta la librería pyzipper para abrir respaldos cifrados.")
        archive = pyzipper.AESZipFile(io.BytesIO(data))
        archive.setpassword(password.encode("utf-8"))
        return archive
    return zipfile.ZipFile(io.BytesIO(data))


def rows_from_zip(data: bytes, password: str | None = None) -> tuple[dict, dict[str, list[dict]]]:
    """Lee un respaldo. Devuelve (manifiesto, {tabla: [filas]}) con los vacíos como None y todo lo
    demás como texto (PostgREST convierte el texto al tipo de cada columna)."""
    with _open(data, password) as archive:
        manifest = json.loads(archive.read(MANIFEST).decode("utf-8"))
        tables: dict[str, list[dict]] = {}
        for name in manifest["tables"]:
            raw = archive.read(f"{name}.csv")
            if not raw.decode("utf-8-sig").strip():  # tabla vacía: el CSV no tiene ni encabezados (solo la marca BOM)
                tables[name] = []
                continue
            frame = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, encoding="utf-8-sig")
            rows = []
            for record in frame.to_dict("records"):
                rows.append({k: (None if v == "" else v) for k, v in record.items()})
            tables[name] = rows
    return manifest, tables
