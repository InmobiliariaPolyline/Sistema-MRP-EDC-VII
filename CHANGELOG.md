# Registro de cambios

Historial de parches del Sistema MRP (Streamlit + Supabase): qué se agregó, qué se corrigió, los problemas que aparecieron y cómo se resolvieron. La versión vigente se muestra al pie del menú lateral («Sistema MRP · parche NNN») y vive en `core/version.py`.

Formato de cada parche: **Agregado** · **Corregido** · **Problemas y causa** · **Hay que hacer** (acciones fuera del código).

---

## Parche 053 — Fase F: historial con antes y después, pruebas SQL reales y limpieza · 2026-10-16

**Parche 052 · Pruebas contra un Postgres real**
- Nuevo `tests/sql/` con **14 pruebas que corren los scripts y las funciones SQL en un Postgres 18 de verdad** (PGlite, Postgres compilado a WebAssembly; solo necesita Node). Cubren: todos los scripts en orden y repetidos, `receive_order` (parcial, completa, tope, orden cancelada o inexistente, todo o nada, documento), `create_dispatch` (vale, etapa, numeración, sin stock no deja nada), los triggers (stock nunca negativo, no borrar órdenes con recepción, historial de precios), las vistas (`stock_levels`, `site_consumption`, `dashboard_stats`), las restricciones nuevas, y el **cierre de la base** (`040`: la clave pública no ve nada, la de servicio sí; lo que se agrega después nace cerrado; `040b` lo deshace). `tests/test_sql_runtime.py` las lanza desde Python y GitHub Actions las corre en cada subida.
- **Problema real que encontraron:** volver a correr `036_despacho_mrp.sql` después de la Fase B re-creaba las funciones `receive_order` y `create_dispatch` con su firma antigua y quedaban **dos versiones** de cada una (la API no sabría cuál llamar). Además reabría `price_history` y `dispatch_vouchers` en una base cerrada. Ahora 036 elimina la versión antigua si existe la nueva y respeta una base cerrada.
- `db/schema.sql` ahora es el **esquema completo hasta la Fase F** para instalaciones nuevas (con un aviso de no volver a correrlo sobre una base cerrada con datos).

**Parche 053 · Historial con valor anterior y nuevo**
- Las ediciones de **materiales, proveedores, precios/disponibilidad del catálogo, órdenes (campos y líneas), estado de las órdenes y presupuestos de obra** anotan **qué cambió**: «Stock mínimo: 5 → 8», «Cemento (cantidad): 10 → 12», «Estado: Pendiente → Enviada». Si no cambió nada, no se anota. El texto del resumen ya incluye el detalle, y además se guarda de forma estructurada (`entity_type`, `entity_id`, `changes`).
- Pantalla Historial: cada edición con detalle tiene «Ver los N cambio(s)» con la tabla Campo / Antes / Después, y un filtro «Solo ediciones con detalle».
- El respaldo guarda esa columna como JSON válido y se puede restaurar.

**Limpieza**
- Eliminado código sin uso: `set_user_active` y `delete_user` (ambos repositorios), `ui.meter`, `ui.activity_list`, `geocode_address`, un import sin usar y un parámetro sobrante.
- `streamlit-option-menu` ya se había quitado en el parche 041.

**Pruebas nuevas (23):** diferencias y descripción de cambios, texto/JSON del historial, columnas en una base local antigua y respaldo; 14 pruebas SQL en Postgres real (corren dentro de la suite de Python si hay Node).

**Hay que hacer**
- Correr `db/migrations/044_fase_f.sql` en Supabase (agrega tres columnas a `audit_log`). Antes de eso el historial sigue funcionando con el detalle dentro del texto del resumen.
- Para correr las pruebas SQL en tu equipo: `cd tests/sql && npm ci` (opcional; en GitHub se hace solo).

## Parche 051 — Fase E: rendimiento · 2026-10-16

**Problema:** tres pantallas (la ficha de una obra, el despacho/devolución y la sugerencia de compra) traían **todos** los movimientos de stock (hasta 100 000 filas, en peticiones de 1 000) y los sumaban en Python cada vez que se abrían. Funcionaba con pocos datos, pero se pondría lento con el uso.

