-- =============================================================================
-- Fase B — Operación real del almacén
--
-- Cómo usarlo: copia TODO este archivo en el SQL Editor de Supabase y pulsa Run.
-- Es idempotente: se puede ejecutar más de una vez. No borra ni cambia datos existentes
-- (solo agrega tablas, columnas, restricciones y reemplaza las dos funciones).
--
-- Qué agrega:
--   1. Toma de inventario    inventory_counts, inventory_count_lines, stock_movements.count_id
--      (las devoluciones de obra no necesitan columnas nuevas: son movimientos de tipo «devolucion»)
--   2. Condiciones de orden  purchase_orders.expected_date / currency / exchange_rate / tax_rate
--   3. Recepción contra documento   order_receipts (quién entregó, guía/factura, observaciones)
--                                   y la función receive_order con esos datos
--   4. Adjuntos              tabla attachments y el depósito privado «adjuntos» (Storage)
--   5. Presupuesto por etapas  site_budgets.stage, dispatch_vouchers.stage, stock_movements.stage
--                              y la función create_dispatch con la etapa
--   6. Unidades              materials.unit (lista cerrada) rellenada desde la métrica actual
--
-- Si la base ya está cerrada (040_cerrar_base.sql), lo nuevo se cierra solo al final.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Toma de inventario físico
-- -----------------------------------------------------------------------------
create table if not exists inventory_counts (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,                       -- CT-0001
  note text,
  actor text,
  created_at timestamptz not null default now()
);

create table if not exists inventory_count_lines (
  id uuid primary key default gen_random_uuid(),
  count_id uuid not null references inventory_counts(id) on delete cascade,
  material_id uuid not null references materials(id) on delete cascade,
  system_qty numeric not null,                     -- lo que decía el sistema al contar
  counted_qty numeric not null check (counted_qty >= 0),
  difference numeric not null,                     -- contado − sistema
  reason text
);
create index if not exists idx_count_lines_count on inventory_count_lines(count_id);

alter table stock_movements add column if not exists count_id uuid references inventory_counts(id) on delete set null;
create index if not exists idx_movements_count on stock_movements(count_id);


-- -----------------------------------------------------------------------------
-- 2. Condiciones de la orden: fecha prometida, moneda, tipo de cambio e IGV
-- -----------------------------------------------------------------------------
alter table purchase_orders add column if not exists expected_date date;
alter table purchase_orders add column if not exists currency text not null default 'PEN';
alter table purchase_orders add column if not exists exchange_rate numeric not null default 1;
alter table purchase_orders add column if not exists tax_rate numeric not null default 0;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'purchase_orders_currency_chk') then
    alter table purchase_orders add constraint purchase_orders_currency_chk check (currency in ('PEN', 'USD'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'purchase_orders_exchange_rate_chk') then
    alter table purchase_orders add constraint purchase_orders_exchange_rate_chk check (exchange_rate > 0);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'purchase_orders_tax_rate_chk') then
    alter table purchase_orders add constraint purchase_orders_tax_rate_chk check (tax_rate >= 0 and tax_rate <= 1);
  end if;
end $$;


-- -----------------------------------------------------------------------------
-- 3. Recepción contra documento
-- -----------------------------------------------------------------------------
create table if not exists order_receipts (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references purchase_orders(id) on delete cascade,
  delivered_by text,                               -- quién entregó (chofer, proveedor…)
  document_ref text,                               -- N.º de guía de remisión o factura
  notes text,                                      -- observaciones: faltantes, material dañado…
  actor text,                                      -- quién la registró en el sistema
  received_at timestamptz not null default now()
);
create index if not exists idx_receipts_order on order_receipts(order_id, received_at desc);

alter table stock_movements add column if not exists receipt_id uuid references order_receipts(id) on delete set null;
create index if not exists idx_movements_receipt on stock_movements(receipt_id);

-- Misma función de siempre, con los datos del documento. Se elimina la firma anterior para que
-- no queden dos versiones (PostgREST no sabría cuál llamar).
drop function if exists receive_order(uuid, jsonb, text);

create or replace function receive_order(
  p_order_id uuid, p_receipts jsonb, p_actor text default null,
  p_delivered_by text default null, p_document_ref text default null, p_notes text default null
) returns text
language plpgsql as $$
declare
  v_code text;
  v_status text;
  r record;
  v_item record;
  v_qty numeric;
  v_pending int;
  v_receipt uuid;
  v_doc text := nullif(trim(p_document_ref), '');
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

    if v_receipt is null then   -- una recepción por llamada, con su documento
      insert into order_receipts (order_id, delivered_by, document_ref, notes, actor)
      values (p_order_id, nullif(trim(p_delivered_by), ''), v_doc, nullif(trim(p_notes), ''), p_actor)
      returning id into v_receipt;
    end if;

    update purchase_order_items set received_qty = received_qty + v_qty where id = v_item.id;
    if v_item.material_id is not null then
      insert into stock_movements (material_id, kind, quantity, note, order_id, actor, movement_type, receipt_id)
      values (
        v_item.material_id, 'entrada', v_qty, 'Recepción ' || v_code || coalesce(' · ' || v_doc, ''),
        p_order_id, p_actor, 'recepcion', v_receipt
      );
    end if;
  end loop;

  select count(*) into v_pending from purchase_order_items
    where order_id = p_order_id and received_qty < quantity;
  v_status := case when v_pending > 0 then 'parcial' else 'recibida' end;
  update purchase_orders set status = v_status, updated_at = now() where id = p_order_id;
  return v_status;
