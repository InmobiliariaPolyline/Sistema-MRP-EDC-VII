-- =============================================================================
-- Parche 036 — Despacho a obra, stock mínimo, historial de precios e integridad
--
-- Cómo usarlo: copia TODO este archivo en el SQL Editor de Supabase y pulsa Run.
-- Es idempotente: se puede ejecutar más de una vez sin duplicar ni romper nada.
-- No toca datos existentes (solo agrega columnas, tablas, vista, funciones y
-- triggers). Los cambios de seguridad (RLS, intentos de login) NO van aquí.
--
-- Qué agrega:
--   1. materials.min_stock                    stock mínimo por material
--   2. supplier_materials.price_updated_at    fecha del último cambio de precio
--      price_history + trigger                historial automático de precios
--   3. dispatch_vouchers + movimientos        vales de salida (despacho a obra)
--      stock_movements.voucher_id/movement_type
--   4. stock_levels (vista)                   stock actual por material, sin límites
--   5. Funciones receive_order y create_dispatch   recepción y despacho todo-o-nada
--   6. Triggers de integridad                 no borrar órdenes con recepciones,
--                                             no sacar más stock del que hay
--   7. Índices, permisos y RLS desactivado para las tablas nuevas
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Stock mínimo por material
-- -----------------------------------------------------------------------------
alter table materials add column if not exists min_stock numeric not null default 0;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'materials_min_stock_nonneg') then
    alter table materials add constraint materials_min_stock_nonneg check (min_stock >= 0);
  end if;
end $$;


-- -----------------------------------------------------------------------------
-- 2. Precios: fecha de actualización e historial
-- -----------------------------------------------------------------------------
alter table supplier_materials add column if not exists price_updated_at timestamptz;

create table if not exists price_history (
  id uuid primary key default gen_random_uuid(),
  supplier_id uuid not null references suppliers(id) on delete cascade,
  material_id uuid not null references materials(id) on delete cascade,
  price numeric,
  source text not null default 'manual',          -- manual | importacion
  recorded_at timestamptz not null default now()
);
create index if not exists idx_price_history_material on price_history(material_id, recorded_at desc);
create index if not exists idx_price_history_supplier on price_history(supplier_id, recorded_at desc);

-- Cada vez que cambia el precio de un material de un proveedor se anota solo.
create or replace function log_price_change() returns trigger
language plpgsql as $$
begin
  if (tg_op = 'INSERT' and new.price is not null)
     or (tg_op = 'UPDATE' and new.price is distinct from old.price) then
    new.price_updated_at := now();
    insert into price_history (supplier_id, material_id, price)
    values (new.supplier_id, new.material_id, new.price);
  end if;
  return new;
end $$;

drop trigger if exists trg_log_price_change on supplier_materials;
create trigger trg_log_price_change
  before insert or update of price on supplier_materials
  for each row execute function log_price_change();


-- -----------------------------------------------------------------------------
-- 3. Vales de salida (despacho a obra)
-- -----------------------------------------------------------------------------
create sequence if not exists voucher_seq;

create table if not exists dispatch_vouchers (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,                       -- VS-0001
  project_site_id uuid references project_sites(id) on delete set null,
  site_name text not null,                         -- copia: se conserva si la obra se borra
  worker_id uuid references workers(id) on delete set null,
  requested_by text,                               -- quién lo pidió (nombre del obrero)
  note text,
  actor text,                                      -- quién lo registró en el sistema
  created_at timestamptz not null default now()
);
create index if not exists idx_vouchers_site on dispatch_vouchers(project_site_id);
create index if not exists idx_vouchers_created on dispatch_vouchers(created_at desc);

alter table stock_movements add column if not exists voucher_id uuid references dispatch_vouchers(id) on delete set null;
alter table stock_movements add column if not exists movement_type text;   -- recepcion | despacho | entrada_manual | merma | ajuste
create index if not exists idx_movements_voucher on stock_movements(voucher_id);