**Cambios**
- **Consumo por obra ya sumado en la base** (vista `site_consumption`: despachado − devuelto por obra, material y etapa). Lo usan el progreso de la obra, el aviso de presupuesto al despachar, el stock devuelto por obra y la sugerencia de compra. En una prueba con 60 000 movimientos en la base local, de 582 ms a 54 ms; contra Supabase el ahorro es mayor: de ~40 peticiones de red a 1. El resultado es idéntico (hay una prueba que compara la vista con el cálculo en Python).
- **Contadores del dashboard en una sola consulta** (vista `dashboard_stats`) en lugar de leer materiales, proveedores, vínculos, órdenes y vales completos.
- **Conteo de líneas de vales y de recepciones** con un conteo agregado en vez de traer los ids de cada línea.
- **Índices** para las consultas frecuentes (movimientos por obra/material/fecha, líneas de orden, estado y fecha de órdenes, ofertas por material, presupuestos por obra, historial).
- **Botón «Actualizar datos»** en el menú lateral: vuelve a leer todo de la base al instante. La lectura se guarda en memoria 30 s para ir rápido; si algún día hay varias personas, ese botón (o la variable `MRP_CACHE_TTL` para cambiar los segundos) cubre el desfase.
- La **devolución de obra** puede indicar la etapa de la que se devuelve, para descontar del consumo de esa etapa (antes un material despachado a una etapa y devuelto sin etapa dejaba la etapa sin descontar).
- Si el SQL de la fase aún no se corrió, la app calcula lo mismo leyendo las tablas (como antes): nada se rompe.
- `compute_suggestions` recibe ahora el consumo ya sumado en lugar de la lista de movimientos.

**Pruebas nuevas (5):** la vista equivale al cálculo en Python con devoluciones, mermas, conteos, devoluciones a proveedor y etapas; filtros; filas netas en cero; devolución por etapa; y que ninguna pantalla vuelva a leer todos los movimientos.

**Hay que hacer**
- Correr `db/migrations/043_fase_e.sql` en Supabase (crea las dos vistas y los índices; no toca datos). La app ya funciona sin él, solo que sin la mejora.

## Parche 050 — Fase D: reportes, reporte de obra, kardex y correo · 2026-10-16

**Agregado**
- **Reportes con 8 conjuntos nuevos** (ahora 17): vales de salida, detalle de vales, historial de precios, presupuestos de obra (con etapa e importe), conteos de inventario, recepciones de órdenes (guía, quién entregó, observaciones), calificación de proveedores e historial de cambios. Por defecto siguen marcados los 9 de siempre («Los básicos»); el resto se agrega a gusto. Movimientos de inventario ahora trae motivo, vale, etapa y conteo.
- **Reporte de obra en PDF** (Obras → «📄 Reporte de la obra»): resumen (presupuesto, pedido, recibido, despachado valorizado, disponible, avance), tabla por material con su estado (EXCEDE / fuera de presupuesto), tabla por etapa y lista de vales. Importes en soles y sin IGV; horizontal, listo para imprimir.
- **Kardex por material** (Inventario → Kardex): cada entrada y salida en orden cronológico con documento (orden, vale o conteo), detalle y **saldo corrido**; avisa si el saldo no coincide con el stock actual. Descarga en Excel y PDF.
- **Envío por correo** de órdenes y de vales de salida: el botón abre tu programa de correo con destinatario (el del proveedor), asunto y texto ya escritos; se adjunta el PDF descargado. No se envía nada desde el servidor ni se guardan contraseñas. En la orden también marca la orden pendiente como enviada, igual que WhatsApp.
- `list_movements` acepta filtrar por material (además de obra), y ordena empates de forma estable.

**Pruebas nuevas (9):** kardex (saldo, orden, etiquetas, vacíos y NaN), enlaces de correo (codificación y recorte), los 17 conjuntos de Reportes con exportación a Excel y PDF, reporte de obra con y sin datos, texto del vale y coincidencia del kardex con el stock.

**Hay que hacer:** nada (no hay SQL nuevo).

## Parche 049 — Fase C: compras y precios (vigencia, plazos, envío y calificación) · 2026-10-16

**Parche 047 · Vigencia de precios**
- Cada precio del catálogo de un proveedor muestra **cuándo se actualizó** («actualizado hace 12 d», «⚠ hace 5 meses (vencido)»). La vigencia es de 90 días y se ajusta en la ficha del proveedor.
- Filtro **«Precio vencido»** y tarjeta «Precios vencidos» en el catálogo del proveedor.
- Al crear una orden: aviso al elegir un material con precio vencido y un resumen de cotizaciones vencidas antes de crearla. En la sugerencia de compra: columna «Cotización» y aviso de las vencidas. Un precio sin fecha conocida (anterior al historial) no se marca como vencido.

