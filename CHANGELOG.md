# Registro de cambios

Historial de parches del Sistema MRP (Streamlit + Supabase): qué se agregó, qué se corrigió, los problemas que aparecieron y cómo se resolvieron. La versión vigente se muestra al pie del menú lateral («Sistema MRP · parche NNN») y vive en `core/version.py`.

Formato de cada parche: **Agregado** · **Corregido** · **Problemas y causa** · **Hay que hacer** (acciones fuera del código).

---

## Parche 072 — Un pedido, una ficha: varios proveedores juntos · 2026-10-22

Cuando un pedido junta materiales de varios proveedores, ahora queda como **un solo pedido con un código (PD-0001)** y una sola ficha, en lugar de órdenes sueltas.

**Agregado**
- «Crear pedido (N proveedores)»: el sistema genera el pedido PD-NNNN y, dentro, una orden por proveedor (cada una conserva su PDF para enviárselo, su IGV, su forma de pago y su recepción, porque dependen del proveedor).
- En la lista, las órdenes de un pedido aparecen juntas en **una tarjeta** con el total general y los estados; «Ver pedido» abre la ficha con todos los materiales agrupados por proveedor, el total del pedido y el **PDF del pedido**.
- Cada orden dice a qué pedido pertenece y tiene el botón «Ver el pedido completo».

**Hay que hacer:** correr `db/migrations/047_pedido_varios_proveedores.sql` en el SQL Editor de Supabase (agrega `purchase_orders.batch_code`). Sin ese SQL las órdenes de un solo proveedor funcionan igual; crear un pedido con varios proveedores avisará que falta correrlo.

## Parche 071 — Un pedido con varios proveedores · 2026-10-22

Al crear una orden, cambiar de proveedor ya no borra lo agregado: el pedido es un carrito agrupado por proveedor y al crearlo se genera **una orden por proveedor**.

**Agregado**
- Cambiar de proveedor conserva los materiales ya elegidos; el selector indica cuántos materiales lleva cada uno («Sodimac · 2 en el pedido»).
- **Condiciones por proveedor**: fecha prometida, moneda, IGV y forma de pago se guardan para cada uno y se recuperan al volver.
- «Comparar cotizaciones» muestra cada proveedor con su precio, si es el más barato y cuánto menos/más cuesta, con el botón **Agregar desde aquí** que cambia de proveedor con ese material ya elegido.
- Cada línea tiene **Mover a otro proveedor** (con su precio y la diferencia); si el destino ya tenía el material, suma cantidades.
- «Revisa y crea» muestra una tarjeta por proveedor con su IGV y su plan de pagos, el total de todas las órdenes y el botón «Crear N órdenes».
- El aviso de presupuesto de la obra suma todas las órdenes del pedido.

## Parche 070 — Orden de compra más exacta: IGV claro, pagos en cuotas y PDF por pago · 2026-10-21

Se rehízo el formulario «Nueva orden de compra» a partir de los errores señalados.

**Agregado**
- **IGV en dos opciones claras**: «Se suma 18 % de IGV a los precios» o «Los precios ya incluyen IGV». Antes aparecía una tercera opción confusa.
- **Forma de pago**: contado, contra entrega, crédito a un plazo o **en cuotas** (de 2 a 24, mensuales/quincenales/semanales, primera cuota a 0–60 días, inicial opcional). El sistema calcula importes y vencimientos (la última cuota absorbe los céntimos).
- **PDF por pago**: aviso de cada pago («OC-…-P1», «P2»…) y **cronograma** completo, desde el primero hasta el último. La orden y el texto de WhatsApp incluyen el plan.
- Ficha del material elegido, tarjetas de «Precio unitario» y «Subtotal», líneas del pedido como tarjetas y resumen con la etiqueta de IGV.

