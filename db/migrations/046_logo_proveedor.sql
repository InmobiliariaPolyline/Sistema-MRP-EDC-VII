-- =============================================================================
-- Logotipo de los proveedores
--
-- Cómo usarlo: copia TODO este archivo en el SQL Editor de Supabase y pulsa Run.
-- Es idempotente y no toca datos existentes (solo agrega una columna).
--
--   suppliers.logo   imagen del proveedor como texto (data URL base64 de una imagen ya reducida a ~160 px, de pocos KB).
--                    Se sube al crear o editar un proveedor y se muestra en su tarjeta y en su ficha.
-- =============================================================================

alter table suppliers add column if not exists logo text;
