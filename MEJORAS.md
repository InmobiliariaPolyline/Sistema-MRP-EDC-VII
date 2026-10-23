# Hoja de ruta: qué falta cerrar y qué se puede mejorar

Estado al parche 072 (22/10/2026): ~16 500 líneas de Python, 283 pruebas automáticas que corren en cada subida (GitHub Actions), 13 módulos, migraciones SQL (hasta la 047) y un manual de usuario dentro de la app. El flujo completo funciona: proveedor → orden de compra (IGV, cuotas, varios proveedores) → recepción → almacén → despacho a obra con vale.

Reglas del sistema que cualquier mejora debe respetar: un solo administrador, un solo almacén, el catálogo de 501 materiales es la lista maestra (materiales sin proveedor son normales), el sistema **no compra ni paga** ni se conecta con los proveedores, y las cifras son «valor de los pedidos», nunca «pérdida» ni «pagado».

---

## 1. Para cerrar esta semana (en este orden)

**A. Puesta en producción (hacer sí o sí)**
1. Correr en el SQL Editor de Supabase `046_logo_proveedor.sql` y `047_pedido_varios_proveedores.sql`.
2. **Rotar la clave `SUPABASE_SERVICE_KEY`** (se filtró en una conversación) y actualizarla en Streamlit Cloud y en `.env`.
3. Reiniciar la app en Streamlit Cloud y comprobar que el pie del menú dice el parche vigente.
4. Cargar los datos de la empresa en *Mi cuenta* (razón social, RUC, dirección fiscal): salen en los PDF de órdenes.
5. Si la base tiene datos de prueba, correr `python scripts/clean_data.py` (conserva catálogo, usuarios y empresa) y cargar proveedores y precios reales (Importar precios en la ficha de cada proveedor).
6. Activar el **respaldo semanal** de GitHub (secretos `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `BACKUP_PASSWORD`; repositorio privado) y **probar una restauración** una vez.

**B. Huecos funcionales que conviene tapar antes de entregar**
| # | Qué | Por qué |
|---|-----|---------|
| 1 | **Editar una obra ya creada** (nombre, dirección, ubicación) | Hoy solo se puede borrar y volver a crear; es el pendiente más antiguo. |
| 2 | **Acciones sobre un pedido completo (PD-)**: cancelar todas sus órdenes, marcar todas como enviadas y un estado resumen | Hoy cada orden del pedido se maneja por separado. |
| 3 | **Permisos más finos del Operador** (p. ej. que no pueda cancelar ni eliminar órdenes, ni ajustar inventario) | Hoy el Operador ve todo menos Trabajadores, Historial y Respaldo. |
| 4 | **Cuotas por vencer en el Dashboard** (próximos 7 días, vencidas) | Las cuotas ya se calculan; falta avisarlas donde se mira cada día. |
| 5 | **Revisión en el celular** de los formularios nuevos (orden, pedido, ficha del pedido) y en modo oscuro | Se diseñaron y probaron en escritorio. |
| 6 | **Prueba de punta a punta con datos reales** (un pedido de dos proveedores, recepción parcial, despacho, reporte) en la app desplegada | Es la mejor red de seguridad antes de entregar. |

**C. Entrega**
- Sesión de capacitación corta con el Manual de Usuario (ya trae maquetas y buscador) y una hoja con las 5 tareas diarias: crear pedido, recibir, despachar, ver stock mínimo, descargar reporte.
- Dejar escrito quién renueva credenciales y cómo se actualiza (README: «Puesta en marcha»).

---

## 2. Mejoras recomendadas (después de entregar)

### Compras
- **Pedir cotización a varios proveedores a la vez** (WhatsApp con los materiales ya escritos), antes de armar la orden.
- **Marcar una cuota como «avisada a tesorería»** o con la fecha en que se pagó, solo como registro informativo (el sistema sigue sin pagar).
- **Cotizaciones vigentes con historial por proveedor**: gráfico de cómo cambia el precio de un material en el tiempo (ya existe `price_history`).
- **Editar un pedido con varios proveedores** como un todo (hoy se edita cada orden).
- Plantillas de pedido por obra o por etapa («lo que siempre se pide para cimentación»).
- Condiciones de pago por defecto en la ficha de cada proveedor (para no repetirlas en cada orden).

### Almacén e inventario
- **Código QR o de barras en el vale de salida** y lectura con la cámara para recibir/despachar (los PDF ya dibujan el código de barras).
- **Ubicación dentro del almacén** (pasillo/estante) por material.
- Alertas por correo o WhatsApp cuando un material cruza su stock mínimo.
- Conteos cíclicos programados (hoy el inventario físico se hace a mano).

### Obras y personal
- **Avance de obra por etapa** con fotos adjuntas.
- Cuadrillas con horarios y resumen de asistencia exportable por quincena.
- Costo de materiales por obra frente al presupuesto con un gráfico de consumo por etapa.

### Dashboard y reportes
- Compras por proveedor y por mes con comparación contra el mes anterior.
- Reporte de **ahorro logrado** (precio pagado frente al más caro del catálogo) para mostrar el valor del comparador de cotizaciones.
- Programar reportes semanales por correo al administrador.

### Calidad técnica
- `modules/ordenes.py` tiene ~1 100 líneas: separar la lista, el detalle y el alta en archivos propios.
- Pruebas de interfaz (AppTest) de los diálogos de orden y de pedido; hoy se cubren la lógica, los PDF y los datos, no el recorrido de pantallas.
- Hacer que las pruebas **no puedan** tocar la base real aunque exista `.env` (hoy hay que apartar el archivo a mano; correrlas con `.env` presente consulta Supabase).
- `db/schema.sql` debe incluir todas las columnas de las migraciones 046 y 047 (verificar con una instalación nueva).
- Registro de errores centralizado (por ejemplo, un archivo de log o un servicio gratuito) en vez de depender de los avisos en pantalla.
- Fijar y revisar mensualmente las versiones de `requirements.txt` (hoy están fijas; falta el hábito de actualizarlas a propósito).

### Seguridad
- Rotar claves cada cierto tiempo y no pegarlas en chats ni capturas.
- Autenticación en dos pasos para el administrador.
- Revisar que ninguna tabla nueva nazca con Row Level Security abierto (`python scripts/check_security.py` después de cada migración).

---

## 3. Lo que NO se recomienda hacer

- Conectar con los sistemas de los proveedores, procesar pagos o guardar tarjetas/cuentas: contradice el alcance del sistema y agrega riesgo legal y de seguridad.
- Una orden única con líneas de varios proveedores: cada proveedor necesita su propio documento, IGV, pago y recepción. El **pedido PD-** ya da la sensación de una sola ficha sin romper eso.
- Varios almacenes o varios administradores: el sistema se diseñó para uno de cada uno; cambiarlo toca casi todas las tablas.
