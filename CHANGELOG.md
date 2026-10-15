# Registro de cambios

Historial de parches del Sistema MRP (Streamlit + Supabase): qué se agregó, qué se corrigió, los problemas que aparecieron y cómo se resolvieron. La versión vigente se muestra al pie del menú lateral («Sistema MRP · parche NNN») y vive en `core/version.py`.

Formato de cada parche: **Agregado** · **Corregido** · **Problemas y causa** · **Hay que hacer** (acciones fuera del código).

---

## Parche 038 — Editar una orden permite agregar y quitar materiales · 2026-10-16
**Agregado**
- Al editar una orden (pendiente o enviada, mientras no haya recibido material) ahora se puede, en un solo guardado: **agregar** materiales del catálogo del proveedor (con su precio fijo), **cambiar la cantidad** de cada línea y **quitar** líneas. Obra y notas también.
- Si el material ya estaba en la orden, lo agregado se suma a su cantidad y conserva su precio; si no tiene precio en el catálogo, no se puede agregar.
- Si la orden ya estaba «enviada», el aviso al guardar recuerda **reenviar** el pedido actualizado (el PDF y el mensaje de WhatsApp se arman siempre con los datos vigentes de la orden).
- Prueba automática del caso agregar + cambiar cantidad + quitar.

## Parche 037 — El precio unitario de una orden es el del catálogo y no se edita · 2026-10-16
**Corregido**
- Al crear una orden, el precio unitario se podía subir o bajar a mano. Ahora es de solo lectura: sale del catálogo del proveedor (donde el administrador sí lo edita) y solo cambia el **total** al pedir más cantidad.
- Si el material no tiene precio en el catálogo del proveedor, no se puede agregar a la orden: se avisa dónde registrarlo (Proveedores → Catálogo o importar su lista).
- Al **editar** una orden solo se pueden cambiar las cantidades (y quitar líneas); el precio queda como estaba.
- Al **duplicar** una orden, las líneas toman el precio vigente del catálogo, no el que tenía la orden original.

## Parche 036 — Despacho a obra, stock mínimo, sugerencia de compra e integridad · 2026-10-16
Basado en cómo se usa el sistema: **un solo administrador** opera el almacén; el material llega del proveedor al almacén (entrada) y sale hacia las obras cuando alguien lo pide en persona (despacho). No hay roles ni aprobaciones, y el almacén es uno solo.

**Agregado**
- **Despacho a obra con vale de salida** (`Inventario → ＋ Despachar a obra`, también desde Obras): obra, solicitante (trabajador o texto libre), varios materiales por vale, aviso si supera el presupuesto, descuento de stock y **vale PDF** con firmas (`VS-0001…`). Pestaña «Vales de salida» para reimprimirlos.
- **Stock mínimo** por material, alertas en el tablero y estado «stock bajo» en el inventario.
- **Sugerencia de compra** (`Órdenes de compra → Sugerencia de compra`): faltante = presupuesto sin despachar + mínimo − stock − lo que ya viene en órdenes; asigna el proveedor más barato y crea las órdenes agrupadas.
- **Importar lista de precios** del proveedor desde Excel/CSV (detecta columnas, tolera títulos, enlaza por nombre incluso con diferencias leves, vista previa y plantilla descargable) e **historial de precios**.
- **Editar órdenes** pendientes o enviadas (cantidades, precios, obra, notas, quitar líneas) mientras no hayan recibido material.
- Aviso de **presupuesto al crear una orden** (total y por material).
- Tablero: KPIs útiles (en el almacén, stock bajo, despachos del mes), alerta de stock bajo y accesos rápidos a despachar.
- `db/migrations/036_despacho_mrp.sql`: script SQL único (idempotente) con columnas, tablas, vista `stock_levels`, funciones `receive_order` y `create_dispatch`, triggers y permisos.
- Pruebas automáticas de stock, recepción, despacho, edición/borrado de órdenes, precios, sugerencia de compra e importación (34 en total).