**Corregido**
- El precio unitario ya no es un campo gris con +/−: es una tarjeta (viene del catálogo del proveedor).
- La lista de materiales no se reduce al agregar uno (claves estables y reinicio al cambiar de proveedor).
- Se quitó «Este mismo pedido con otros proveedores» del formulario; se conserva «Comparar cotizaciones» por material.
- La unidad de la línea es la principal del material (kg, m, unid.), no la lista completa.

## Parche 069 — Búsqueda de direcciones más precisa · 2026-10-21

La búsqueda de la ubicación de una obra seguía siendo la de OpenStreetMap «a secas». Se midió contra 24 lugares conocidos del Perú escritos como los escribiría una persona (con abreviaturas, sin tildes, con errores): **antes acertaba a la primera 12 de 24 y ahora 18 de 24; entre los candidatos mostrados, de 14 a 21.**

**Qué cambió**
- Se busca **solo en Perú** (antes un «Plaza de Armas» o «Av. Venezuela» podía caer en otro país).
- **Variantes de la misma dirección** cuando la primera no responde: abreviaturas expandidas (Av., Jr., Cdra., Urb., Mz., Sta., Gral.), sin el nombre del local, sin el número de puerta y asumiendo Lima si no se escribe ciudad.
- **Segundo buscador de respaldo (Photon)**, también con datos de OpenStreetMap, que tolera errores de escritura y prioriza lo cercano a Lima.
- **Orden de los candidatos:** primero el que trae el número de puerta escrito y, si no se nombra otra ciudad, los del área de Lima (nunca se descarta ninguno).
- Alias de lugares con otro nombre en el mapa (p. ej. la Plaza de Armas de Lima es «Plaza Mayor»).
- Respeta el límite de 1 consulta por segundo de OpenStreetMap, recuerda los resultados para no repetirlos y no memoriza como «no existe» un corte de internet.
- `scripts/probar_direcciones.py`: banco de pruebas para medir el buscador y afinarlo con tus propias obras. Pruebas sin red en `tests/test_geocode.py`.

**Límite que sigue:** si OpenStreetMap no tiene los números de puerta de una zona, solo conoce el eje de la calle y el punto cae a unos cientos de metros; ahí lo exacto sigue siendo pegar el enlace de Google Maps o las coordenadas.

---

## Parche 068 — Mensajes de WhatsApp para trabajadores y mejor formato · 2026-10-21

**Qué cambió**
- **Mensajes propios para trabajadores:** el botón WhatsApp de cada trabajador ya no ofrece lo de los proveedores (pedir catálogos o cotizaciones no tiene sentido con alguien de tu equipo). Ahora despliega siete mensajes de trato de «tú»: convocar a trabajar, recordar la asistencia, cambio de obra o turno, material listo en almacén, aviso de seguridad, pedir el reporte del día y pedir documentos. Llevan la obra y el puesto del trabajador, y solo tienen Llamar y WhatsApp (no correo).
- **Mejor formato en todos los mensajes:** WhatsApp con el título en *negrita*, saludo, párrafos, listas con sangría y viñetas, datos con su campo en negrita y «____» donde falta completar, despedida y firma en _cursiva_. El correo (Gmail, Outlook, app del equipo) va en texto limpio con la misma sangría y «Saludos cordiales». Los de proveedores pasan a trato de «usted» y piden los datos concretos (precio, plazo, pago, pedido mínimo…).
- Pruebas: opciones distintas por público, formato por canal y que a un trabajador nunca se le ofrezca nada de cotizaciones.

---

## Parche 067 — Logotipo de proveedores y botones de contacto · 2026-10-21

