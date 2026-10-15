-- =============================================================================
-- Parche 039 — Desactivar RLS en TODAS las tablas de la app
--
-- Por qué: la app se conecta con la clave pública de Supabase. Si una tabla tiene
-- Row Level Security (RLS) activo y ninguna política, Supabase rechaza toda
-- escritura con el error 42501 («new row violates row-level security policy»).
-- schema.sql no desactivaba RLS en `workers` (ni en otras tablas base), por eso al
-- registrar un trabajador salía «No se pudo registrar al trabajador».
--
-- Es idempotente (se puede correr varias veces) y solo toca las tablas de la app.
-- La seguridad (RLS con políticas) queda para una etapa posterior.
-- =============================================================================

do $$
declare
  t text;
begin
  foreach t in array array[
    'materials', 'suppliers', 'supplier_materials', 'users',
    'work_groups', 'project_sites', 'workers',
    'purchase_orders', 'purchase_order_items',
    'stock_movements', 'site_budgets', 'attendance', 'audit_log',
    'price_history', 'dispatch_vouchers'
  ]
  loop
    if to_regclass('public.' || t) is not null then
      execute format('alter table public.%I disable row level security', t);
    end if;
  end loop;
end $$;

notify pgrst, 'reload schema';