**Parche 048 · Plazos, mínimo de compra y registro del envío**
- El proveedor tiene **plazo de entrega habitual** y **monto mínimo de compra** (opcionales).
- La **sugerencia de compra** muestra por proveedor el total estimado, su mínimo, el plazo y la fecha aproximada de llegada. Si el pedido no llega al mínimo avisa cuánto falta y ofrece **completar con materiales que ese proveedor vende y están por debajo del doble de su stock mínimo** (marcas los que quieras sumar). Las órdenes creadas por la sugerencia llevan como fecha prometida «hoy + plazo».
- **Envío registrado:** al abrir «Enviar por WhatsApp» una orden pendiente pasa sola a «enviada» y guarda la fecha y hora de envío (`sent_at`); también al marcarla como enviada a mano. El detalle de la orden muestra «Enviada al proveedor el …». La primera fecha no se pisa.

**Parche 049 · Calificación de proveedores**
- Nota de 0 a 100 por proveedor: **entrega a tiempo** (60 %: órdenes completadas a más tardar en su fecha prometida; las abiertas con fecha vencida cuentan como atrasadas) y **cantidades completas** (40 %: lo recibido sobre lo pedido en órdenes recibidas o parciales de más de 30 días). Etiquetas: Excelente (90+), Buena (75+), Regular (50+), Baja. Sin historial no se califica.
- Se ve en la lista de proveedores y, con el detalle (a tiempo, cantidades, atraso promedio), en la ficha.

**Pruebas nuevas (22):** vigencia de precios, plazos y mínimos, candidatos para completar un pedido, orden del envío y calificación.

**Hay que hacer**
- Correr `db/migrations/042_fase_c.sql` en Supabase (agrega `lead_time_days`, `min_order_amount` y `sent_at`). Antes de eso todo sigue funcionando; guardar plazo o mínimo avisa que falta el SQL y el envío se marca sin hora.

## Parche 046 — Métricas de cómputo de lista cerrada · 2026-10-16
Fase B, última parte.

**Agregado**
- **La métrica de cómputo se elige de una lista** (Materiales → nuevo / editar): primero las métricas que ya usa tu catálogo (por frecuencia) y luego las estándar (m², m³, kg, m, unidad, litros, galones, bolsa, saco, rollo, plancha, caja, balde, juego, millar, global). Con «➕ Otra métrica…» se puede escribir una nueva.
- **Normalización:** lo que se escribe se unifica antes de guardarse (m3, M³ y m^3 → m³; Kg y kgs → kg; unidades y und → unidad) y si coincide con una métrica conocida se usa tal cual está escrita. Así «Volumen (m3)» y «Volumen (m³)» ya no son dos cosas distintas.
- No hace falta SQL ni cambia el catálogo existente: las 22 métricas que ya tienes (por ejemplo «Área (m²)») siguen siendo válidas y aparecen en la lista. Se descartó agregar una columna `unit` aparte porque la métrica ya es la unidad que se muestra en toda la app.
- Pruebas nuevas (4): normalización, respeto de métricas conocidas y orden de las opciones.

**Ajustes**
- Los botones de Inventario («Devolver de una obra», «Toma de inventario», «Entrada, merma o devolución a proveedor») tienen más ancho y ya no se parten en tres líneas.
- Comprobado en un navegador real con una base de prueba: el diálogo de devolución, la toma de inventario completa (contar, anotar el motivo, guardar → «Conteo CT-0001 guardado», stock ajustado de 46 a 44) y el formulario de nueva orden con la fecha, la moneda y el IGV.

## Parche 045 — Presupuesto por etapas de obra · 2026-10-16
Fase B, cuarta parte.