**Agregado**
- **Logotipo del proveedor:** al crear o editar un proveedor se puede subir una imagen (PNG, JPG o WEBP, hasta 4 MB). Se reduce sola a 160 px, conserva la transparencia y la proporción, y se guarda dentro del propio registro. Se ve en su tarjeta, en su ficha y en la **orden de compra en PDF** (arriba a la derecha de la tarjeta del proveedor). Hay opción de quitarlo y el historial anota «con/sin logotipo».
- **Botones de contacto con diseño propio:** **Llamar** en celeste, **WhatsApp** en verde con su logo, y el correo dividido en **Gmail** (rojo) y **Outlook** (azul), cada uno con el logo de su aplicación, destello al pasar el cursor y menú animado.
- **Mensajes preestablecidos:** WhatsApp, Gmail y Outlook se despliegan con seis mensajes listos: solicitar cotización, consultar disponibilidad, pedir lista de precios, seguimiento de un pedido, coordinar entrega en obra y pedir factura o comprobante. Saludan por el nombre de la persona de contacto y firman con la empresa. Al elegir uno se abre la aplicación con el texto escrito; el sistema no envía nada. Outlook además ofrece abrir la app de correo del equipo.
- Un celular de 9 dígitos (sin código de país) abre WhatsApp con el 51 de Perú.

**Hay que hacer:** correr `db/migrations/046_logo_proveedor.sql` en el SQL Editor de Supabase (agrega la columna `suppliers.logo`). Sin ese SQL todo lo demás funciona, pero al guardar un logotipo avisará que falta correrlo.

---

## Parche 066 — Sellos nuevos y mejor espaciado en los PDF · 2026-10-21

**Qué cambió**
- **Sello rectangular rediseñado:** doble borde, icono en un círculo (✓, o ✕ si la orden está cancelada), la palabra grande y debajo una línea chica con el código y la fecha. Va inclinado y más visible que antes, sin tapar lo de abajo. En la orden de compra se **centra en el hueco que deja el cuadro de totales** (antes quedaba pegado a la línea de la tabla).
- **Sello redondo de almacén** en el vale de salida: anillos, icono arriba, «ENTREGADO» en una banda y la fecha abajo, **estampado sobre la firma de quien entrega** (como un sello real) en lugar de flotar entre la tabla y la nota.
- **Espaciado:** más aire entre la tabla, la nota y las firmas del vale; el sello ya no toca el rótulo de la firma; el texto de la tarjeta «Avance» del reporte de obra se acortó para que no se corte.
- Pruebas: tamaño y centrado del sello, que no mueva el cursor, que el sello redondo ajuste cualquier palabra y que las firmas con sello pasen enteras a la página siguiente cuando no caben.

---

## Parche 065 — PDF: gráficos, seguimiento y valores en dos líneas · 2026-10-21

**Qué cambió**
- **Valores largos en dos líneas:** el «Tratamiento del IGV» (y cualquier dato largo de las tarjetas) ya no se corta con «…»: pasa a dos líneas y su fila crece lo justo.
- **Orden de compra:** barra de **Seguimiento del pedido** (Emitida → Enviada → Recepción con % → Pago pactado) y marca de agua diagonal «CANCELADA» en todas las páginas cuando corresponde. Ajustes de espacio para que siga cabiendo en una página.
- **Vale de salida:** columna **Verif.** con casillas para marcar al revisar el material.
- **Reporte de obra:** tarjeta con **comparación de importes** (presupuesto, pedido, recibido, despachado) en barras y un **anillo** con el % despachado.
- **Kardex:** gráfico de línea con la **evolución del saldo** (mínimo y máximo marcados).
- **Reporte general:** **índice** al inicio con cada sección, su número y cuántos registros trae.
- Piezas nuevas en `BrandPDF`: `donut`, `hbars`, `linechart`, `timeline`, `index_card` y `watermark`. Pruebas con valores extremos (sin datos, un solo punto, línea plana, fracciones fuera de rango).

---

## Parche 064 — PDF con identidad propia por tipo de documento · 2026-10-21

Antes todos los PDF eran la misma plantilla en violeta. Ahora cada familia de documentos tiene su color y su portada.

