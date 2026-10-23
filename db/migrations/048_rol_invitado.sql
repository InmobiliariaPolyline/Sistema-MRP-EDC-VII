-- =============================================================================
-- Rol «invitado» con acceso temporal de 24 horas
--
-- Cómo usarlo: copia TODO este archivo en el SQL Editor de Supabase y pulsa Run.
-- Es idempotente. Qué cambia:
--
--   users.access_until   hasta cuándo puede entrar un invitado (se renueva 24 h cada vez que el administrador lo reactiva).
--                        El administrador no vence. Sin fecha = sin acceso hasta que el administrador lo reactive.
--   users.role           ahora solo existe 'admin' e 'invitado'. Los usuarios 'operador' pasan a 'invitado' SIN acceso activo:
--                        conservan su usuario y contraseña, pero el administrador debe reactivarlos (Trabajadores > Reactivar 24 h).
-- =============================================================================

alter table users add column if not exists access_until timestamptz;
alter table users alter column role set default 'invitado';
update users set role = 'invitado' where role not in ('admin', 'invitado');
