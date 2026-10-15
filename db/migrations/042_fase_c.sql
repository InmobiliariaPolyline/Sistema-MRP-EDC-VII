-- =============================================================================
-- Fase C — Compras y precios
--
-- Cómo usarlo: copia TODO este archivo en el SQL Editor de Supabase y pulsa Run.
-- Es idempotente y no toca datos existentes (solo agrega columnas).
--
--   suppliers.lead_time_days     plazo de entrega habitual del proveedor, en días
--   suppliers.min_order_amount   monto mínimo de compra del proveedor
--   purchase_orders.sent_at      cuándo se envió la orden al proveedor
-- =============================================================================

alter table suppliers add column if not exists lead_time_days integer;
alter table suppliers add column if not exists min_order_amount numeric;
alter table purchase_orders add column if not exists sent_at timestamptz;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'suppliers_lead_time_chk') then
    alter table suppliers add constraint suppliers_lead_time_chk check (lead_time_days is null or lead_time_days >= 0);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'suppliers_min_order_chk') then
    alter table suppliers add constraint suppliers_min_order_chk check (min_order_amount is null or min_order_amount >= 0);
  end if;
end $$;

notify pgrst, 'reload schema';