**Qué cambió**
- **Orden de compra** (violeta, franja con círculos): sello inclinado con su estado («Recibida parcial», «Pendiente»…) junto a los totales.
- **Vale de salida** (verde azulado, talonario): franja con muescas, **código de barras Code 39** con el número del vale (lo lee cualquier lector), línea de corte, filas con separador punteado y sello «Entregado».
- **Reporte del sistema** (azul, póster): título grande, barras de gráfico decorativas y datos del reporte en etiquetas.
- **Reporte de obra** (ámbar, obra): franja de peligro con rayas, nombre de la obra en grande; la franja también acompaña las páginas siguientes.
- **Kardex** (verde, libro mayor): encabezado sobrio con barra de color, tabla de líneas finas y **entradas en verde / salidas en rojo**; en el reporte general también colorea «Diferencia» según su signo.
- Piezas nuevas en `BrandPDF`: temas, estilos de portada, `barcode`, `stamp`, `hazard`, `dashed` y tres estilos de tabla (zebra, líneas, talonario).
- Pruebas: todas las combinaciones de tema y portada se generan, el sello no mueve el cursor y el código de barras usa los patrones estándar.

---

## Parche 063 — Hora de Perú y segunda pasada de interfaz · 2026-10-21

**Qué cambió**
- **Hora de Perú:** todo el sistema usa la hora de Lima (UTC−5), que no depende del servidor ni del horario de verano. «Hora del sistema», los PDF y reportes («Generado el…»), el historial, los vales, las recepciones, el kardex y los «hace 5 min» ya no salen con 5 horas de diferencia. Las marcas guardadas en UTC se convierten al mostrarse. Módulo `utils/clock.py` y un test que impide volver a leer el reloj del servidor.
- **Encabezados con icono:** cada pantalla lleva un azulejo con el icono de su módulo; los rótulos y paneles llevan icono según su tema.
- **Más iconos:** pestañas, botones (nuevo, guardar, cancelar, ver, limpiar, dar acceso…) y rótulos con icono Material; las secciones de formulario llevan su número en una insignia.
- **Más movimiento:** números enteros que «suben» hasta su valor, filas de listas en cascada, bloques que aparecen al desplazarse, barra de progreso superior mientras carga, lo anterior se atenúa mientras se recarga, destellos del botón principal y acciones por fila con color (eliminar rojo, editar azul, ver verde azulado).

---

## Parche 062 — Interfaz remasterizada: iconos, movimiento y acceso renovado · 2026-10-21

**Qué cambió**
- **Sin emojis:** todos se sustituyeron por iconos vectoriales propios que toman el color del tema (tarjetas, estados vacíos, línea de tiempo, enlaces, avisos y botones usan iconos Material). Un test impide que vuelva a colarse un emoji sin icono.
- **Valores con color según su signo:** el saldo del presupuesto, las diferencias de inventario y el kardex (entradas en verde, salidas en rojo) cambian de color con el valor; ceros y vacíos quedan neutros.
- **Movimiento:** una sola «sensación» (curvas, duraciones y ~25 animaciones) en `05_motion.css`: entrada en cascada de cada pantalla (se reproduce al navegar, no en cada clic), tarjetas que se elevan, brillo en los botones primarios, menú con indicador que se desliza, pestañas, desplegables, diálogos, avisos que vibran si son errores, gráficos con transición. Todo se apaga con «reducir movimiento» del sistema.
- **Pantalla de carga nueva:** marca que se dibuja sola, anillos giratorios, barra con brillo, porcentaje y mensajes que cambian, todo en CSS (sin saltos).
- **Acceso renovado:** panel de marca con malla de color animada, órbitas, tarjetas que entran en cascada y contador de proveedores; formulario de cristal con entrada escalonada.
- **Sistema visual:** nuevas variables (acento secundario, cristal, anillo de foco, rejilla), hero con aurora animada, tarjetas con halo y raya que crece, sidebar con brillo y marca animada, gráficos con paleta propia (sin el recuadro oscuro del treemap).
- Pruebas nuevas en `tests/test_visual_system.py`.