**Agregado**
- **Etapas en el presupuesto:** al añadir un material al presupuesto de una obra se puede elegir su etapa (o crear una nueva). El mismo material puede estar en varias etapas de la misma obra; guardar de nuevo en la misma etapa reemplaza su cantidad y precio.
- **Despacho por etapa:** el vale y sus movimientos guardan la etapa (opcional). El aviso de presupuesto al despachar compara contra la etapa elegida.
- **Pestaña Materiales de la obra:** con etapas aparece un selector («Todas las etapas», «Sin etapa» o una etapa) que muestra el presupuesto y lo despachado de esa etapa. Las órdenes de compra no se asignan a etapas, así que la vista por etapa omite Pedido y Recibido.
- «Quitar del presupuesto» lista ahora cada partida con su etapa; la ficha del material muestra la etapa en «Obras donde se usa».
- El detalle del vale muestra su etapa.

**Corregido**
- El gasto pedido de una obra ahora se calcula en **soles y sin IGV** (precio × tipo de cambio), coherente con las órdenes en dólares de la Fase B.
- La sugerencia de compra y el aviso de cantidad de las órdenes sumaban mal si un material estaba presupuestado dos veces en la misma obra; ahora agrupan por obra y material.
- Las bases locales de prueba antiguas se actualizan solas (se reconstruye `site_budgets` conservando los datos).

**Hay que hacer**
- Correr `db/migrations/041_fase_b.sql` (cambia la restricción única de `site_budgets` y reemplaza `create_dispatch`). Antes del SQL, el presupuesto y el despacho sin etapa siguen funcionando; con etapa avisa que falta el SQL.
- Pruebas nuevas (6): etapas, progreso por etapa, vale con etapa, sugerencias sin doble resta y actualización de una base local antigua.

## Parche 044 — Documentos adjuntos · 2026-10-16
Fase B, tercera parte.

**Agregado**
- **📎 Documentos adjuntos** en la orden de compra, en el vale de salida y en el conteo de inventario: foto o PDF de la factura, la guía de remisión, el vale firmado, etc. (PDF, PNG, JPG o WEBP; máximo 10 MB). Se pueden abrir, descargar y quitar. El archivo se lee de la base solo al pulsar «Abrir».
- En Supabase los archivos van a un **depósito privado** (`adjuntos`) de Storage y la lista a la tabla `attachments`; solo se accede con la clave de servicio. Si el depósito no existe, la app lo crea la primera vez que se sube algo. Sin clave de servicio, la app lo avisa en vez de intentar subirlo. En local se guardan en `db/attachments/` (ignorado por git).
- El nombre del archivo se limpia (sin rutas ni caracteres raros) y la ruta incluye un código único, así que dos archivos con el mismo nombre no se pisan.
- La pantalla Respaldo aclara que el ZIP incluye la lista de adjuntos pero no los archivos.
- Pruebas nuevas (7): reglas del archivo, ruta única y ciclo subir-leer-borrar.

**Hay que hacer**
- Tener configurada `SUPABASE_SERVICE_KEY` (ver parche 041) y correr `db/migrations/041_fase_b.sql` (crea la tabla `attachments`).

## Parche 043 — Fecha prometida, moneda, IGV y recepción contra documento · 2026-10-16
Fase B, segunda parte.

**Agregado**
- **Fecha prometida de entrega** por orden. Una orden abierta que pasa esa fecha se marca «N d de atraso» en la lista, aparece en un aviso rojo (lista, detalle y dashboard) y cuenta en el chip de atrasadas del dashboard (junto a las que llevan muchos días sin cerrarse).
- **Moneda (soles o dólares), tipo de cambio e IGV** por orden. Los totales muestran subtotal, IGV y total en la moneda de la orden. El dashboard y el aviso de presupuesto de obra suman siempre **en soles** (dólares × tipo de cambio; el presupuesto compara sin IGV). El PDF y el mensaje de WhatsApp incluyen fecha, moneda e IGV.
- **Recepción contra documento:** N.º de guía o factura, quién entregó y observaciones. Cada recepción queda guardada (tabla `order_receipts`) y se ve en «Recepciones registradas» dentro de la orden; el movimiento de stock menciona la guía.
- El reporte de órdenes (Reportes) trae ahora entrega prometida, moneda, subtotal, IGV y total.
- Pruebas nuevas (13): moneda e IGV, totales en soles, atrasos, y recepciones con su documento.

**Problemas y causa**
- El panel de alertas del dashboard solo conocía las órdenes «viejas»; se separó el aviso de las atrasadas por fecha prometida para no mezclar los dos criterios.

