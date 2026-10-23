# Hoja de ruta: qué falta cerrar y qué se puede mejorar

Estado al parche 072 (22/10/2026): ~16 500 líneas de Python, 283 pruebas automáticas que corren en cada subida (GitHub Actions), 13 módulos, migraciones SQL (hasta la 047) y un manual de usuario dentro de la app.

## Qué es este sistema (y qué no)

Es una herramienta para **preparar documentación y gestionar los datos del almacén**. Sus tres objetivos:

1. **Contactar con el proveedor**: tener sus datos, su catálogo y precios, y abrir WhatsApp, Gmail u Outlook con el mensaje ya escrito (llamar, pedir catálogo, cotizar, enviar la orden).
2. **Importar material al almacén**: orden de compra → recepción (parcial o total) → entrada al inventario; más la importación de listas de precios del proveedor.
3. **Exportar material a las obras**: despacho del almacén a la obra con su vale de salida (PDF para firmar), con control del presupuesto de la obra.

El sistema **no está conectado a ningún servicio real**: no se comunica con los proveedores (el usuario manda el mensaje o el PDF por su cuenta), no compra, no paga ni guarda cuentas o tarjetas, y no envía correos ni mensajes por sí mismo. Calcula el valor exacto de cada pedido (IGV 18 %) y genera los documentos. Por eso las cifras son «valor de los pedidos», nunca «pagado» ni «pérdida». Un solo administrador, un solo almacén y un catálogo maestro de 501 materiales (materiales sin proveedor son normales).

Toda mejora debe caber en eso: más claridad, más datos útiles, mejores documentos y menos pasos; nada que requiera un servicio externo real.

---

## 1. Para cerrar esta semana (en este orden)