---

## Parche 061 — Manual de usuario ilustrado · 2026-10-21

El colaborador aportó el módulo «Manual de Usuario» (solo texto en pestañas y desplegables). Se rediseñó para que se vea como el resto del sistema y se entienda de un vistazo.

**Qué cambió**
- **Capítulos con selector** (Empezar, Preparar los datos, Pedir material, Almacén, Obras y personal, Control y respaldo, Preguntas y glosario) y **buscador** que ignora tildes.
- **Maquetas fieles de los formularios** en cada procedimiento (~26): campos, botones, tablas y resúmenes dibujados como en el sistema, con **números** que remiten al paso que los explica.
- **Tarjetas ilustradas:** recorrido de una compra, lo que el sistema sí y no hace, ruta para empezar, estados de las órdenes y glosario.
- **Textos corregidos:** se quitaron expresiones imprecisas («compra formal», «emitir el documento»); el manual dice que el sistema no compra ni paga ni se conecta con el proveedor.
- **Exactitud comprobada por tests:** cada etiqueta, botón y columna de las maquetas debe existir en el código del módulo que la dibuja (`tests/test_manual.py`).
- Se restauró `import streamlit as st` en `core/shell.py` (el alias `str_lit` del merge) y la ayuda de contraseña del primer administrador ahora dice 8 caracteres con letras y números.

---

## Parche 060 — Ventanas de ayuda «Cómo usar» renovadas · 2026-10-16

La ayuda de cada pantalla era un cuadro pequeño con un muro de texto y numeración rara («3a0», «3b1»). Ahora es una ventana propia, ordenada y clara.

**Qué cambió**
- **Ventana en lugar de globo:** el botón **Cómo usar** (con icono, en forma de píldora) abre una ventana grande con encabezado de color (icono, nombre de la pantalla, para qué sirve y cuántos pasos tiene).
- **Tres pestañas:** **Paso a paso**, **Ejemplo** y **Consejos y avisos**.
- **Paso a paso con línea de tiempo:** los pasos van agrupados por tarea («Parte 2 de 5 · Comunicarla al proveedor»), numerados de corrido (1, 2, 3…), con un título corto, una explicación breve y una etiqueta **dónde está** (por ejemplo «Botón de arriba a la derecha»).
- **Ejemplo real** contado en pocos pasos (pedir 120 bolsas de cemento, despachar a una obra, importar una lista de precios…).
- **Consejos, avisos y «lo que el sistema no hace»** en tarjetas de colores distintas (azul, ámbar y verde azulado). Queda dicho en las pantallas que corresponde que el sistema no se conecta con el proveedor, no compra y no paga.
- **Estilo nuevo** (`modules/styles/45_help.css`): tarjetas con bordes redondeados y sombra suave, degradado de la marca, números con degradado, animación al pasar el mouse, funciona en **modo claro y oscuro** y en pantallas angostas, y respeta «reducir movimiento».
- **Iconos vectoriales** dibujados (`utils/icons.py`), los mismos de los PDF: no dependen de internet ni de fuentes.
- **Guías reescritas** para las 12 pantallas con frases cortas y orden lógico: por ejemplo, Órdenes de compra pasó de una lista de 20 viñetas mezcladas a 5 partes (armar el pedido, comunicarla al proveedor, cuando llega el material, corregir o cerrar, y ayuda para decidir) con 14 pasos.
- Las guías ahora son datos estructurados (`modules/guides.py`), no texto suelto.

**Problema que se encontró al probarlo en el navegador:** Streamlit da a las listas del Markdown un ancho «ajustado al contenido» con más fuerza que cualquier clase, y las tarjetas de una misma guía salían de anchos distintos. Se fuerza el ancho completo y hay una prueba que lo vigila.

