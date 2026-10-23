"""Guías de uso por módulo: el botón «Cómo usar» que aparece junto al título de cada pantalla.

Cada guía es un dato (no un texto suelto) para que la ventana de ayuda las dibuje siempre igual:

    icon       nombre de un icono de `utils/icons.py`
    summary    una frase: para qué sirve la pantalla
    sections   grupos de pasos (cada uno con título); cada paso lleva `title`, `text` y, si ayuda, `where` (dónde está)
    example    un caso real contado en pocos pasos: {"title", "steps": [...]}
    tips       consejos útiles
    warnings   avisos de cosas que conviene saber antes de actuar
    not_does   lo que el sistema NO hace (para evitar malentendidos)

En los textos, `**así**` es negrita y `` `así` `` es código. Se buscan por el título de la página."""
from __future__ import annotations

GUIDES: dict[str, dict] = {
    "Dashboard": {
        "icon": "chart",
        "summary": "Una lectura rápida de cómo va todo: qué está abierto, qué falta y qué necesita tu atención hoy.",
        "sections": [
            {
                "title": "Qué verás en esta pantalla",
                "steps": [
                    {"title": "Las tarjetas de arriba", "text": "Cuentan los **materiales** del catálogo, los que tienen **stock** en el almacén, los que están en o bajo su **stock mínimo**, las **órdenes abiertas** y los **despachos del mes**.", "where": "Parte superior"},
                    {"title": "Los accesos rápidos", "text": "Cuatro botones para lo que más se hace: **Nueva orden**, **Pasar lista**, **Despachar material** y **Ver obras**. Te llevan directo a cada pantalla."},
                    {"title": "Los avisos", "text": "Un aviso **amarillo** señala órdenes abiertas hace muchos días o materiales con stock bajo. Un aviso **rojo** señala órdenes que ya pasaron su fecha prometida de entrega."},
                    {"title": "Los gráficos", "text": "El **valor de los pedidos por mes**, por **categoría** y por **proveedor**, y las órdenes **por estado**. Son los importes exactos de las órdenes no canceladas, con IGV."},
                    {"title": "El mapa y la actividad", "text": "El mapa muestra las obras que tienen ubicación. Abajo ves lo último que se agregó al sistema."},
                ],
            }
        ],
        "example": {"title": "Ves «3 órdenes atrasadas»", "steps": ["Pulsa **Órdenes de compra** en el menú.", "Abre la orden marcada como atrasada.", "Llama o escribe al proveedor desde su ficha y pregunta por la entrega."]},
        "tips": ["El límite de días para el aviso amarillo se cambia en **Órdenes de compra**, en el campo «Avisar tras (días)».", "Pulsa **Actualizar datos** en el menú lateral si otra persona acaba de hacer cambios."],
        "not_does": ["Los importes son el valor de los **pedidos**: el sistema no compra ni paga. Eso se hace fuera, con el RUC de la empresa."],
    },
    "Proveedores": {
        "icon": "truck",
        "summary": "Tener a la mano a quién llamar, qué vende cada proveedor y a qué precio, para comparar y pedir bien.",
        "sections": [
            {
                "title": "Registrar un proveedor",
                "steps": [
                    {"title": "Crea la ficha", "text": "Pulsa **＋ Nuevo proveedor** y escribe su nombre. Es lo único obligatorio. Si quieres, sube su **logotipo** (PNG, JPG o WEBP): se reduce solo y sirve para reconocerlo de un vistazo.", "where": "Botón de arriba a la derecha"},
                    {"title": "Agrega cómo contactarlo", "text": "Escribe el teléfono (un celular de 9 dígitos o con código de país, por ejemplo `51987654321`), el correo y la persona de contacto. En su tarjeta tendrás **Llamar** (celeste), **WhatsApp** (verde), **Gmail** y **Outlook**."},
                    {"title": "Usa los mensajes ya escritos", "text": "WhatsApp, Gmail y Outlook se despliegan con mensajes listos: solicitar cotización, consultar disponibilidad, pedir lista de precios, seguimiento de un pedido, coordinar entrega o pedir un comprobante. Al elegir uno se abre la aplicación con el texto escrito, con título, sangría y datos por completar; tú lo revisas y lo envías."},
                    {"title": "Anota su RUC y sus condiciones", "text": "El **RUC** (11 dígitos; el sistema comprueba que esté bien escrito) sale en la orden de compra. El **plazo de entrega** y el **monto mínimo de compra** ayudan a la sugerencia de compra."},
                ],
            },
            {
                "title": "Cargar su catálogo y sus precios",
                "steps": [
                    {"title": "Abre su catálogo", "text": "En la tarjeta del proveedor pulsa **Catálogo**.", "where": "Tarjeta del proveedor"},
                    {"title": "Marca lo que vende", "text": "Para cada material marca **Lo ofrece**, indica si está **Disponible** y escribe su **precio**. Se guarda solo, sin botón.", "where": "Lista de materiales del catálogo"},
                    {"title": "O importa su lista de precios", "text": "Pulsa **Importar precios** y sube el Excel o CSV que te mandó. Verás qué cambia **antes** de aplicarlo. Si tu archivo no tiene formato, descarga la plantilla.", "where": "Botón dentro del catálogo"},
                ],
            },
            {
                "title": "Mantener todo al día",
                "steps": [
                    {"title": "Revisa la vigencia", "text": "Cada precio muestra cuándo se actualizó. Pasados **90 días** (se ajusta) aparece como vencido. El filtro **Precio vencido** lista lo que conviene volver a cotizar."},
                    {"title": "Mira su calificación", "text": "Cada proveedor recibe una nota de **0 a 100**: 60 % por entregar a tiempo y 40 % por entregar las cantidades completas. Aparece en la lista y en su ficha."},
                ],
            },
        ],
        "example": {"title": "Llegó la lista de precios de Ferretería Norte", "steps": ["Entra a **Proveedores** y abre **Catálogo** de Ferretería Norte.", "Pulsa **Importar precios** y sube su Excel.", "Revisa la tabla de cambios y aplícala.", "Los precios nuevos ya sirven para las órdenes y la sugerencia de compra."]},
        "tips": ["Cada cambio de precio queda guardado en el historial de precios.", "En la tarjeta del proveedor tienes botones para llamar, escribir por WhatsApp o redactar un correo en Gmail u Outlook, con mensajes ya escritos."],
        "warnings": ["El precio que usa una orden es el del catálogo en ese momento. Si cambia después, las órdenes ya creadas no se tocan."],
    },
    "Materiales": {
        "icon": "box",
        "summary": "El catálogo maestro de todo lo que el almacén puede manejar, tenga o no proveedor.",
        "sections": [
            {
                "title": "Crear y mantener materiales",
                "steps": [
                    {"title": "Agrega un material", "text": "Pulsa **＋ Nuevo material**. La **categoría** y el **nombre** juntos identifican al material: no pueden repetirse.", "where": "Botón de arriba a la derecha"},
                    {"title": "Elige su métrica de cómputo", "text": "Es la unidad en que lo presupuestas, lo pides y lo cuentas (por ejemplo *Volumen (m³)* o *Peso (kg)*). Elígela de la lista; así «m3» y «m³» no quedan como dos cosas distintas."},
                    {"title": "Las existencias no se tocan aquí", "text": "El catálogo solo describe al material. Su stock sube con la **recepción de una orden de compra** o la importación de un proveedor; el **stock mínimo** se define en Inventario."},
                    {"title": "Consulta su ficha", "text": "Pulsa el botón de **información** de un material para ver su densidad, sus precios por proveedor, su stock y en qué obras se usa.", "where": "Botón ℹ️ de cada fila"},
                ],
            }
        ],
        "tips": ["Usa el buscador y el filtro por categoría para encontrar un material entre cientos."],
        "not_does": ["Que un material no tenga proveedor es **normal**: el catálogo es todo lo que puedes almacenar, no solo lo que ya cotizaste."],
    },
    "Órdenes de compra": {
        "icon": "order",
        "summary": "Armar el pedido a un proveedor con su valor exacto (IGV incluido) y seguirlo hasta que el material llega al almacén.",
        "sections": [
            {
                "title": "Armar el pedido",
                "steps": [
                    {"title": "Empieza una orden nueva", "text": "Pulsa **＋ Nueva orden** y elige el **proveedor**. La **obra destino** es opcional; si la eliges, el sistema avisa cuando el pedido supera su presupuesto.", "where": "Botón de arriba a la derecha"},
                    {"title": "Define entrega, IGV y pago", "text": "La **fecha prometida** activa el aviso de atraso. En **IGV (18 %)** eliges cómo cotiza el proveedor: sin IGV (se suma), con IGV incluido (se separa) o exonerado. La **condición de pago** es solo informativa."},
                    {"title": "Agrega los materiales", "text": "Elige un material, escribe la cantidad y pulsa **＋ Agregar al pedido**. El **precio unitario es el del catálogo** y no se cambia aquí: lo que sube con la cantidad es el total."},
                    {"title": "Revisa los importes", "text": "Verás el **valor de venta**, el **IGV** y el **importe total**, como en una factura. Si otro proveedor tiene un material más barato, **Comparar cotizaciones** te deja agregarlo desde ahí sin perder lo anterior: se crea **una orden por proveedor**."},
                    {"title": "Crea la orden", "text": "Pulsa **Crear orden**. Queda en estado **Pendiente**."},
                ],
            },
            {
                "title": "Comunicarla al proveedor",
                "steps": [
                    {"title": "Elige cómo enviarla", "text": "Descarga el **PDF**, o usa **Enviar por WhatsApp** o **Correo**: se abre tu WhatsApp o tu correo con el pedido ya escrito. Tú lo envías.", "where": "Botones debajo del detalle de la orden"},
                    {"title": "Queda anotado el envío", "text": "Al abrir WhatsApp o el correo, una orden pendiente pasa sola a **Enviada** y se guarda la fecha y la hora."},
                ],
            },
            {
                "title": "Cuando llega el material",
                "steps": [
                    {"title": "Registra la recepción", "text": "Abre **Registrar recepción**, escribe lo que llegó de cada línea, el **N.º de guía o factura**, quién entregó y las observaciones (faltantes, daños). Lo recibido **entra al stock del almacén**.", "where": "Dentro de la orden"},
                    {"title": "Si llegó solo una parte", "text": "La orden queda **Recibida parcial**. Cuando llegue el resto, vuelve a registrar la recepción. No se puede recibir más de lo pedido."},
                    {"title": "Guarda los documentos", "text": "En **Documentos adjuntos** sube la foto o el PDF de la factura o de la guía de remisión (hasta 10 MB)."},
                ],
            },
            {
                "title": "Corregir, repetir o cerrar",
                "steps": [
                    {"title": "Editar", "text": "**Editar orden** permite cambiar cantidades, quitar o agregar materiales, la obra y las condiciones, **mientras no haya recibido material**."},
                    {"title": "Duplicar", "text": "**Duplicar** crea otra orden con los mismos materiales, con los precios vigentes del catálogo."},
                    {"title": "Cancelar o eliminar", "text": "**Cancelar orden** cierra un pedido que no sigue. **Eliminar** solo se puede si no recibió nada."},
                ],
            },
            {
                "title": "Ayuda para decidir qué pedir",
                "steps": [
                    {"title": "Sugerencia de compra", "text": "Calcula qué falta según los presupuestos de las obras, el stock y lo que ya viene en camino. Elige el proveedor más barato, avisa si no llega al **mínimo de compra** y crea las órdenes por ti.", "where": "Botón «Sugerencia de compra»"},
                ],
            },
        ],
        "example": {"title": "Pedir 120 bolsas de cemento", "steps": ["**＋ Nueva orden** → elige *Ferretería Norte* y la obra *Torre Central*.", "En IGV deja «Los precios NO incluyen IGV» y elige *Crédito 30 días*.", "Material *Cemento*, cantidad 120 → **Agregar al pedido** → **Crear orden**.", "Pulsa **Enviar por WhatsApp**: la orden pasa a *Enviada*.", "Cuando llegue el camión: **Registrar recepción** con el N.º de guía."]},
        "tips": ["Una orden atrasada se marca en rojo en la lista y en el dashboard.", "Si un precio del catálogo está vencido, el sistema te avisa al agregarlo."],
        "warnings": ["Una orden que ya recibió material **no se puede borrar** (el stock quedaría descuadrado): si no continúa, cancélala."],
        "not_does": ["El sistema **no se conecta con el sistema del proveedor, no compra y no paga**. Prepara el pedido con su valor exacto y lo registra; la compra y el pago se hacen fuera, con el RUC de la empresa."],
    },
    "Inventario": {
        "icon": "box",
        "summary": "Saber qué hay en el almacén, registrar lo que sale hacia las obras y corregir las diferencias.",
        "sections": [
            {
                "title": "Ver qué hay",
                "steps": [
                    {"title": "Stock actual", "text": "Cada material muestra su stock con un color: verde si hay, ámbar si está en o bajo el mínimo, rojo si se agotó. La pestaña tiene buscador.", "where": "Primera pestaña"},
                    {"title": "Cómo entra el material", "text": "Entra con la **recepción de una orden de compra**. También puedes registrar una **entrada** suelta con «Entrada, merma o devolución a proveedor»."},
                    {"title": "Define el stock mínimo", "text": "Pulsa **Stock mínimo**, elige el material y escribe el nivel por debajo del cual conviene reponer. Con él, el tablero avisa y la sugerencia de compra lo repone.", "where": "Botón sobre la lista de stock"},
                ],
            },
            {
                "title": "Sacar material hacia una obra",
                "steps": [
                    {"title": "Empieza el despacho", "text": "Pulsa **＋ Despachar a obra**. Elige la **obra**, quién **solicita** el material y, si la obra tiene etapas, la **etapa**.", "where": "Botón de arriba a la derecha"},
                    {"title": "Agrega los materiales", "text": "Solo aparecen materiales con stock. Elige uno, la cantidad y pulsa **＋ Agregar al vale**. Puedes poner varios en el mismo vale."},
                    {"title": "Confirma y descarga el vale", "text": "Pulsa **Registrar despacho y generar vale**. El stock baja y obtienes un **vale en PDF** para que quien recibe lo firme."},
                ],
            },
            {
                "title": "Cuando algo vuelve o no cuadra",
                "steps": [
                    {"title": "Devolver de una obra", "text": "Si sobra material en una obra, pulsa **Devolver de una obra**: vuelve al almacén y suma al stock. Solo puedes devolver lo que esa obra recibió.", "where": "Botón debajo del título"},
                    {"title": "Toma de inventario", "text": "Cuenta lo que hay en estantería, una categoría a la vez. Escribe lo contado (lo que dejes vacío no se toca) y el motivo de cada diferencia; el stock se ajusta y el conteo queda guardado.", "where": "Botón «Toma de inventario»"},
                    {"title": "Merma o devolución a proveedor", "text": "Con **Entrada, merma o devolución a proveedor** das de baja material dañado o prestado, o devuelves al proveedor lo que llegó mal."},
                ],
            },
            {
                "title": "Consultar el historial",
                "steps": [
                    {"title": "Vales de salida", "text": "Aquí están todos los vales: puedes verlos, reimprimirlos en PDF, enviarlos por correo y adjuntar el vale firmado."},
                    {"title": "Kardex", "text": "Elige un material y verás cada entrada y salida en orden, con el **saldo** después de cada una. Si no coincide con el stock actual, el sistema avisa."},
                    {"title": "Conteos y movimientos", "text": "**Conteos** guarda cada toma de inventario con sus diferencias. **Movimientos** lista todo lo que entró y salió, con fecha y responsable."},
                ],
            },
        ],
        "example": {"title": "Juan Pérez pide 4 m³ de concreto para Torre Central", "steps": ["Pulsa **＋ Despachar a obra**.", "Elige *Torre Central* y como solicitante *Juan Pérez*.", "Material *Concreto*, cantidad 4 → **Agregar al vale**.", "**Registrar despacho y generar vale** → descarga el PDF y haz que Juan lo firme."]},
        "tips": ["Si te pasas del presupuesto de la obra, el sistema avisa, pero no lo impide."],
        "warnings": ["No se puede sacar más de lo que hay en el almacén."],
    },
    "Obras y presupuesto": {
        "icon": "building",
        "summary": "Ver todo de una obra en un solo lugar: su presupuesto, lo pedido, lo recibido y lo que ya se despachó.",
        "sections": [
            {
                "title": "Preparar la obra",
                "steps": [
                    {"title": "Elige la obra", "text": "Usa el selector **Obra** de arriba. Las obras se crean en **Trabajadores → Obras / Proyectos**.", "where": "Parte superior"},
                    {"title": "Define el presupuesto", "text": "En la pestaña **Materiales** pulsa **＋ Material al presupuesto**: cantidad prevista y precio estimado de cada material. Si la obra va por fases, elige o crea la **etapa** (cimentación, estructura, acabados…).", "where": "Pestaña Materiales"},
                ],
            },
            {
                "title": "Seguir la obra",
                "steps": [
                    {"title": "Compara presupuesto, pedido y despacho", "text": "La tabla de **Materiales** muestra, por material, lo presupuestado, lo pedido, lo recibido y lo despachado. Si la obra tiene etapas, un selector deja ver una etapa o todas."},
                    {"title": "Despacha o devuelve desde aquí", "text": "Los botones **Despachar material** y **Devolver material** abren el mismo formulario del Inventario, ya con esta obra elegida."},
                    {"title": "Mira el progreso", "text": "En **Progreso** ves el porcentaje pedido, recibido y despachado. La pestaña **Trabajadores** muestra quién está asignado y sus jornadas."},
                ],
            },
            {
                "title": "Entregar cuentas",
                "steps": [{"title": "Descarga el reporte", "text": "El botón **Reporte de la obra (PDF)** reúne el presupuesto frente a lo pedido, recibido y despachado, por material y por etapa, con los vales. Está listo para imprimir.", "where": "Debajo de las tarjetas, antes de las pestañas"}],
            },
        ],
        "tips": ["Lo que supera el presupuesto se marca como «Sobre lo presupuestado»: es un aviso de presupuesto, no una pérdida."],
    },
    "Asistencia": {
        "icon": "calendar",
        "summary": "Llevar quién fue a qué obra cada día.",
        "sections": [
            {
                "title": "Pasar lista",
                "steps": [
                    {"title": "Elige el día", "text": "Selecciona la **fecha** y, si quieres, filtra por obra."},
                    {"title": "Marca el estado de cada trabajador", "text": "En la tabla cambia **Estado** (presente, tardanza, permiso, ausente) y la **Obra**. «—» significa sin registrar."},
                    {"title": "Completa de una vez", "text": "**Marcar pendientes presentes** pone «presente» a las filas visibles sin estado. Todavía es un borrador."},
                    {"title": "Guarda", "text": "Revisa la lista y pulsa **Guardar asistencia**. Los borradores se conservan al cambiar de fecha o filtro; **Descartar cambios visibles** vuelve a lo guardado."},
                ],
            }
        ],
        "tips": ["La pestaña **Resumen** cuenta asistencias y faltas de los últimos días."],
    },
    "Reportes": {
        "icon": "list",
        "summary": "Sacar la información del sistema a Excel o PDF para compartirla o archivarla.",
        "sections": [
            {
                "title": "Descargar un reporte",
                "steps": [
                    {"title": "Elige el contenido", "text": "«Los básicos» trae lo de siempre. Puedes agregar vales de salida, historial de precios, presupuestos de obra, conteos, recepciones, calificación de proveedores e historial de cambios."},
                    {"title": "Descarga", "text": "**Excel** crea una hoja por conjunto; **PDF** los reúne en un documento con portada y tablas."},
                    {"title": "Revisa la vista previa", "text": "Abajo puedes abrir cada conjunto para comprobar sus datos antes de compartir el archivo."},
                ],
            },
            {
                "title": "Reportes que están en otras pantallas",
                "steps": [
                    {"title": "Reporte de una obra", "text": "En **Obras**, botón **Reporte de la obra (PDF)**.", "where": "Pantalla Obras"},
                    {"title": "Kardex de un material", "text": "En **Inventario → Kardex**, con descarga en Excel y PDF.", "where": "Pantalla Inventario"},
                ],
            },
        ],
    },
    "Trabajadores": {
        "icon": "user",
        "summary": "El personal de obra: cuadrillas, obras y quién puede entrar al sistema.",
        "sections": [
            {
                "title": "Organizar al personal",
                "steps": [
                    {"title": "Crea cuadrillas y obras", "text": "Empieza por las **cuadrillas** y las **obras**. En la obra puedes pegar el **enlace de Google Maps** para guardar su ubicación exacta."},
                    {"title": "Registra a cada trabajador", "text": "Pulsa **＋ Nuevo trabajador**: nombre, documento, teléfono, puesto, cuadrilla y obra.", "where": "Botón de arriba a la derecha"},
                    {"title": "Escríbele por WhatsApp", "text": "En la tarjeta de cada trabajador, **WhatsApp** se despliega con mensajes pensados para tu equipo: convocar a trabajar, recordar la asistencia, cambio de obra o turno, material listo en almacén, aviso de seguridad, pedir el reporte del día o pedir documentos. Ya llevan su obra y su puesto; completas lo que dice «____» y lo envías."},
                    {"title": "Dale acceso si lo necesita", "text": "Si alguien debe entrar al sistema, créale un usuario con contraseña: será Invitado (solo consulta) por 24 horas. Cuando venza, pulsa «Reactivar 24 h» en su fila."},
                ],
            }
        ],
        "warnings": ["Las contraseñas deben tener al menos 8 caracteres, con letras y números."],
    },
    "Sistema": {
        "icon": "info",
        "summary": "Ver en qué versión está el sistema, dónde guarda los datos, cuántos registros hay y las últimas novedades.",
        "sections": [
            {
                "title": "Qué encuentras aquí",
                "steps": [
                    {"title": "Versión y entorno", "text": "Las tarjetas de arriba dicen qué versión está desplegada, si usas Supabase o la base de prueba y si la base está protegida."},
                    {"title": "Novedades", "text": "Los últimos cambios del sistema, leídos de su registro de cambios."},
                    {"title": "Resumen para soporte", "text": "Al final hay un texto para copiar y enviar si necesitas ayuda. **No incluye contraseñas ni claves.**"},
                ],
            }
        ],
        "not_does": ["El sistema **no se conecta con el sistema del proveedor ni procesa pagos**. Prepara el pedido con su valor exacto (IGV incluido) y registra lo pedido por proveedor, lo que entra al almacén y lo que sale a cada obra. La compra y el pago se hacen fuera, con el RUC de la empresa."],
    },
    "Manual de usuario": {
        "icon": "info",
        "summary": "El manual completo del sistema: cada procedimiento muestra el formulario tal como lo verás y los pasos para completarlo.",
        "sections": [
            {
                "title": "Cómo leerlo",
                "steps": [
                    {"title": "Elige un capítulo", "text": "Los botones de arriba siguen el orden natural del trabajo: empezar, preparar datos, pedir material, almacén, obras y control."},
                    {"title": "Mira la maqueta y sigue los números", "text": "El dibujo del formulario lleva marcas numeradas; cada número es el paso que lo explica."},
                    {"title": "Busca por palabra", "text": "Escribe «recepción», «IGV» o «vale» en el buscador para ir directo al procedimiento."},
                ],
            }
        ],
        "not_does": ["El sistema **no se conecta con el sistema del proveedor ni procesa pagos**: el manual explica cómo registrar lo pedido, lo recibido y lo despachado."],
    },
    "Respaldo de datos": {
        "icon": "shield",
        "summary": "Tener una copia de todo fuera del sistema, por si algo se borra por error.",
        "sections": [
            {
                "title": "Hacer un respaldo",
                "steps": [
                    {"title": "Protégelo con contraseña", "text": "Marca **Proteger con contraseña** (recomendado) y escribe una que guardes aparte: el respaldo incluye datos sensibles."},
                    {"title": "Genera y descarga", "text": "Pulsa **Generar respaldo** y luego **Descargar**. Obtienes un ZIP con un archivo por tabla."},
                    {"title": "Guárdalo fuera de este equipo", "text": "Disco externo o nube. Un respaldo que solo está en el mismo equipo no sirve si el equipo falla."},
                ],
            },
            {
                "title": "Restaurar",
                "steps": [{"title": "Usa el script de restauración", "text": "Para restaurar se usa `scripts/restore_backup.py`; la misma pantalla explica cómo.", "where": "Sección 3 de esta pantalla"}],
            },
        ],
        "tips": ["El respaldo semanal también puede hacerse solo desde GitHub (se explica en la pantalla)."],
        "warnings": ["Los documentos adjuntos (fotos y PDF) no van dentro del ZIP: solo se respalda su lista."],
    },
    "Historial de cambios": {
        "icon": "clock",
        "summary": "Auditoría: quién creó, editó, recibió o eliminó algo, y cuándo.",
        "sections": [
            {
                "title": "Consultar el historial",
                "steps": [
                    {"title": "Busca o filtra", "text": "Usa el buscador, o filtra por **persona**."},
                    {"title": "Mira qué cambió", "text": "En las ediciones de materiales, proveedores, precios, órdenes y presupuestos, abre **Ver los cambios** para ver el valor **antes y después** (por ejemplo «Precio: 10 → 12»)."},
                    {"title": "Solo ediciones con detalle", "text": "Marca **Solo ediciones con detalle** para ocultar las acciones simples y ver únicamente las ediciones."},
                ],
            }
        ],
        "tips": ["Solo lo ven los administradores."],
        "not_does": ["El **RUC** de la empresa no se escribe en el historial: solo queda anotado que cambió."],
    },
}


def guide_for(eyebrow: str, title: str) -> dict | None:
    """La guía de una pantalla (por su título), o None si no tiene."""
    if title in GUIDES:
        return {**GUIDES[title], "title": title}
    if eyebrow.upper().startswith("CENTRO DE CONTROL"):
        return {**GUIDES["Dashboard"], "title": "Dashboard"}
    return None
