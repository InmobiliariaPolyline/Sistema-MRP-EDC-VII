-- =============================================================================
-- Parche 041 — Cerrar la base: que la clave pública ya no pueda leer ni escribir
--
-- ⚠️ ORDEN IMPORTANTE — leer antes de ejecutar:
--   1. En Supabase → Project Settings → API copia la clave «service_role» (secreta).
--   2. Guárdala en la app como SUPABASE_SERVICE_KEY (Streamlit Cloud → Manage app →
--      Settings → Secrets, y en tu .env local). La app la usa en cuanto existe.
--   3. Reinicia la app y comprueba que funciona.
--   4. SOLO ENTONCES ejecuta este script.
-- Si lo ejecutas antes del paso 2, la app dejará de poder leer y escribir (se arregla
-- corriendo db/migrations/040b_reabrir_base_emergencia.sql).
--
-- Qué hace: activa RLS en TODAS las tablas de la app SIN políticas y retira todos los permisos
-- a los roles `anon` y `authenticated` (los de la clave pública). La clave de servicio salta RLS,
-- así que la app sigue funcionando; quien solo tenga la clave pública ya no ve nada.
-- Es idempotente y recorre todas las tablas, vistas, secuencias y funciones de la app que existan
-- (también las de parches posteriores). Se verifica con: python scripts/check_security.py
-- =============================================================================

do $$
declare
  r record;
begin
  -- Tablas
  for r in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', r.tablename);
    execute format('revoke all on table public.%I from anon, authenticated', r.tablename);
  end loop;

  -- Vistas: que usen los permisos de quien consulta (no los de su dueño) y sin acceso público
  for r in select viewname from pg_views where schemaname = 'public' loop
    execute format('alter view public.%I set (security_invoker = true)', r.viewname);
    execute format('revoke all on public.%I from anon, authenticated', r.viewname);
  end loop;

  -- Secuencias
  for r in select sequencename from pg_sequences where schemaname = 'public' loop
    execute format('revoke all on sequence public.%I from anon, authenticated', r.sequencename);
  end loop;

  -- Funciones que la app llama por rpc: solo la clave de servicio
  for r in
    select p.oid::regprocedure as sig
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname in ('receive_order', 'create_dispatch')
  loop
    execute format('revoke all on function %s from public, anon, authenticated', r.sig);
    execute format('grant execute on function %s to service_role', r.sig);
  end loop;
end $$;

notify pgrst, 'reload schema';
