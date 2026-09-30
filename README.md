# Sistema MRP (Streamlit + Supabase)

Sistema con login propio, dashboard y varios módulos:

- **Dashboard**: totales generales (materiales, proveedores, proveedores con
  algo disponible, materiales sin proveedor).
- **Materiales**: catálogo general (categoría, nombre, densidad, métrica de
  cómputo), con alta/edición/baja e importar/exportar en Excel. El
  importador reconoce tanto encabezados en español como en inglés, y
  también el catálogo de referencia (501 materiales / 27 categorías) tal
  cual viene, con sus filas de título antes de la tabla.
- **Proveedores**: tarjetas de proveedores con su contacto (teléfono, correo,
  notas). Al abrir un proveedor se ve el catálogo completo de materiales
  agrupado por categoría, marcando cuáles ofrece y si está disponible ahora
  mismo (se marca a mano, pensado para saber a quién contactar). Importar y
  exportar proveedores también en Excel, en un archivo separado al de
  materiales.
- **Trabajadores** (solo administradores, reemplaza al antiguo módulo
  "Usuarios"): catálogo de personal de obra — nombre, documento, teléfono,
  puesto, a qué **cuadrilla** pertenece y en qué **obra/proyecto** está
  trabajando, con su ubicación en un mapa (geocodificación gratuita vía
  OpenStreetMap/Nominatim, sin API key). Cuando alguien también necesita
  entrar al sistema, se le puede dar acceso (usuario/contraseña/rol) desde
  la misma ficha; ese acceso vive en la tabla `users` de siempre.
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
- **Mapas**: `st.map` (nativo de Streamlit, sin API key) + geocodificación
  de direcciones con la API pública de Nominatim (OpenStreetMap).
- **Rendimiento**: las lecturas contra Supabase se cachean con
  `st.cache_data` (30s) para que navegar entre módulos no dispare una
  consulta de red en cada clic; cada escritura invalida el caché que
  corresponda.

## Puesta en marcha

1. Crea un proyecto en Supabase y corre `db/schema.sql` en su SQL Editor
   (crea las tablas `materials`, `suppliers`, `supplier_materials`, `users`,
   `work_groups`, `project_sites` y `workers`).
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
app.py                     # Punto de entrada: login + sidebar + navegación
db/auth.py                 # Hash y verificación de contraseñas (bcrypt)
db/client.py                # Cliente de Supabase (cacheado)
db/repository.py            # Fachada: Supabase o SQLite local según haya credenciales
db/local_repository.py      # Implementación SQLite (modo local/demo)
db/supabase_repository.py   # Implementación Supabase (con cache de lecturas)
db/schema.sql                # DDL de las tablas en Supabase
pages_app/login.py          # Login y alta del primer administrador
pages_app/dashboard.py      # Totales generales
pages_app/materiales.py     # Módulo de Materiales
pages_app/proveedores.py    # Módulo de Proveedores
pages_app/trabajadores.py   # Módulo de Trabajadores (cuadrillas, obras, acceso)
pages_app/ordenes.py        # Placeholder: Órdenes de compra
pages_app/reportes.py       # Placeholder: Reportes
utils/excel.py               # Importar/exportar Excel (alias español/inglés)
utils/geocode.py             # Geocodificación de direcciones (Nominatim)
```

## Formato de los Excel

**Materiales** (`materiales.xlsx`): acepta encabezados `category`/`name`/
`density`/`metric_label` o sus equivalentes en español (`Categoría`,
`Material`, `Densidad (kg/m³)`, `Métrica que usa`), y detecta la fila de
encabezado aunque el archivo traiga filas de título antes de la tabla (como
el catálogo de referencia). Se identifican por categoría + nombre: si ya
existe esa combinación, se actualiza; si no, se crea.

**Proveedores** (`proveedores.xlsx`): columnas `name`/`nombre` (obligatoria),
`contact_name`/`contacto`, `phone`/`telefono`, `email`/`correo`,
`notes`/`notas` (todas menos el nombre son opcionales). Cada fila importada
crea un proveedor nuevo.
