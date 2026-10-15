-- =============================================================================
-- Fase E — Rendimiento
--
-- Cómo usarlo: copia TODO este archivo en el SQL Editor de Supabase y pulsa Run.
-- Es idempotente y no toca datos (solo crea vistas e índices).
--
-- Antes la app traía TODOS los movimientos de stock y los sumaba en Python cada vez que se
-- abría una obra, un despacho o la sugerencia de compra. Ahora la base entrega ya sumado:
--
--   site_consumption   consumo neto por obra, material y etapa (despachado − devuelto)
--   dashboard_stats    los contadores del dashboard en una sola fila
--   índices            para las consultas más frecuentes
--
-- Si la base ya está cerrada (040_cerrar_base.sql), las vistas nuevas nacen cerradas.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Consumo neto por obra, material y etapa
--    Cuenta como lo hace la app (utils/consumption.py): los despachos suman, las devoluciones
--    desde la obra restan; recepciones, mermas, conteos y devoluciones a proveedor no cuentan.
-- -----------------------------------------------------------------------------
create or replace view site_consumption as
select
  c.project_site_id,
  c.material_id,
  c.stage,
  m.name as material_name,
  m.category,
  m.metric_label as unit,
  c.quantity
from (
  select
    s.project_site_id,
    s.material_id,
    coalesce(s.stage, '') as stage,
    sum(
      case
        when s.kind = 'salida' and coalesce(s.movement_type, '') <> 'devolucion_proveedor' then s.quantity
        when s.kind = 'entrada' and s.movement_type = 'devolucion' then -s.quantity
        else 0
      end
    ) as quantity
  from stock_movements s
  where s.project_site_id is not null
  group by s.project_site_id, s.material_id, coalesce(s.stage, '')
) c
join materials m on m.id = c.material_id
where c.quantity <> 0;


-- -----------------------------------------------------------------------------
-- 2. Contadores del dashboard en una fila
-- -----------------------------------------------------------------------------
create or replace view dashboard_stats as
select
  (select count(*) from materials) as materials,
  (select count(*) from suppliers) as suppliers,
  (select count(distinct supplier_id) from supplier_materials where available) as suppliers_with_available,
  (select count(*) from materials m
     where not exists (select 1 from supplier_materials sm where sm.material_id = m.id)) as materials_without_supplier,
  (select count(*) from purchase_orders where status in ('pendiente', 'enviada', 'parcial')) as orders_open,
  (select count(*) from stock_levels where stock > 0) as materials_in_stock,
  (select count(*) from stock_levels where min_stock > 0 and stock <= min_stock) as low_stock,
  (select count(*) from dispatch_vouchers
     where (created_at at time zone 'America/Lima') >= date_trunc('month', now() at time zone 'America/Lima')) as dispatches_month;


-- -----------------------------------------------------------------------------
-- 3. Índices para las consultas más frecuentes
-- -----------------------------------------------------------------------------
create index if not exists idx_movements_site_material on stock_movements(project_site_id, material_id);
create index if not exists idx_movements_material_created on stock_movements(material_id, created_at desc);
create index if not exists idx_movements_created on stock_movements(created_at desc);
create index if not exists idx_order_items_order on purchase_order_items(order_id);
create index if not exists idx_orders_status on purchase_orders(status);
create index if not exists idx_orders_created on purchase_orders(created_at desc);
create index if not exists idx_supplier_materials_material on supplier_materials(material_id);
create index if not exists idx_budgets_site on site_budgets(project_site_id);
create index if not exists idx_audit_created on audit_log(created_at desc);


-- -----------------------------------------------------------------------------
-- 4. Permisos: si la base ya está cerrada, las vistas nuevas nacen cerradas; si no, como el resto
-- -----------------------------------------------------------------------------
do $$
declare
  v text;
  closed boolean := coalesce((select relrowsecurity from pg_class where oid = 'public.materials'::regclass), false);
begin
  foreach v in array array['site_consumption', 'dashboard_stats']
  loop
    if closed then
      execute format('alter view public.%I set (security_invoker = true)', v);
      execute format('revoke all on public.%I from anon, authenticated', v);
    else
      execute format('grant select on public.%I to anon, authenticated', v);
    end if;
  end loop;
end $$;

notify pgrst, 'reload schema';