**Hay que hacer**
- Correr `db/migrations/041_fase_b.sql` (el mismo script de toda la Fase B). Mientras no se corra, las órdenes siguen funcionando igual (soles, sin IGV), pero guardar una fecha, dólares, IGV o los datos del documento avisa que falta el SQL.

## Parche 042 — Devoluciones de obra y toma de inventario · 2026-10-16
Fase B (operación real del almacén), primera parte.

**Agregado**
- **Devolver de una obra** (Inventario y pestaña Materiales de cada obra): el material que sobra vuelve al almacén. No deja devolver más de lo que la obra tiene (despachado menos devuelto) ni materiales que nunca recibió; es todo o nada. Queda anotado quién devuelve.
- **Toma de inventario físico:** se cuenta por categoría, se compara con el sistema y cada diferencia genera un ajuste (entrada si sobra, salida si falta) con su motivo. Cada conteo queda guardado (CT-0001…) con el detalle de lo que decía el sistema y lo contado, en la pestaña nueva **Conteos**.
- **Devolución a proveedor** como tercer tipo de movimiento manual (sale del almacén y no cuenta como consumo de ninguna obra).
- Lo despachado a una obra ahora **descuenta lo devuelto** en el presupuesto de la obra, en el aviso al despachar y en la sugerencia de compra (`utils/consumption.py`).
- Nuevas etiquetas en Movimientos: Devolución de obra, Devolución a proveedor y Toma de inventario.
- Pruebas nuevas (11): devoluciones, topes, todo o nada, conteos en ambos sentidos y consumo neto.

**Corregido**
- `040_cerrar_base.sql` y `040b_reabrir_base_emergencia.sql` ahora recorren **todas** las tablas, vistas, secuencias y funciones del esquema público, en lugar de una lista fija: también cierran las tablas de los parches siguientes y no fallan si una función cambió de firma.

**Hay que hacer**
- Correr `db/migrations/041_fase_b.sql` en Supabase (es el script de toda la Fase B; se puede correr una sola vez cuando termine la fase). Sin él, las devoluciones funcionan, pero la toma de inventario avisa que falta el SQL.

## Parche 041 — Seguridad, respaldos, versiones fijas y revisión automática · 2026-10-16
Primera fase del plan de mejoras (lo necesario antes de usar datos reales).

**Agregado**
- **Clave de servicio y base cerrada.** La app usa `SUPABASE_SERVICE_KEY` (service_role, solo en el servidor) si existe; si no, la pública como hasta ahora. El script `db/migrations/040_cerrar_base.sql` activa RLS sin políticas y quita todos los permisos a la clave pública (tablas, vista, secuencia y funciones). `040b_reabrir_base_emergencia.sql` lo deshace. `python scripts/check_security.py` comprueba tabla por tabla si la clave pública puede escribir. Mientras la base esté abierta, la app lo avisa en el menú lateral.
- **Bloqueo por intentos fallidos:** 5 contraseñas incorrectas seguidas bloquean al usuario 15 minutos (también para nombres que no existen, para no revelar cuáles hay). Muestra los intentos que quedan.
- **Política de contraseñas** (al menos 8 caracteres, letras y números, no común, distinta del usuario) para el primer administrador, accesos nuevos y cambios.
- **«Mi cuenta»** (menú lateral): cambio de contraseña con la actual.
- **Cookie de sesión** firmada con `SESSION_SECRET` (o la clave de servicio) y con atributo `Secure` bajo HTTPS. `SESSION_SECRET` ya está en los ejemplos de configuración.
- **Respaldo** (pantalla nueva, solo administrador): descarga un ZIP con un CSV por tabla, cifrado con AES-256 si se pone contraseña. `scripts/backup.py` hace lo mismo por línea de comandos y `scripts/restore_backup.py` restaura (upsert por `id`, repetible, no borra).
- **Respaldo semanal automático** en GitHub Actions (`.github/workflows/backup.yml`): ZIP cifrado guardado 30 días; no corre sin `BACKUP_PASSWORD`.
- **Versiones fijas** en `requirements.txt` (streamlit 1.66.0, pandas 3.0.6, etc.) y `requirements-dev.txt` para desarrollo. Se quitó la librería `streamlit-option-menu`, que ya no se usaba.
- **Revisión automática** (`.github/workflows/tests.yml`): corre las pruebas en cada subida a `main` y en cada pull request.
- **Pruebas nuevas** (59 en total): bloqueo y contraseñas, respaldo (ZIP, cifrado, tablas vacías, ciclo completo) y validación de sintaxis de todos los scripts SQL con el analizador real de Postgres (`pglast`).

