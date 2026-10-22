-- =============================================================================
-- Pedido con varios proveedores
--
-- Cómo usarlo: copia TODO este archivo en el SQL Editor de Supabase y pulsa Run.
-- Es idempotente y no toca datos existentes (solo agrega una columna).
--
--   purchase_orders.batch_code   código del pedido (PD-0001) que une las órdenes creadas juntas cuando un pedido junta materiales de
--                                varios proveedores. Cada proveedor conserva su propia orden (su PDF, IGV, pago y recepción);
--                                el pedido las muestra como una sola ficha con el total general. Las órdenes de un solo proveedor lo dejan vacío.
-- =============================================================================

alter table purchase_orders add column if not exists batch_code text;
create index if not exists purchase_orders_batch_code_idx on purchase_orders (batch_code);