**Corregido**
- «Consumo» pasa a llamarse **«Despacho»** en toda la interfaz (el material sale del almacén aunque todavía no se gaste).
- Borrar una orden con material recibido dejaba el stock descuadrado: ahora no se puede (se cancela). También lo impide un trigger en la base.
- Recepciones y despachos son **todo o nada** (función en la base; respaldo en Python que valida antes de escribir). No se puede recibir más de lo pedido ni sacar más stock del que hay, ni siquiera con dos operaciones simultáneas (trigger con bloqueo).
- El KPI «sin proveedor» se quitó del tablero: el catálogo es todo lo que el almacén puede manejar, no solo lo cotizado.

**Problemas y causa**
- **Límite silencioso de 1 000 filas**: PostgREST (Supabase) corta cada consulta en 1 000 filas sin avisar; con 500 materiales × varios proveedores o miles de movimientos, listas como ofertas, líneas de órdenes y movimientos se truncaban. Ahora se consultan por páginas (`_select_all`, probado contra Supabase con 501 filas en páginas de 100).
- El stock se calculaba con los últimos 5 000 movimientos (en Supabase, 1 000): ahora sale de la vista `stock_levels` (o de todos los movimientos si la vista aún no existe).

**Hay que hacer**
- En Supabase → SQL Editor, pegar y ejecutar `db/migrations/036_despacho_mrp.sql` (una vez). Hasta entonces la app funciona con respaldos, pero sin historial automático de precios, sin los triggers de integridad y con despachos/recepciones menos protegidos contra fallos a medias.
- Reiniciar la app en Streamlit Cloud si no toma el cambio.

## Parche 035 — Los cambios de CSS no se veían en Streamlit Cloud · 2026-10-15
**Corregido**
- Los parches 033 y 034 (espaciado, textos pegados) estaban en GitHub pero la app desplegada seguía mostrando el diseño anterior hasta reiniciarla.

**Problemas y causa**
- `modules/ui_styles.py` leía los `.css` una sola vez al importarse. Streamlit solo recarga los módulos `.py` que cambian y Streamlit Cloud actualiza los archivos sin reiniciar el proceso, así que un parche que solo tocaba CSS no tenía efecto. Ahora `ui_styles.bundle()` compara la fecha y el tamaño de los `.css` en cada recarga y los vuelve a leer solo si cambiaron. Se comprobó cambiando un `.css` con el servidor encendido: se aplicó sin reiniciar.
- Se comprobó también con Streamlit 1.66 (la versión que instala Cloud con `streamlit>=1.56,<2`), además de la 1.56 con la que se desarrolla: el espaciado y el menú quedan correctos en ambas.

**Hay que hacer**
- Una sola vez, en Streamlit Cloud: *Manage app → Reboot app* para que cargue este parche. Después, los cambios solo de CSS se aplican solos.

## Parche 034 — Textos pegados en todo el UI · 2026-10-15
**Corregido**
- Textos que quedaban pegados o tapados por el módulo siguiente (ej. «RESUMEN» sobre «Dashboard»), en todas las pantallas, el menú y los diálogos.
- Pastillas en línea que se tocaban al partirse en dos líneas; etiquetas de campo muy pegadas a su campo; nombre/subtítulo de las filas sin separación.

**Problemas y causa**
- Streamlit pone `margin-bottom: -1rem` a cada bloque Markdown (y a `st.caption`) para cancelar el margen del último párrafo. Los bloques HTML propios (`.mrp-*`) no llevan párrafo, así que su contenido se salía 1 rem sobre el elemento siguiente. Se neutralizó ese margen en `15_spacing.css`.

**Agregado**
- `tools/audit_spacing.js`: auditor para la consola del navegador que detecta elementos solapados (SOLAPE) o a menos de 5 px (PEGADO). Se pasó por los 10 módulos y por los diálogos en HD, FHD y UHD.

## Parche 033 — Espaciado uniforme y proporcional · 2026-10-15
**Corregido**
- Separación irregular entre bloques (14 px en unos sitios, 35 px en otros) porque los bloques propios sumaban sus márgenes al hueco del contenedor.
- Los cuatro accesos rápidos se partían en 3 + 1 filas al agrandarse el hueco entre columnas.
- Cinco `st.write("")` que metían huecos de más.