**Pruebas nuevas (12):** toda pantalla tiene guía y todo `page_header` del código resuelve a una; estructura completa (icono válido, pasos con título y texto cortos, sin numeración escrita a mano); formato en línea seguro (se escapa el HTML); numeración continua entre partes; ejemplo y avisos; que no quede Markdown sin convertir; que exista el estilo de cada clase; y el ancho completo de las listas.

**Hay que hacer:** nada (no hay SQL nuevo).

## Parche 059 — Corrección de lenguaje: el sistema prepara pedidos, no compra · 2026-10-16

**Aclaración (definitiva):** una orden de compra en el sistema **no es una transacción**: no se conecta con el sistema ni la base de datos del proveedor, no compra y no maneja dinero. Sirve para llegar a la **exactitud del trato, con el IGV**, de modo que al hacer la compra (por fuera) se sepa cuánto es. El sistema solo maneja datos: qué se pide a cada proveedor, qué entra al almacén y qué sale a cada obra.

**Se corrigió lo que decía otra cosa**
- «Comprado hasta hoy», «Comprado» y «Comprado S/» (Obras y reporte de obra en PDF) volvieron a **«Pedido»**: afirmaban una compra hecha.
- En el dashboard, «Compras por mes / por categoría / por proveedor» pasó a **«Valor de los pedidos por mes», «Pedidos por categoría» y «Pedidos por proveedor»**.
- «Pagar a más tardar» pasó a **«pago pactado hasta el…»** (es lo acordado con el proveedor, no una orden de pago).
- El módulo **Sistema**, las guías y el README ahora explican qué hace y qué no hace: no se conecta con el proveedor, no compra y no paga; el flujo dice «se arma el pedido con su valor exacto (con IGV) y se comunica al proveedor por WhatsApp, correo o llamada», «lo recibido entra al stock» y «sale hacia la obra».
- Nuevo apartado «Qué hace y qué no hace el sistema» en el README.

**Se dejó igual (sigue siendo coherente):** IGV 18 % y valor de venta / IGV / importe total, RUC de la empresa con contraseña, «Facturar a» en la orden, condición de pago informativa, recepción contra guía o factura, almacén, despacho, devoluciones, conteos, kardex, reportes y el resto.

**Hay que hacer:** nada.

## Parches 056–058 — Datos de la empresa (RUC), IGV real y condición de pago · 2026-10-16

El sistema no paga nada: las compras se pagan fuera, con el RUC de la empresa. Estos cambios hacen que las órdenes se parezcan a una compra real.

**Parche 056 · Datos de la empresa y RUC con contraseña**
- **Mi cuenta** ahora tiene dos pestañas (la segunda solo para el administrador): **Contraseña** y **Empresa y RUC**. Los datos de facturación (razón social, nombre comercial, RUC, dirección fiscal) **no se ven hasta ingresar la contraseña de la sesión** (la del Administrador). Comparte el bloqueo por intentos fallidos del inicio de sesión (5 intentos, 15 min). Tras ingresarla se muestran 3 minutos y hay un botón «Ocultar»; se vuelven a ocultar al reabrir «Mi cuenta».
- El **RUC se valida** con el dígito verificador de SUNAT (11 dígitos, empieza con 10, 15, 17 o 20) y se informa el tipo de contribuyente. En el **Historial** solo queda «RUC: (oculto) → (oculto)»: el número no se escribe ahí porque allí se vería sin contraseña.
- **RUC del proveedor** (validado igual) en su formulario, su ficha y los reportes.
- La **orden de compra en PDF** trae ahora «Facturar a» (razón social, nombre comercial, RUC y dirección fiscal de la empresa) y el RUC del proveedor; el mensaje de WhatsApp/correo incluye «Facturar a: … · RUC …». Es el dato que el proveedor necesita para emitir la factura.

