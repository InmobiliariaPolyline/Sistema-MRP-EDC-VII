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
-- Qué hace: activa RLS en todas las tablas SIN políticas y retira todos los permisos a los
-- roles `anon` y `authenticated` (los de la clave pública). La clave de servicio salta RLS,
-- así que la app sigue funcionando; quien solo tenga la clave pública ya no ve nada.
-- Es idempotente. Se verifica con: python scripts/check_security.py
-- =============================================================================

do $$
declare
  t text;
begin
  foreach t in array array[
    'materials', 'suppliers', 'supplier_materials', 'users',
    'work_groups', 'project_sites', 'workers',
    'purchase_orders', 'purchase_order_items',
    'dispatch_vouchers', 'stock_movements', 'site_budgets', 'attendance', 'audit_log', 'price_history'
  ]
  loop
    if to_regclass('public.' || t) is not null then
      execute format('alter table public.%I enable row level security', t);
      execute format('revoke all on table public.%I from anon, authenticated', t);
    end if;
  end loop;
end $$;

-- La vista de stock se ejecutaba con los permisos de su dueño (saltaba RLS): que use los del consultante.
do $$
begin
  if to_regclass('public.stock_levels') is not null then
    execute 'alter view public.stock_levels set (security_invoker = true)';
    execute 'revoke all on public.stock_levels from anon, authenticated';
  end if;
  if to_regclass('public.voucher_seq') is not null then
    execute 'revoke all on sequence public.voucher_seq from anon, authenticated';
  end if;
end $$;

-- Las funciones se pueden llamar por rpc: solo la clave de servicio.
revoke all on function public.receive_order(uuid, jsonb, text) from public, anon, authenticated;
revoke all on function public.create_dispatch(uuid, uuid, text, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.receive_order(uuid, jsonb, text) to service_role;
grant execute on function public.create_dispatch(uuid, uuid, text, text, text, jsonb) to service_role;

notify pgrst, 'reload schema';