**Agregado**
- `modules/styles/15_spacing.css`: una sola escala de espaciado (`--gap-section`, `--gap-card`, `--gap-field`, `--gap-tight`) en rem. Separación medida entre bloques: ≈20 px en HD, 27 px en FHD, 44 px en UHD.

## Parche 032 — Hojas CSS ordenadas, 16:9 y gráficos · 2026-10-15
**Agregado**
- El CSS pasó de cadenas de Python a archivos reales en `modules/styles/` (paletas + 00 base · 10 layout · 20 sidebar · 30 controles · 40 componentes · 50 formularios · 60 responsive). `modules/ui_styles.py` los une.
- Escalado fluido para pantallas 16:9: tamaño raíz 15 px (HD 1280) → ≈17 px (FHD 1920) → ≈24 px (UHD 3840), con ancho máximo propio por rango; la altura de los gráficos Plotly se ajusta a la pantalla.
- Gráficos del dashboard: gasto mensual + órdenes, órdenes por estado, gasto por categoría (mosaico), gasto por proveedor, avance de materiales por obra, asistencia de los últimos 14 días.
- `modules/form_assist.py`: progreso de campos obligatorios, aviso de nombres duplicados, medidor y coincidencia de contraseñas, autoenfoque en diálogos y botones Guardar/Cancelar fijos al pie del diálogo.

**Corregido**
- La tipografía Inter nunca se cargaba: su `@import` quedaba después de las reglas y el navegador lo ignoraba.

**Problemas y causa**
- Una hoja larga con líneas en blanco dentro de `st.markdown` se mostraba como texto: se minifica antes de inyectarla.
- `:has()` no admite `:has()` anidado: la barra fija de acciones usaba un selector inválido y no se aplicaba.
- Streamlit no vigila los `.css`: tras cambiar uno hay que reiniciar el servidor.

## Parche 031 — Rediseño visual completo · 2026-10-15
**Agregado**
- Sistema de diseño moderno: fondo con degradados suaves, sombras en capas, tarjetas con color por tipo, botones con degradado, pestañas segmentadas, diálogos con fondo difuminado, chips con punto de color y animaciones de entrada.
- Menú lateral siempre oscuro, agrupado (Resumen · Compras y almacén · Obra y personal · Análisis), con iconos Material y tarjeta de usuario.
- Dashboard con banner de bienvenida, accesos rápidos y línea de tiempo de actividad.
- Login con panel de marca (degradado y tres ventajas) y pantalla de carga con el mismo fondo.

**Corregido**
- Alerta de «modo de prueba» ilegible en el menú oscuro; botones del menú centrados en vez de alineados a la izquierda.

## Parche 030 — Formularios y experiencia visual · 2026-10-10 (por el equipo)
**Agregado / cambiado**
- Paleta con variables CSS (claro/oscuro propio, sin invertir colores), formularios con `st.form` y vista previa, secciones numeradas, estados vacíos, paginación, resultados con contador y botón «Limpiar» en los filtros.
- Reglas de validación compartidas (`modules/forms.py`) que se aplican al guardar y en vivo; pruebas en `tests/test_forms.py`.
- Navegación con botones propios (sustituye a `streamlit-option-menu`).

## Parche 029 — Fichas, guías y validación en vivo · 2026-10-06
**Agregado**
- Ficha de obra (Información con mapa · Materiales · Trabajadores · Progreso) y ficha de material (qué significa su densidad, precios por proveedor, stock y obras donde se usa).
- Botón «❓ Cómo usar» en cada módulo y consejos con ejemplo en los formularios (`modules/guides.py`).
- Validación en vivo al teclear (contador, caracteres no permitidos, borde rojo/verde) en `modules/live_validation.py`.
- Modo oscuro con mejor contraste.

**Problemas y causa**
- Una expresión regular con `\"` no era válida en modo Unicode y detenía la validación: se corrigió y se protegió con `try/catch`.
- El script de validación se creaba dentro de un iframe que Streamlit destruye en cada recarga; ahora se instala como `<script>` de la página principal.

