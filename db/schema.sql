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

-- Cuentas del sistema. El primer usuario se crea desde la propia app
-- (pantalla de "crear el primer administrador" cuando esta tabla está vacía).
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  username text not null unique,
  password_hash text not null,
  name text not null,
  role text not null default 'operador', -- 'admin' | 'operador'
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Cuadrillas/equipos de trabajo (ej. "Electricistas", "Cuadrilla A").
create table if not exists work_groups (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  created_at timestamptz not null default now()
);

-- Obras/proyectos de construcción, con ubicación geocodificada (OpenStreetMap)
-- para mostrarlas en el mapa.
create table if not exists project_sites (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text,
  latitude double precision,
  longitude double precision,
  created_at timestamptz not null default now()
);

-- Trabajadores de obra: su información personal, a qué cuadrilla
-- pertenecen y en qué obra están trabajando. `user_id` es opcional: solo
-- se llena si además tiene cuenta para entrar al sistema (ver `users`).
create table if not exists workers (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  document_id text,
  phone text,
  position text,
  work_group_id uuid references work_groups(id) on delete set null,
  project_site_id uuid references project_sites(id) on delete set null,
  user_id uuid references users(id) on delete set null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_workers_group on workers(work_group_id);
create index if not exists idx_workers_site on workers(project_site_id);
