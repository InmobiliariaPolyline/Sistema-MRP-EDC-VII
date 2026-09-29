-- Esquema para Supabase (Postgres). Ejecutar en el SQL Editor del proyecto.

create extension if not exists "pgcrypto";

-- Catálogo de materiales.
create table if not exists materials (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  name text not null,
  density numeric,
  metric_label text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (category, name)
);

-- Proveedores.
create table if not exists suppliers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  contact_name text,
  phone text,
  email text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Qué materiales ofrece cada proveedor, y si está disponible ahora mismo
-- (lo marca el usuario a mano, no se calcula de un stock).
create table if not exists supplier_materials (
  id uuid primary key default gen_random_uuid(),
  supplier_id uuid not null references suppliers(id) on delete cascade,
  material_id uuid not null references materials(id) on delete cascade,
  available boolean not null default true,
  price numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (supplier_id, material_id)
);

create index if not exists idx_materials_category on materials(category);
create index if not exists idx_supplier_materials_supplier on supplier_materials(supplier_id);
create index if not exists idx_supplier_materials_material on supplier_materials(material_id);
