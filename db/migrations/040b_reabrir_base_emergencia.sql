-- =============================================================================
-- EMERGENCIA — volver a abrir la base (deshace 040_cerrar_base.sql)
--
-- Úsalo solo si cerraste la base antes de configurar SUPABASE_SERVICE_KEY en la app y esta
-- dejó de funcionar. Devuelve el estado de antes: RLS desactivado y permisos para la clave
-- pública, en todas las tablas de la app. Después, configura la clave de servicio y vuelve a cerrar.
-- =============================================================================

do $$
declare
  r record;
begin
  for r in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I disable row level security', r.tablename);
    execute format('grant select, insert, update, delete on table public.%I to anon, authenticated', r.tablename);
  end loop;

  for r in select viewname from pg_views where schemaname = 'public' loop
    execute format('grant select on public.%I to anon, authenticated', r.viewname);
  end loop;

  for r in select sequencename from pg_sequences where schemaname = 'public' loop
    execute format('grant usage, select on sequence public.%I to anon, authenticated', r.sequencename);
  end loop;

  for r in
    select p.oid::regprocedure as sig
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname in ('receive_order', 'create_dispatch')
  loop
    execute format('grant execute on function %s to anon, authenticated', r.sig);
  end loop;
end $$;

notify pgrst, 'reload schema';