## Parche 028 — Enlace a Google Maps con coordenadas · 2026-10-06
**Corregido**
- «Abrir en Google Maps» abre las coordenadas guardadas de la obra, no la dirección escrita; cada obra con ubicación tiene su enlace.

## Parche 027 — Ubicación exacta de obras · 2026-10-06
**Corregido / agregado**
- Campo para pegar un enlace de Google Maps (largo o corto) o coordenadas; la búsqueda por dirección muestra hasta 5 candidatos sin duplicados para elegir.

**Problemas y causa**
- OpenStreetMap no tiene números de puerta en muchas zonas y devuelve el eje de la calle (a ≈1 km del punto real, ej. Av. Las Lomas 1649, San Juan de Lurigancho). Ningún buscador gratuito lo resuelve; por eso la ubicación por búsqueda se marca como «aproximada».

## Parche 026 — Sesión persistente y `app.py` · 2026-10-06
**Agregado**
- La sesión sobrevive a recargar la página: cookie firmada (HMAC, 7 días); cerrar sesión la borra. Define `SESSION_SECRET` para usar tu propio secreto.
- Manejo global de errores con mensaje claro y botón «Reintentar»; versión visible en el menú; sidebar abierto al iniciar y menú del navegador más limpio.

## Parche 025 — Compras, almacén y obra · 2026-10-06
**Agregado**
- Recepción parcial por línea de orden (estado «Recibida parcial»); **Inventario** (entradas, consumos, mermas, movimientos); **Obras** con presupuesto frente a pedido/recibido/consumido; **Asistencia** diaria; **Historial** de cambios (quién, qué y cuándo).
- Comparador de cotizaciones al crear una orden (por material y por pedido completo), duplicar orden, PDF de la orden y mensaje de WhatsApp, alertas de órdenes atrasadas.
- Gráficos de gasto, carga única del catálogo de 501 materiales (`scripts/seed_catalog.py`) y primer modo oscuro.

**Hay que hacer**
- Correr en Supabase el SQL de la «Ronda 3» al final de `db/schema.sql` (tablas `stock_movements`, `site_budgets`, `attendance`, `audit_log` y columna `received_qty`, con RLS desactivado).

**Problemas y causa**
- El encabezado real del Excel es «Densidad (kg/m³)» y «Métrica que usa»: el script reconoce los encabezados por prefijo.

---

## Base previa (sin numerar) · 2026-09-29 → 2026-10-06
- Sistema MRP inicial: materiales y proveedores con catálogo por proveedor, disponibilidad y precio; login propio con `bcrypt`; dashboard; rendimiento (caché de lecturas de Supabase); módulo **Trabajadores** (cuadrillas, obras, mapa); reorganización en capas `core/` · `modules/` · `db/`; **Órdenes de compra** y **Reportes** (Excel/PDF); edición, búsqueda y contacto rápido (llamar, WhatsApp, correo).
- Se quitó la importación/exportación de Excel de Materiales y Proveedores (los reportes viven en Reportes).

---

## Problemas conocidos y pendientes
**Seguridad (fuera de alcance por decisión del equipo; pendiente)**
- La tabla `users` es legible con la clave pública de Supabase (hay que activar RLS con políticas o mover la autenticación al servidor).
- No hay límite de intentos de inicio de sesión ni cambio de contraseña.
- El secreto de la cookie de sesión usa por defecto la clave de Supabase; define `SESSION_SECRET`.

**Funcionales**
- Las obras ya guardadas no se pueden editar (para corregir su ubicación hay que borrarlas y crearlas de nuevo).
- La recepción de una orden no valida cantidades en la capa de datos (la pantalla sí limita lo que se puede recibir).
- Ubicar por dirección es aproximado (OpenStreetMap); para el punto exacto pega el enlace de Google Maps.
- La barra de Guardar/Cancelar de los diálogos es fija: con contenido largo flota sobre los campos que quedan debajo (comportamiento esperado).

**Técnicos**
- Hasta el parche 034, tras editar un `.css` había que reiniciar Streamlit; desde el 035 se recargan solos.
- Los gráficos Plotly usan píxeles; su altura se ajusta con un script (`form_assist.py`) al cargar y al redimensionar.
