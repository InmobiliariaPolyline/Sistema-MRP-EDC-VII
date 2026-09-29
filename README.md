# Sistema MRP (Streamlit + Supabase)

Sistema con login propio, dashboard y varios módulos:

- **Dashboard**: totales generales (materiales, proveedores, proveedores con
  algo disponible, materiales sin proveedor).
- **Materiales**: catálogo general (categoría, nombre, densidad, métrica de
  cómputo), con alta/edición/baja e importar/exportar en Excel.
- **Proveedores**: tarjetas de proveedores con su contacto (teléfono, correo,
  notas). Al abrir un proveedor se ve el catálogo completo de materiales
  agrupado por categoría, marcando cuáles ofrece y si está disponible ahora
  mismo (se marca a mano, pensado para saber a quién contactar). Importar y
  exportar proveedores también en Excel, en un archivo separado al de
  materiales.
- **Usuarios** (solo administradores): crear cuentas, activar/desactivar,
  eliminar. Roles: `admin` y `operador`.
- **Órdenes de compra** y **Reportes**: todavía sin implementar (pantallas
  "próximamente").

Todavía no incluye expedientes/tareas del planner original; se evaluará más
adelante.

## Stack

- **Frontend/backend**: [Streamlit](https://streamlit.io) (todo en un solo
  proceso, sin API aparte).
- **Base de datos**: [Supabase](https://supabase.com) (Postgres), vía el
  cliente `supabase-py`.
- **Login**: tabla `users` propia (no Supabase Auth), contraseñas con hash
  `bcrypt`. La sesión vive en `st.session_state` mientras la pestaña del
  navegador siga abierta.

## Puesta en marcha

1. Crea un proyecto en Supabase y corre `db/schema.sql` en su SQL Editor
   (crea las tablas `materials`, `suppliers`, `supplier_materials` y `users`).
2. Instala las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

3. Configura las credenciales de Supabase, de una de estas dos formas:
   - Copia `.env.example` a `.env` y completa `SUPABASE_URL` / `SUPABASE_KEY`.
   - O copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml`
     (recomendado si vas a desplegar en Streamlit Community Cloud).

4. Corre la app:

   ```bash
   streamlit run app.py
   ```

5. Como todavía no hay usuarios, la primera vez la app te pide crear el
   Administrador (nombre, usuario y contraseña). Desde ahí puedes crear más
   cuentas en el módulo **Usuarios**.

## Estructura

```
app.py                     # Punto de entrada: login + sidebar + navegación
db/auth.py                 # Hash y verificación de contraseñas (bcrypt)
db/client.py                # Cliente de Supabase (cacheado)
db/repository.py            # Fachada: Supabase o SQLite local según haya credenciales
db/local_repository.py      # Implementación SQLite (modo local/demo)
db/supabase_repository.py   # Implementación Supabase
db/schema.sql                # DDL de las tablas en Supabase
pages_app/login.py          # Login y alta del primer administrador
pages_app/dashboard.py      # Totales generales
pages_app/materiales.py     # Módulo de Materiales
pages_app/proveedores.py    # Módulo de Proveedores
pages_app/usuarios.py       # Módulo de Usuarios (solo admin)
pages_app/ordenes.py        # Placeholder: Órdenes de compra
pages_app/reportes.py       # Placeholder: Reportes
utils/excel.py               # Importar/exportar Excel
```

## Formato de los Excel

**Materiales** (`materiales.xlsx`): columnas `category`, `name`, `density`
(opcional), `metric_label`. Se identifican por `category + name`: si ya
existe esa combinación, se actualiza; si no, se crea.

**Proveedores** (`proveedores.xlsx`): columnas `name` (obligatoria),
`contact_name`, `phone`, `email`, `notes` (todas opcionales). Cada fila
importada crea un proveedor nuevo.