**Problemas y causa**
- Con la base abierta, quien consiga la clave pública puede leer y escribir todo, incluida la tabla `users` (hashes de contraseña). Se comprobó con `check_security.py`: las 15 tablas y las 2 funciones eran accesibles.
- Probando el respaldo con datos reales apareció un fallo: una tabla vacía se guardaba como archivo sin columnas y no se podía leer. Corregido y con prueba.

**Hay que hacer (en este orden)**
1. Supabase → Project Settings → API: copiar la clave **service_role**.
2. Guardarla como `SUPABASE_SERVICE_KEY` en Streamlit Cloud (Manage app → Settings → Secrets) y en el `.env` local. Agregar también `SESSION_SECRET` (texto largo y aleatorio).
3. Reiniciar la app y comprobar que funciona.
4. **Solo entonces** ejecutar `db/migrations/040_cerrar_base.sql` en el SQL Editor. Si se ejecuta antes del paso 2 la app deja de funcionar (se arregla con `040b_reabrir_base_emergencia.sql`).
5. Comprobar con `python scripts/check_security.py` (debe decir «Base cerrada»).
6. Opcional: secretos del repositorio `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` y `BACKUP_PASSWORD` para el respaldo semanal (repositorio privado).

## Parche 040 — Error al hacer un despacho (vacíos que llegaban como NaN) · 2026-10-16
**Corregido**
- Después de despachar, la pantalla de Inventario mostraba «No se pudo completar esta operación» (`TypeError: sequence item 3: expected str instance, float found`).
- El mismo fallo podía aparecer en otras pantallas con datos de Supabase (lista de trabajadores en Obras, nombres con puesto o documento vacíos…), y los textos de reemplazo («Sin puesto», «sin solicitante») no se usaban o salía «nan».

**Problemas y causa**
- Con **pandas 3** (la versión que instala Streamlit Cloud), una columna de texto con algunos vacíos pasa a tipo `str` y sus vacíos son `NaN`, que en Python es un `float` «verdadero». `" · ".join(...)` falla con él y `x or "otro texto"` nunca usa el texto de reemplazo. La capa local (SQLite) ya devolvía `None`, por eso no se veía al probar sin Supabase.
- Se arregló en la raíz: todos los DataFrames que devuelve `db/supabase_repository.py` pasan por `_df(...)`, que deja los vacíos de texto como `None` (las columnas numéricas conservan su NaN numérico). Se comprobó con tus datos reales: ninguna tabla devuelve ya `NaN` en columnas de texto y las 10 pantallas cargan.
- Prueba automática nueva (`tests/test_nan.py`) que documenta y vigila el problema.

## Parche 039 — No se podía registrar trabajadores (RLS activo en `workers`) · 2026-10-16
**Corregido**
- Al registrar un trabajador salía «No se pudo registrar al trabajador».
- Registrar trabajadores (y, por la misma causa, cualquier escritura en esa tabla) quedaba bloqueado por Supabase.

**Problemas y causa**
- La tabla `workers` tenía **Row Level Security (RLS) activo sin políticas**, así que Supabase rechazaba toda escritura con el error `42501` («new row violates row-level security policy»). `db/schema.sql` nunca incluyó `disable row level security` para `workers` ni para las tablas base (`materials`, `suppliers`, `supplier_materials`, `users`, `work_groups`, `project_sites`); las demás ya estaban abiertas porque se desactivaron a mano en su día. Se comprobó escribiendo y borrando una fila de prueba en las 15 tablas: solo `workers` estaba bloqueada.
- La app escondía la causa real detrás de un mensaje genérico, así que parecía un fallo sin explicación.

**Agregado**
- `db/migrations/037_disable_rls_all.sql`: desactiva RLS en todas las tablas de la app (idempotente). También quedó añadido al final de `db/schema.sql` para instalaciones nuevas.
- Los errores de base de datos ahora muestran su causa: si es RLS, dicen qué tabla y qué comando corre el administrador; en los demás casos se agrega el detalle técnico debajo del mensaje.

**Hay que hacer**
- En Supabase → SQL Editor: `alter table workers disable row level security;` (o el archivo `037_disable_rls_all.sql`, que cubre todas las tablas).

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