-- Completa el tipo de los movimientos que ya existían.
update stock_movements set movement_type = 'recepcion'
  where movement_type is null and kind = 'entrada' and order_id is not null;
update stock_movements set movement_type = 'entrada_manual'
  where movement_type is null and kind = 'entrada';
update stock_movements set movement_type = 'despacho'
  where movement_type is null and kind = 'salida' and project_site_id is not null;
update stock_movements set movement_type = 'merma'
  where movement_type is null and kind = 'salida';

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'stock_movements_kind_chk') then
    alter table stock_movements add constraint stock_movements_kind_chk check (kind in ('entrada', 'salida'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'stock_movements_qty_chk') then
    alter table stock_movements add constraint stock_movements_qty_chk check (quantity > 0) not valid;
  end if;
end $$;


-- -----------------------------------------------------------------------------
-- 4. Stock actual por material (vista): entradas - salidas, sin límite de filas
-- -----------------------------------------------------------------------------
create or replace view stock_levels as
select
  m.id as material_id,
  m.category,
  m.name as material_name,
  m.metric_label as unit,
  m.min_stock,
  coalesce(sum(case when s.kind = 'entrada' then s.quantity end), 0) as entradas,
  coalesce(sum(case when s.kind = 'salida' then s.quantity end), 0) as salidas,
  coalesce(sum(case when s.kind = 'entrada' then s.quantity when s.kind = 'salida' then -s.quantity end), 0) as stock
from materials m
left join stock_movements s on s.material_id = m.id
group by m.id, m.category, m.name, m.metric_label, m.min_stock;


-- -----------------------------------------------------------------------------
-- 5. Integridad: stock nunca negativo y no borrar órdenes con material recibido
-- -----------------------------------------------------------------------------
create or replace function check_stock_before_exit() returns trigger
language plpgsql as $$
declare v_stock numeric;
begin
  if new.kind = 'salida' then
    perform pg_advisory_xact_lock(hashtext(new.material_id::text));   -- evita carreras entre dos salidas
    select coalesce(sum(case when kind = 'entrada' then quantity else -quantity end), 0)
      into v_stock from stock_movements where material_id = new.material_id;
    if v_stock < new.quantity then
      raise exception 'Stock insuficiente: hay % y se intenta sacar %', v_stock, new.quantity
        using errcode = 'P0001';
    end if;
  end if;
  return new;
end $$;

drop trigger if exists trg_check_stock_before_exit on stock_movements;
create trigger trg_check_stock_before_exit
  before insert on stock_movements
  for each row execute function check_stock_before_exit();

create or replace function block_delete_received_order() returns trigger
language plpgsql as $$
begin
  if exists (select 1 from purchase_order_items where order_id = old.id and received_qty > 0) then
    raise exception 'La orden % ya recibió material: cancélala en lugar de eliminarla', old.code
      using errcode = 'P0001';
  end if;
  return old;
end $$;

drop trigger if exists trg_block_delete_received_order on purchase_orders;
create trigger trg_block_delete_received_order
  before delete on purchase_orders
  for each row execute function block_delete_received_order();


-- -----------------------------------------------------------------------------
-- 6. Funciones todo-o-nada (la app las llama con rpc; si no existen usa un
--    respaldo en Python, así que correr este script no es urgente)
-- -----------------------------------------------------------------------------

-- Recepción de una orden. p_receipts = {"<id de línea>": cantidad recibida ahora, ...}
-- Devuelve el nuevo estado de la orden: 'parcial' o 'recibida'.
create or replace function receive_order(p_order_id uuid, p_receipts jsonb, p_actor text default null)
returns text
language plpgsql as $$
declare
  v_code text;
  v_status text;
  r record;
  v_item record;
  v_qty numeric;
  v_pending int;
begin
  select code, status into v_code, v_status from purchase_orders where id = p_order_id for update;
  if v_code is null then
    raise exception 'La orden no existe';
  end if;
  if v_status = 'cancelada' then
    raise exception 'La orden % está cancelada y no puede recibir material', v_code;
  end if;

  for r in select key as item_id, value as qty from jsonb_each(p_receipts) loop
    v_qty := (r.qty #>> '{}')::numeric;
    continue when v_qty is null or v_qty <= 0;

    select id, material_id, quantity, received_qty into v_item
      from purchase_order_items where id = r.item_id::uuid and order_id = p_order_id for update;
    if v_item.id is null then
      raise exception 'La línea % no pertenece a la orden %', r.item_id, v_code;
    end if;
    if v_item.received_qty + v_qty > v_item.quantity then
      raise exception 'Se intenta recibir más de lo pedido en una línea de %', v_code;
    end if;

    update purchase_order_items set received_qty = received_qty + v_qty where id = v_item.id;
    if v_item.material_id is not null then
      insert into stock_movements (material_id, kind, quantity, note, order_id, actor, movement_type)
      values (v_item.material_id, 'entrada', v_qty, 'Recepción ' || v_code, p_order_id, p_actor, 'recepcion');
    end if;
  end loop;

  select count(*) into v_pending from purchase_order_items
    where order_id = p_order_id and received_qty < quantity;
  v_status := case when v_pending > 0 then 'parcial' else 'recibida' end;
  update purchase_orders set status = v_status, updated_at = now() where id = p_order_id;
  return v_status;
end $$;

-- Despacho de material a una obra con su vale de salida.
-- p_lines = [{"material_id": "...", "quantity": 5, "note": "..."}, ...]
-- Devuelve el código del vale (VS-0001). Si algún material no alcanza, no se
-- registra nada (el trigger de stock lanza el error y se deshace todo).
create or replace function create_dispatch(
  p_site uuid, p_worker uuid, p_requested_by text, p_note text, p_actor text, p_lines jsonb
) returns text
language plpgsql as $$
declare
  v_code text;
  v_voucher uuid;
  v_site_name text;
  l jsonb;
begin
  select name into v_site_name from project_sites where id = p_site;
  if v_site_name is null then
    raise exception 'La obra no existe';
  end if;
  if p_lines is null or jsonb_array_length(p_lines) = 0 then
    raise exception 'El vale no tiene materiales';
  end if;

  v_code := 'VS-' || lpad(nextval('voucher_seq')::text, 4, '0');
  insert into dispatch_vouchers (code, project_site_id, site_name, worker_id, requested_by, note, actor)
  values (v_code, p_site, v_site_name, p_worker, nullif(trim(p_requested_by), ''), nullif(trim(p_note), ''), p_actor)
  returning id into v_voucher;

  for l in select * from jsonb_array_elements(p_lines) loop
    insert into stock_movements (material_id, project_site_id, kind, quantity, note, actor, voucher_id, movement_type)
    values (
      (l ->> 'material_id')::uuid, p_site, 'salida', (l ->> 'quantity')::numeric,
      coalesce(nullif(l ->> 'note', ''), 'Despacho ' || v_code), p_actor, v_voucher, 'despacho'
    );
  end loop;
  return v_code;
end $$;


-- -----------------------------------------------------------------------------
-- 7. Permisos y RLS (la app usa la clave pública: sin esto no puede leer/escribir)
-- -----------------------------------------------------------------------------
alter table price_history disable row level security;
alter table dispatch_vouchers disable row level security;

grant select, insert, update, delete on price_history, dispatch_vouchers to anon, authenticated;
grant select on stock_levels to anon, authenticated;
grant usage, select on sequence voucher_seq to anon, authenticated;
grant execute on function receive_order(uuid, jsonb, text) to anon, authenticated;
grant execute on function create_dispatch(uuid, uuid, text, text, text, jsonb) to anon, authenticated;

-- Hace que PostgREST (la API de Supabase) vea ya las funciones y la vista nuevas.
notify pgrst, 'reload schema';