**Parche 057 · IGV real y condición de pago**
- **IGV 18 %** (16 % IGV + 2 % IPM) con tres tratamientos por orden: los precios **no incluyen** IGV (se suma, por omisión), **ya lo incluyen** (se separa: valor de venta = total ÷ 1,18) o **sin IGV** (exonerada o inafecta).
- Importes como en una factura: **valor de venta, IGV e importe total**, redondeados a céntimos con el .5 hacia arriba (15.75 + 18 % = 15.75 + 2.84 = 18.59). Se ven así al armar la orden, en su detalle, en el PDF, en el mensaje, en el reporte de órdenes (con «Condición de pago») y en la sugerencia de compra.
- **Condición de pago informativa:** Contado, Contra entrega o Crédito de 7, 15, 30, 45 o 60 días, con la **fecha límite de pago** calculada. Solo informa a tesorería.
- Las compras en dólares y las que ya traen IGV se convierten a soles correctamente en el dashboard; la gráfica «Compras por categoría» usa el mismo criterio que «Compras por mes» (soles e IGV de cada orden). El presupuesto de obra sigue comparando sin IGV.
- Las órdenes nuevas nacen con IGV 18 % sumado (antes sin IGV).

**Parche 058 · Cierre**
- La ayuda de las contraseñas decía «al menos 6 caracteres» pero la política es de 8 con letras y números: ahora dice lo mismo que se exige.
- **Pruebas nuevas (24):** RUC (validador con RUC reales, casos del dígito 10 y 11), IGV (sumado, incluido, exonerado, dólares, céntimos), condición de pago y vencimiento, ficha de la empresa (una sola fila, RUC inválido rechazado, respaldo), RUC de proveedores, PDF y mensaje con RUC e IGV; y 2 pruebas SQL en Postgres real (una sola ficha de empresa, RUC de 11 dígitos, y que nazca cerrada en una base cerrada). Comprobado en navegador real: Mi cuenta oculta el RUC hasta la contraseña, el formulario de orden con IGV y condición de pago, y el módulo Sistema.

**Hay que hacer**
- Correr `db/migrations/045_empresa_igv.sql` en Supabase (tabla `company_profile`, columna `ruc` de proveedores y `prices_include_tax` y `payment_terms` de las órdenes). Antes de eso todo sigue funcionando (las órdenes con IGV sumado y sin condición de pago se guardan igual); guardar el RUC, «precios con IGV incluido» o una condición de pago avisa que falta el SQL.
- Cargar en «Mi cuenta → Empresa y RUC» la razón social y el RUC de la empresa.

## Parche 055 — El dinero es compra, no pérdida, y nuevo módulo Sistema · 2026-10-16

**Aclaración del sistema:** el sistema no cobra ni paga nada (no usa tarjetas ni cuentas). Las compras las paga el administrador por fuera, con el RUC de la empresa; el sistema registra lo comprado para consulta y para tesorería.

**Cambios**
- **Lenguaje:** se quitó todo lo que sonaba a dinero perdido. «Gasto mensual / por categoría / por proveedor» pasó a «Compras por mes / por categoría / por proveedor» («En qué tipo de material se compra más» en lugar de «se va el dinero»); «Pedido hasta hoy» → «Comprado hasta hoy»; «Disponible» → «Saldo del presupuesto»; «Materiales excedidos» y «Excede lo previsto» → «Sobre lo presupuestado»; «ahorrarías» → «costaría menos». Lo que supera el presupuesto ya no se pinta de rojo: es un aviso ámbar de presupuesto, no una pérdida. La columna interna «Gasto pedido $» se llama ahora «Pedido $».
- **Módulo Sistema** (último grupo del menú, visible para todos): versión desplegada, base de datos y seguridad (protegida / abierta / prueba), hora del sistema, para qué sirve, cómo fluye una compra (proveedor → orden → recepción → almacén → despacho), cuántos registros hay, las últimas novedades leídas del CHANGELOG y un resumen técnico para copiar al pedir soporte (sin contraseñas ni claves). Incluye la aclaración de que el pago se hace fuera del sistema.
- Guías actualizadas.

