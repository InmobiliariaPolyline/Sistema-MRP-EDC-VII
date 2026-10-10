# Sistema MRP (Streamlit + Supabase)

Sistema con login propio, dashboard y varios módulos:

- **Dashboard**: totales generales, gasto por mes y por proveedor, órdenes
  por estado, alertas de órdenes atrasadas y mapa de obras. Hay **modo
  oscuro** (interruptor en el sidebar).
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
  cancelada). Al armar el pedido, un **comparador de cotizaciones** muestra
  el precio de cada proveedor lado a lado y sugiere el más barato (por
  material y para el pedido completo). La **recepción es parcial por
  línea** (lo que llega se suma al inventario y la orden queda «Recibida
  parcial» hasta completarse). Cada orden se puede **duplicar**, bajar en
  **PDF** o enviar por **WhatsApp** con el pedido ya escrito. Las órdenes
  abiertas hace más de X días se marcan con ⏰ aquí y en el dashboard.
- **Inventario**: stock por material (entradas por recepciones y ajustes,
  menos consumo en obra y mermas) e historial de movimientos.
- **Obras**: presupuesto de materiales por obra frente a lo pedido, recibido
  y consumido, con aviso cuando un material excede lo previsto.
- **Asistencia**: pasar lista por día (estado y obra de cada trabajador) y
  resumen por trabajador y por obra.
- **Ayuda en cada pantalla**: botón «❓ Cómo usar» junto al título de cada módulo, consejos con ejemplo en los formularios y **validación en vivo** mientras se escribe (contador de caracteres, qué falta, qué caracteres no se permiten, borde rojo/verde).
- **Ficha de obra y de material**: en *Obras*, pestañas de información (mapa), materiales, trabajadores y progreso; en *Materiales*, el botón ℹ️ abre la ficha del material (qué significa su densidad, precios, stock y obras donde se usa).
- **Sesión persistente**: al recargar la página no se pierde el login (cookie firmada, 7 días; define `SESSION_SECRET` en `.env`/secrets para tu propio secreto).
- **Historial** (solo administradores): quién creó, editó, recibió o
  eliminó qué y cuándo.
- **Reportes**: descarga en Excel (una hoja por conjunto de datos) o PDF de
  materiales, proveedores, catálogo y precios por proveedor, trabajadores y
  órdenes de compra.

En todos los módulos: buscadores y filtros, edición, confirmación antes de
borrar, avisos (toast) al guardar, y diseño adaptado a móvil.

Todavía no incluye expedientes/tareas del planner original; se evaluará más
adelante.

## Arquitectura

### Formularios e interfaz (parche 030)

- Campos agrupados por propósito, con etiquetas, ejemplos, ayuda y acciones de guardar, cancelar y revisar datos cuando corresponde. Los formularios de registro conservan lo escrito si falla la validación.
- `modules/forms.py` centraliza las reglas aplicadas antes de guardar; `modules/live_validation.py` utiliza esas reglas para mostrar errores, contadores y bordes al escribir. Los campos opcionales vacíos son válidos y se conserva la notación técnica del catálogo.
- `modules/ui_styles.py` contiene las paletas clara y oscura, tamaños y estados de los componentes. El modo oscuro conserva los colores de mapas e imágenes.
- El menú lateral usa botones nativos con estado activo y navegación por teclado, conservando todos los módulos y sus permisos anteriores.
- Materiales, catálogos y directorios usan páginas de 20, 50 o 100 filas cuando hay muchos registros. Las búsquedas incluyen contadores, estados vacíos y controles para limpiar filtros.
- Asistencia mantiene borradores durante la sesión al cambiar de fecha o filtro; marcar presentes prepara la lista y solo «Guardar asistencia» confirma los datos. Recibir todo lo pendiente también prepara un borrador de recepción que se confirma después.
- Se requiere Streamlit 1.56 o superior (antes de la versión 2). Las tablas conservan los controles nativos de Streamlit y los reportes siguen incluyendo todas las filas, aunque la pantalla se pagine.
- Pruebas de reglas: `python -m unittest discover -s tests -v`. Para pruebas aisladas del repositorio local se puede indicar una ruta SQLite mediante `MRP_LOCAL_DB`; por defecto continúa usando `db/local.db`.

Esta actualización conserva las tablas y los datos existentes; no necesita ejecutar SQL adicional ni cambiar las credenciales.

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
   `work_groups`, `project_sites`, `workers`, `purchase_orders`,
   `purchase_order_items`, `stock_movements`, `site_budgets`, `attendance`
   y `audit_log`). Si actualizas un proyecto existente, corre solo
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

4. (Opcional, una sola vez) Carga el catálogo de materiales desde el Excel:

   ```bash
   python scripts/seed_catalog.py ruta/al/listado_materiales.xlsx
   ```

   Es idempotente (si el material ya existe solo actualiza densidad y métrica).

5. Corre la app:

   ```bash
   streamlit run app.py
   ```

6. Como todavía no hay usuarios, la primera vez la app te pide crear el
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
modules/inventario.py        # Stock y movimientos
modules/obras.py             # Presupuesto por obra vs. pedido/recibido/consumido
modules/asistencia.py        # Pasar lista y resumen
modules/historial.py         # Auditoría (quién hizo qué)
modules/reportes.py          # Módulo de Reportes (Excel y PDF)
modules/ui.py                # CSS y componentes visuales compartidos (tarjetas, pastillas...)

scripts/seed_catalog.py       # Carga única del catálogo de materiales desde Excel

utils/geocode.py              # Geocodificación de direcciones (Nominatim)
utils/reports.py              # Generación de Excel (openpyxl) y PDF (fpdf2)
utils/timeago.py              # Fechas relativas ("hace 5 min")
```