end $$;


-- -----------------------------------------------------------------------------
-- 4. Adjuntos (fotos y PDF de facturas, guías de remisión, vales firmados…)
-- -----------------------------------------------------------------------------
create table if not exists attachments (
  id uuid primary key default gen_random_uuid(),
  entity_type text not null,                       -- orden | vale | conteo
  entity_id uuid not null,
  filename text not null,
  content_type text,
  size_bytes bigint,
  storage_path text not null unique,
  uploaded_by text,
  created_at timestamptz not null default now()
);
create index if not exists idx_attachments_entity on attachments(entity_type, entity_id);

-- Depósito privado: los archivos solo se leen con la clave de servicio (la app los sirve).
do $$
begin
  if to_regclass('storage.buckets') is not null then
    insert into storage.buckets (id, name, public) values ('adjuntos', 'adjuntos', false)
    on conflict (id) do nothing;
  end if;
end $$;


-- -----------------------------------------------------------------------------
-- 5. Presupuesto por etapas de obra
-- -----------------------------------------------------------------------------
alter table site_budgets add column if not exists stage text not null default '';
alter table dispatch_vouchers add column if not exists stage text;
alter table stock_movements add column if not exists stage text;

-- La misma partida puede repetirse en etapas distintas (cimentación, estructura, acabados…).
alter table site_budgets drop constraint if exists site_budgets_project_site_id_material_id_key;
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'site_budgets_site_material_stage_key') then
    alter table site_budgets add constraint site_budgets_site_material_stage_key unique (project_site_id, material_id, stage);
  end if;
end $$;

drop function if exists create_dispatch(uuid, uuid, text, text, text, jsonb);

create or replace function create_dispatch(
  p_site uuid, p_worker uuid, p_requested_by text, p_note text, p_actor text, p_lines jsonb,
  p_stage text default null
) returns text
language plpgsql as $$
declare
  v_code text;
  v_voucher uuid;
  v_site_name text;
  v_stage text := nullif(trim(p_stage), '');
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
  insert into dispatch_vouchers (code, project_site_id, site_name, worker_id, requested_by, note, actor, stage)
  values (v_code, p_site, v_site_name, p_worker, nullif(trim(p_requested_by), ''), nullif(trim(p_note), ''), p_actor, v_stage)
  returning id into v_voucher;

  for l in select * from jsonb_array_elements(p_lines) loop
    insert into stock_movements (material_id, project_site_id, kind, quantity, note, actor, voucher_id, movement_type, stage)
    values (
      (l ->> 'material_id')::uuid, p_site, 'salida', (l ->> 'quantity')::numeric,
      coalesce(nullif(l ->> 'note', ''), 'Despacho ' || v_code), p_actor, v_voucher, 'despacho', v_stage
    );
  end loop;
  return v_code;
end $$;


-- -----------------------------------------------------------------------------
-- 6. Unidades de medida (lista cerrada que define la app)
-- -----------------------------------------------------------------------------
alter table materials add column if not exists unit text;

-- Rellena la unidad a partir de la métrica actual («Área (m²)» → m², «Peso (kg)» → kg…).
-- Si la métrica menciona dos unidades se toma la primera; se puede corregir luego en Materiales.
update materials
set unit = coalesce(
  (regexp_match(metric_label, '\((m³|m²|kg|m|ton|gal|l)[ )/]'))[1],
  case when metric_label ilike 'unidad%' then 'und' end
)
where unit is null and metric_label is not null;


-- -----------------------------------------------------------------------------
-- 7. Permisos: si la base ya está cerrada, lo nuevo nace cerrado; si no, abierto como el resto
-- -----------------------------------------------------------------------------
do $$
declare
  t text;
  closed boolean := coalesce((select relrowsecurity from pg_class where oid = 'public.materials'::regclass), false);
begin
  foreach t in array array['inventory_counts', 'inventory_count_lines', 'order_receipts', 'attachments']
  loop
    if closed then
      execute format('alter table public.%I enable row level security', t);
      execute format('revoke all on table public.%I from anon, authenticated', t);
    else
      execute format('alter table public.%I disable row level security', t);
      execute format('grant select, insert, update, delete on table public.%I to anon, authenticated', t);
    end if;
  end loop;

  if closed then
    revoke all on function public.receive_order(uuid, jsonb, text, text, text, text) from public, anon, authenticated;
    revoke all on function public.create_dispatch(uuid, uuid, text, text, text, jsonb, text) from public, anon, authenticated;
    grant execute on function public.receive_order(uuid, jsonb, text, text, text, text) to service_role;
    grant execute on function public.create_dispatch(uuid, uuid, text, text, text, jsonb, text) to service_role;
  else
    grant execute on function public.receive_order(uuid, jsonb, text, text, text, text) to anon, authenticated;
    grant execute on function public.create_dispatch(uuid, uuid, text, text, text, jsonb, text) to anon, authenticated;
  end if;
end $$;

notify pgrst, 'reload schema';