**Pruebas nuevas (4):** lectura del changelog, variantes del formato, resumen técnico sin secretos y flujo.

**Hay que hacer:** nada (no hay SQL nuevo).

## Parche 054 — Nuevo diseño de los PDF · 2026-10-16

Todos los PDF del sistema (orden de compra, vale de salida, reportes, reporte de obra y kardex) comparten ahora un mismo diseño con la identidad de la app (`utils/pdf_style.py`).

**Qué cambia**
- **Tipografía Inter** (la misma de la app), incluida en el proyecto (`utils/fonts/`, licencia SIL OFL), con acentos, ñ y los caracteres que antes se perdían: guiones largos, viñetas, flechas, ✓, ≥, ×, №, €… Los textos largos se recortan con «…» y no se montan unos sobre otros (antes «Entrega prometida:» se pisaba con su valor).
- **Portada** de color con el tipo de documento, el código en grande, los datos clave a la derecha y una etiqueta de estado (Pendiente, Enviada, Recibida parcial, Recibida, Cancelada; o la etapa en un vale).
- **Iconos vectoriales dibujados** (no emojis ni fuentes de iconos): orden, camión, caja, edificio, persona, teléfono, correo, calendario, moneda, ubicación, reloj, balanza, gráfico, capas y más.
- **Tarjetas** con los datos del proveedor y de la entrega (orden), del despacho (vale), cifras clave con barra de avance (reporte de obra).
- **Tablas** con encabezado de color, filas alternadas, números alineados a la derecha, numeración, encabezado repetido en cada página y etiquetas de color en las celdas de estado (recibido completo o parcial, excede lo previsto, fuera de presupuesto, completo…).
- **Orden de compra:** columna «Recibido», cuadro de totales con subtotal, IGV y total destacado, equivalente en soles si es en dólares, notas en un recuadro y firmas con el nombre del proveedor.
- **Vale de salida:** datos del despacho (obra, etapa, solicitante, quién lo registró, fecha y hora), nota, **tres firmas** (entrega, recibe y V.° B.° de obra) y una leyenda de conformidad.
- **Reporte de obra:** seis cifras (presupuesto, pedido, recibido, despachado, disponible y avance), tabla de materiales con su estado, **barras de avance por etapa** y vales.
- **Todas las páginas:** pie con fecha y hora de generación, versión del sistema y «Página X de Y»; encabezado fino en las páginas siguientes.
- Armar un PDF toma unos 100 ms.

**Pruebas nuevas (9):** fuentes incluidas, recorte y partido de textos, iconos, caracteres Unicode, tablas de varias páginas, y cada documento con datos completos, casi vacíos, muy largos o con valores faltantes.

**Hay que hacer:** nada (no hay SQL nuevo).

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
La lista vigente de lo que falta y de las mejoras propuestas está en [MEJORAS.md](MEJORAS.md). Resumen:
- Las obras ya guardadas no se pueden editar (para corregir su ubicación hay que borrarlas y crearlas de nuevo).
- Un pedido con varios proveedores (PD-) no tiene todavía acciones conjuntas (cancelar o enviar todas sus órdenes a la vez).
- El rol Operador tiene permisos amplios (ve todo menos Trabajadores, Historial y Respaldo).
- La recepción de una orden no valida cantidades en la capa de datos (la pantalla sí limita lo que se puede recibir).
- Ubicar por dirección es aproximado (OpenStreetMap); para el punto exacto pega el enlace de Google Maps.
- Seguridad: la base se cierra con la clave de servicio (parche 041); define `SESSION_SECRET` y rota las claves si alguna se filtra.

**Técnicos**
- Hasta el parche 034, tras editar un `.css` había que reiniciar Streamlit; desde el 035 se recargan solos.
- Los gráficos Plotly usan píxeles; su altura se ajusta con un script (`form_assist.py`) al cargar y al redimensionar.