**A. Puesta en producción (hacer sí o sí)**
1. Correr en el SQL Editor de Supabase `046_logo_proveedor.sql` y `047_pedido_varios_proveedores.sql`.
2. **Rotar la clave `SUPABASE_SERVICE_KEY`** (se filtró en una conversación) y actualizarla en Streamlit Cloud y en `.env`.
3. Reiniciar la app en Streamlit Cloud y comprobar que el pie del menú dice el parche vigente.
4. Cargar los datos de la empresa en *Mi cuenta* (razón social, RUC, dirección fiscal): salen en los PDF de las órdenes.
5. Si la base tiene datos de prueba, correr `python scripts/clean_data.py` (conserva catálogo, usuarios y empresa) y cargar los proveedores y precios reales (Importar precios en la ficha de cada proveedor).
6. Activar el **respaldo semanal** de GitHub (secretos `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `BACKUP_PASSWORD`; repositorio privado) y probar una restauración una vez.

**B. Huecos que conviene tapar antes de entregar (por objetivo)**
| Objetivo | # | Qué | Por qué |
|----------|---|-----|---------|
| Obras | 1 | ~~Editar una obra ya creada~~ **Hecho (parche 073)** | Nombre, dirección y ubicación, con historial. |
| Importar | 2 | ~~Acciones sobre un pedido completo (PD-)~~ **Hecho (parche 074)** | Estado resumen, marcar enviadas, cancelar y eliminar el pedido; PDF y WhatsApp por orden. |
| General | 3 | **Permisos del Operador** más acotados (p. ej. sin cancelar ni eliminar órdenes ni ajustar inventario) | Hoy ve todo menos Trabajadores, Historial y Respaldo. |
| Importar | 4 | **Fechas de las cuotas visibles en el Dashboard** (próximos 7 días y vencidas), como información para quien lleva el control | Las cuotas ya se calculan; falta que se vean donde se mira cada día. |
| General | 5 | **Revisar en celular y en modo oscuro** los formularios nuevos (orden, pedido, ficha del pedido) | Se diseñaron y probaron en escritorio. |
| Todos | 6 | **Prueba de punta a punta con datos reales** en la app desplegada: pedido a dos proveedores, recepción parcial, despacho con vale y reporte | Es la mejor red de seguridad antes de entregar. |

**C. Entrega**
- Capacitación corta con el Manual de Usuario (ya trae maquetas y buscador) y una hoja con las tareas diarias: crear pedido, recibir material, despachar a obra, revisar stock mínimo, descargar un reporte.
- Dejar escrito quién renueva las credenciales y cómo se actualiza la app (README, «Puesta en marcha»).

---

## 2. Mejoras posibles (después de entregar), dentro del alcance

### Contactar con el proveedor
- Mensajes preestablecidos más variados (reclamo por retraso, pedir factura o guía, confirmar fecha de entrega) para WhatsApp, Gmail y Outlook.
- **Preparar un mismo mensaje de cotización para varios proveedores** de una vez: el sistema deja listos los enlaces y el usuario los abre uno por uno (no se envía nada solo).
- Condiciones de pago y plazo por defecto en la ficha de cada proveedor, para no repetirlas en cada orden.
- Notas de contacto con fecha («llamé el 20/10, quedó en enviar precios»).

### Importar material (compras y almacén)
- Comparativo de cotizaciones **en PDF** para guardar o mostrar la decisión de compra.
- Historial de precios por material en un gráfico (ya existe `price_history`) y reporte de **ahorro** frente al proveedor más caro.
- Plantillas de pedido por obra o etapa («lo que siempre se pide para cimentación»).
- Editar un pedido con varios proveedores como un todo (hoy se edita cada orden).
- Ubicación del material dentro del almacén (pasillo/estante) como dato.
- Más ayudas en la importación de listas de precios: avisos de filas dudosas y vista previa de diferencias.

### Exportar material a obras
- Vale de salida con **código de barras impreso** para identificarlo (ya se dibuja; falta usarlo como referencia en el kardex y la búsqueda por código).
- Saldo de la obra: cuánto del presupuesto de cada material se ha despachado, con aviso al acercarse al límite (ya avisa al pasarse).
- Reporte de materiales por obra y por etapa listo para imprimir.
- Plantillas de despacho repetidas (lo que se manda cada semana a una obra).

### Datos y reportes
- Compras por proveedor y por mes con comparación con el mes anterior.
- Reportes del almacén (stock, mínimos, movimientos) con más filtros y totales.
- Exportación de un pedido completo (PD-) a Excel.

### Calidad técnica
- `modules/ordenes.py` tiene ~1 100 líneas: separar lista, detalle y alta en archivos propios.
- Pruebas de pantalla (AppTest) de los diálogos de orden y de pedido; hoy se cubren la lógica, los PDF y los datos.
- Que las pruebas **no puedan** tocar la base real aunque exista `.env` (hoy hay que apartar el archivo a mano).
- `db/schema.sql` debe incluir las columnas de las migraciones 046 y 047 (verificar con una instalación nueva).
- Revisar las versiones de `requirements.txt` de vez en cuando, a propósito y con las pruebas en verde.

### Seguridad básica
- Rotar claves cada cierto tiempo y no pegarlas en chats ni capturas.
- Correr `python scripts/check_security.py` después de cada migración nueva.

---

## 3. Fuera del alcance (no hacer)

- Conectar con sistemas de proveedores, enviar mensajes o correos automáticamente, o notificaciones en tiempo real: no hay servicio real detrás.
- Registrar pagos, tarjetas o cuentas, ni «marcar como pagada» una cuota: el sistema no maneja dinero (las cuotas son solo información).
- Lectura de códigos con la cámara, firma electrónica, facturación electrónica o consulta automática a SUNAT.
- Una orden única con líneas de varios proveedores: cada proveedor necesita su documento, IGV, pago y recepción. El **pedido PD-** ya da la sensación de una sola ficha sin romper eso.
- Varios almacenes o varios administradores: el sistema se diseñó para uno de cada uno.
- Seguimiento de avance de obra con fotos o gestión de personal más allá de la asistencia: no es parte del almacén.
