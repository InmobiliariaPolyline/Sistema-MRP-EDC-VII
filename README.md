# Sistema MRP (Streamlit + Supabase)

Sistema con login propio, dashboard y varios módulos:

- **Dashboard**: totales generales (materiales, proveedores, proveedores con
  algo disponible, materiales sin proveedor).
- **Materiales**: catálogo maestro (categoría, nombre, densidad, métrica de
  cómputo) con búsqueda, filtro por categoría, alta, edición y baja. Cada
  material muestra el mejor precio disponible entre los proveedores.
- **Proveedores**: tarjetas de proveedores con su contacto (teléfono, correo,
  notas). Al abrir un proveedor se ve el catálogo completo de materiales
  agrupado por categoría, marcando cuáles ofrece, si está disponible ahora
  mismo y a qué precio. Cada tarjeta trae contacto rápido (llamar, WhatsApp,
  correo), búsqueda, edición y baja con confirmación.
- **Trabajadores** (solo administradores, reemplaza al antiguo módulo
  "Usuarios"): catálogo de personal de obra — nombre, documento, teléfono,
  puesto, a qué **cuadrilla** pertenece y en qué **obra/proyecto** está
  trabajando, con su ubicación en un mapa (geocodificación gratuita vía
  OpenStreetMap/Nominatim, sin API key). Cuando alguien también necesita
  entrar al sistema, se le puede dar acceso (usuario/contraseña/rol) desde
  la misma ficha; ese acceso vive en la tabla `users` de siempre.
- **Órdenes de compra**: pedidos a un proveedor con sus líneas de material
  (cantidad y precio, que se precarga del catálogo del proveedor), obra
  destino y un estado que avanza de pendiente a enviada y recibida (o
  cancelada). Las órdenes conservan el nombre del proveedor y del material
  aunque después se borren.
- **Reportes**: descarga en Excel (una hoja por conjunto de datos) o PDF de
  materiales, proveedores, catálogo y precios por proveedor, trabajadores y
  órdenes de compra.

En todos los módulos: buscadores y filtros, edición, confirmación antes de
borrar, avisos (toast) al guardar, y diseño adaptado a móvil.

Todavía no incluye expedientes/tareas del planner original; se evaluará más
adelante.

## Arquitectura

Streamlit **no separa frontend y backend** como el planner original
(Next.js + Express): es un solo proceso Python que arma la página completa
en cada interacción. `app.py` no es "el frontend" — es apenas el arranque
(configura la página, exige sesión iniciada). El resto se organiza en tres
capas, cada una en su carpeta:

- `core/` — el cascarón ya autenticado: sidebar (marca, menú, cerrar
  sesión) y qué módulo mostrar según lo que el usuario elija. No sabe nada
  de materiales, proveedores, etc.; solo orquesta.
- `modules/` — una pantalla por archivo (Dashboard, Materiales,
  Proveedores, Trabajadores...). Cada una arma su propia interfaz y le pide
  los datos a `db/`; no habla con Supabase directamente.
- `db/` — el acceso a datos: `repository.py` es la fachada que los módulos
  usan sin saber si hay Supabase o SQLite local detrás (`supabase_repository.py`
  / `local_repository.py`), y `client.py`/`auth.py`/`schema.sql` acompañan
  a eso.

`utils/` son helpers sin estado (geocodificación, fechas relativas) que no
le pertenecen a ningún módulo en particular.

## Stack

- **Todo en un proceso**: [Streamlit](https://streamlit.io) (sin API aparte;
  ver "Arquitectura" arriba).
- **Base de datos**: [Supabase](https://supabase.com) (Postgres), vía el
  cliente `supabase-py`.
- **Login**: tabla `users` propia (no Supabase Auth), contraseñas con hash
  `bcrypt`. La sesión vive en `st.session_state` mientras la pestaña del
  navegador siga abierta.
- **Mapas**: `st.map` (nativo de Streamlit, sin API key) + geocodificación
  de direcciones con la API pública de Nominatim (OpenStreetMap).
- **Rendimiento**: las lecturas contra Supabase se cachean con
  `st.cache_data` (30s) para que navegar entre módulos no dispare una
  consulta de red en cada clic; cada escritura invalida el caché que
  corresponda.

## Puesta en marcha

1. Crea un proyecto en Supabase y corre `db/schema.sql` en su SQL Editor
   (crea las tablas `materials`, `suppliers`, `supplier_materials`, `users`,
   `work_groups`, `project_sites`, `workers`, `purchase_orders` y
   `purchase_order_items`). Si actualizas un proyecto existente, corre solo
   las tablas que falten. Si alguna queda con Row Level Security activado,
   la app no podrá escribir en ella: el propio `schema.sql` trae los
   `alter table ... disable row level security`.
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
   cuentas en el módulo **Trabajadores** (o dar acceso a un trabajador ya
   registrado).

## Estructura

```
app.py                      # Arranque: config de página, exige login, llama a core/shell.py

core/shell.py                # Sidebar (marca, menú, cerrar sesión) y ruteo entre módulos

db/auth.py                   # Hash y verificación de contraseñas (bcrypt)
db/client.py                 # Cliente de Supabase (cacheado)
db/repository.py             # Fachada: Supabase o SQLite local según haya credenciales
db/local_repository.py       # Implementación SQLite (modo local/demo)
db/supabase_repository.py    # Implementación Supabase (con cache de lecturas)
db/schema.sql                 # DDL de las tablas en Supabase

modules/login.py             # Login y alta del primer administrador
modules/dashboard.py         # Totales generales
modules/materiales.py        # Módulo de Materiales
modules/proveedores.py       # Módulo de Proveedores
modules/trabajadores.py      # Módulo de Trabajadores (cuadrillas, obras, acceso)
modules/ordenes.py           # Módulo de Órdenes de compra (alta, estados, detalle)
modules/reportes.py          # Módulo de Reportes (Excel y PDF)
modules/ui.py                # CSS y componentes visuales compartidos (tarjetas, pastillas...)

utils/geocode.py              # Geocodificación de direcciones (Nominatim)
utils/reports.py              # Generación de Excel (openpyxl) y PDF (fpdf2)
utils/timeago.py              # Fechas relativas ("hace 5 min")
```
