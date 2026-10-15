-- =============================================================================
-- Datos de la empresa (RUC), RUC de proveedores, IGV real y condición de pago
--
-- Cómo usarlo: copia TODO este archivo en el SQL Editor de Supabase y pulsa Run.
-- Es idempotente y no toca datos existentes (solo agrega una tabla y columnas).
--
--   company_profile                    datos de facturación de la empresa (razón social, RUC, dirección fiscal);
--                                      una sola fila. El RUC solo se muestra en la app tras pedir la contraseña.
--   suppliers.ruc                      RUC del proveedor (11 dígitos)
--   purchase_orders.prices_include_tax ¿los precios de la orden ya incluyen IGV? (si no, se suma 18 %)
--   purchase_orders.payment_terms      condición de pago (Contado, Crédito 30 días…): solo informativa, para tesorería
--
-- El sistema no cobra ni paga: las compras se pagan fuera, con el RUC de la empresa.
-- =============================================================================

create table if not exists company_profile (
  id uuid primary key default gen_random_uuid(),
  singleton boolean not null default true unique check (singleton),   -- fuerza una sola fila
  legal_name text,
  trade_name text,
  ruc text check (ruc is null or ruc ~ '^[0-9]{11}$'),
  fiscal_address text,
  updated_by text,
  updated_at timestamptz not null default now()
);

alter table suppliers add column if not exists ruc text;
alter table purchase_orders add column if not exists prices_include_tax boolean not null default false;
alter table purchase_orders add column if not exists payment_terms text;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'suppliers_ruc_chk') then
    alter table suppliers add constraint suppliers_ruc_chk check (ruc is null or ruc ~ '^[0-9]{11}$');
  end if;
end $$;

-- Permisos: si la base ya está cerrada (040_cerrar_base.sql) la tabla nueva nace cerrada; si no, como el resto.
do $$
declare
  closed boolean := coalesce((select relrowsecurity from pg_class where oid = 'public.materials'::regclass), false);
begin
  if closed then
    alter table public.company_profile enable row level security;
    revoke all on table public.company_profile from anon, authenticated;
  else
    alter table public.company_profile disable row level security;
    grant select, insert, update, delete on table public.company_profile to anon, authenticated;
  end if;
end $$;

notify pgrst, 'reload schema';
