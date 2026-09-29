"""Fachada de acceso a datos: usa Supabase si hay credenciales configuradas
(SUPABASE_URL/SUPABASE_KEY); si no, usa un SQLite local (db/local.db) para
poder ver y probar la interfaz sin depender de una cuenta de Supabase.

Ambos módulos (supabase_repository y local_repository) exponen exactamente
las mismas funciones, así que las páginas de la app llaman siempre a
`repository.xxx(...)` sin saber cuál de los dos está detrás."""
from db.client import has_supabase_config

if has_supabase_config():
    from db.supabase_repository import *  # noqa: F401,F403
    USING_LOCAL = False
else:
    from db.local_repository import *  # noqa: F401,F403
    USING_LOCAL = True
