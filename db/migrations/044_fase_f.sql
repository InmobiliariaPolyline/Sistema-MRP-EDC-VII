-- =============================================================================
-- Fase F — Historial de cambios con valor anterior y nuevo
--
-- Cómo usarlo: copia TODO este archivo en el SQL Editor de Supabase y pulsa Run.
-- Es idempotente y no toca datos (solo agrega columnas a audit_log).
--
--   audit_log.entity_type   qué se cambió: material, proveedor, orden, presupuesto…
--   audit_log.entity_id     id del registro cambiado
--   audit_log.changes       lista de cambios [{"field": "...", "before": "...", "after": "..."}]
-- =============================================================================

alter table audit_log add column if not exists entity_type text;
alter table audit_log add column if not exists entity_id text;
alter table audit_log add column if not exists changes jsonb;

create index if not exists idx_audit_entity on audit_log(entity_type, entity_id);

notify pgrst, 'reload schema';
