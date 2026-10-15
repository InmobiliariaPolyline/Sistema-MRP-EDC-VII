-- =============================================================================
-- EMERGENCIA — volver a abrir la base (deshace 040_cerrar_base.sql)
--
-- Úsalo solo si cerraste la base antes de configurar SUPABASE_SERVICE_KEY en la app y esta
-- dejó de funcionar. Devuelve el estado de antes: RLS desactivado y permisos para la clave
-- pública. Después, configura la clave de servicio y vuelve a cerrar.
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
      execute format('alter table public.%I disable row level security', t);
      execute format('grant select, insert, update, delete on table public.%I to anon, authenticated', t);
    end if;
  end loop;
end $$;

grant select on public.stock_levels to anon, authenticated;
grant usage, select on sequence public.voucher_seq to anon, authenticated;
grant execute on function public.receive_order(uuid, jsonb, text) to anon, authenticated;
grant execute on function public.create_dispatch(uuid, uuid, text, text, text, jsonb) to anon, authenticated;

notify pgrst, 'reload schema';
