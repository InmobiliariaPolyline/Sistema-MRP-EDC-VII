"""Contenido del Manual de usuario, como datos.

El manual enseña el sistema de principio a fin. Cada capítulo reúne **procedimientos**; cada procedimiento puede traer una
**maqueta** (`mock`): una réplica del formulario o la pantalla real, con los mismos títulos, campos y botones, y números que
remiten a los pasos. Así quien lee ve *exactamente* lo que va a encontrar en pantalla.

    capítulo      {"id", "title", "icon", "summary", "blocks": [...], "procedures": [...]}
    procedimiento {"title", "goal", "where", "mock", "steps", "tips", "warnings", "not_does"}
    paso          {"title", "text"}  (el número del paso es el que lleva la maqueta)
    maqueta       {"title", "source": [archivos de `modules/` de donde salen los textos], "rows": [...]}

Filas de una maqueta (todas opcionales y combinables):

    {"sec": "1. Proveedor y destino"}                       título de sección del formulario
    {"field": "Proveedor", "kind": "select", "value": "…", "mark": 1}      un campo (kind: text, select, number, date,
                                                                            textarea, check, password); `mark` = n.º de paso
    {"fields": [{...}, {...}]}                               varios campos lado a lado
    {"stats": [("Etiqueta", "Valor"), ...]}                  tarjetas de cifras
    {"table": {"cols": [...], "rows": [[...]], "mark": 2}}   tabla (una celda puede ser {"pill": "Texto", "tone": "good"})
    {"pills": [("Pendiente", "warn"), ...]}                  etiquetas de estado
    {"buttons": [("Cancelar", "ghost"), ("Crear orden", "primary", 5)]}    botones (el 3.er dato opcional es el `mark`)
    {"tabs": ["A", "B"], "active": 1}   {"note": "…", "tone": "info"}   {"lines": [("Cemento × 120", "S/ 3,420.00")]}
    {"menu": [("Grupo", ["Dashboard", ...])], "active": "…"}  {"signatures": ["Entrega", "Recibe"]}  {"caption": "…"}

Cada texto de una maqueta se comprueba en las pruebas contra el código de la pantalla real (`source`): si alguien cambia un
formulario sin actualizar el manual, la prueba lo avisa. Cuando un texto es dinámico en el código, se indica con `check`."""
from __future__ import annotations

FLOW = [
    {"icon": "truck", "title": "Proveedor", "text": "Su ficha, su catálogo y sus precios."},
    {"icon": "order", "title": "Orden de compra", "text": "El pedido con su valor exacto (IGV incluido)."},
    {"icon": "box", "title": "Recepción", "text": "Llega el material y se registra con su guía o factura."},
    {"icon": "layers", "title": "Almacén", "text": "Lo recibido entra al stock."},
    {"icon": "building", "title": "Despacho a obra", "text": "Sale con un vale firmado."},
    {"icon": "chart", "title": "Control", "text": "Presupuesto, reportes e historial."},
]

DOES = [
    "Prepara cada pedido con su **valor exacto**, con el **IGV (18 %)** separado como en una factura.",
    "Registra **qué se pide a cada proveedor**, **qué entra al almacén** y **qué sale a cada obra**.",
    "Compara lo pedido con el **presupuesto** de cada obra y avisa cuando algo no cuadra.",
    "Guarda todo para consulta: reportes en Excel y PDF, kardex, vales firmados e historial de cambios.",
]
DOES_NOT = [
    "**No se conecta** con el sistema ni la base de datos del proveedor.",
    "**No compra ni paga** nada: no usa tarjetas ni cuentas. La compra y el pago se hacen fuera, con el RUC de la empresa.",
    "Los importes que ves son el **valor de los pedidos**, no pérdidas ni pagos hechos.",
]

ROADMAP = [
    {"title": "Carga los datos de la empresa", "where": "Mi cuenta › Empresa y RUC", "text": "Razón social y RUC: salen en «Facturar a» de cada orden."},
    {"title": "Crea el catálogo de materiales", "where": "Materiales › ＋ Nuevo material", "text": "Todo lo que el almacén puede manejar, tenga o no proveedor."},
    {"title": "Registra a tus proveedores y sus precios", "where": "Proveedores", "text": "Ficha, catálogo de lo que venden y precio de cada material."},
    {"title": "Da de alta las obras y al personal", "where": "Trabajadores", "text": "Obras, cuadrillas y trabajadores."},
    {"title": "Define el presupuesto de cada obra", "where": "Obras › ＋ Material al presupuesto", "text": "Cantidad y precio previstos, por etapas si la obra va por fases."},
    {"title": "Arma tu primera orden de compra", "where": "Órdenes de compra › ＋ Nueva orden", "text": "Con proveedor, materiales, IGV y condición de pago."},
    {"title": "Registra la recepción", "where": "Dentro de la orden", "text": "Cuando llegue el material, con su guía o factura."},
    {"title": "Despacha material a una obra", "where": "Inventario › ＋ Despachar a obra", "text": "Con un vale que firma quien recibe."},
    {"title": "Haz un respaldo", "where": "Respaldo", "text": "Una copia de todo, fuera de este equipo."},
]

GLOSSARY = [
    ("Valor de venta", "El precio de los materiales **sin IGV**. En una factura se le llama también base imponible."),
    ("IGV", "Impuesto General a las Ventas: **18 %** en el Perú (16 % de IGV más 2 % del Impuesto de Promoción Municipal)."),
    ("Importe total", "Valor de venta más IGV: lo que cuesta el pedido completo."),
    ("Orden de compra", "El pedido a un proveedor, con materiales, cantidades, precios e IGV. En el sistema es un **registro**, no una compra hecha."),
    ("Recepción", "Registrar que el material llegó (con su guía o factura). Recién ahí **entra al stock**."),
    ("Stock mínimo", "Cantidad por debajo de la cual conviene reponer. Con ella el sistema avisa y sugiere comprar."),
    ("Vale de salida", "Documento que se genera al despachar material a una obra. Lo firma quien lo recibe."),
    ("Despacho", "Sacar material del almacén hacia una obra."),
    ("Merma", "Material dado de baja por daño, pérdida o préstamo, sin que vaya a una obra."),
    ("Kardex", "La historia de un material: cada entrada y salida con el saldo después de cada una."),
    ("Etapa", "Una fase de la obra (cimentación, estructura, acabados…) para presupuestar y despachar por partes."),
    ("Métrica de cómputo", "La unidad en que se presupuesta, pide y cuenta un material (m³, kg, m², unidad…)."),
    ("Toma de inventario", "Contar lo que hay en estantería y ajustar el sistema a la realidad, con el motivo de cada diferencia."),
    ("Condición de pago", "Lo pactado con el proveedor (contado, crédito 30 días…). Es **informativa**: el sistema no paga."),
]

FAQ = [
    ("No veo un cambio que acaba de hacer otra persona.", "Pulsa **Actualizar datos** en el menú lateral. El sistema guarda las lecturas unos segundos para ir más rápido."),
    ("¿Cómo cambio mi contraseña?", "En **Mi cuenta** (menú lateral), pestaña **Contraseña**. Debe tener al menos 8 caracteres, con letras y números."),
    ("¿Dónde veo el RUC de la empresa?", "En **Mi cuenta › Empresa y RUC**. Por seguridad pide tu contraseña y se vuelve a ocultar a los 3 minutos."),
    ("Me equivoqué en una orden. ¿Qué hago?", "Si todavía no recibió material, **Editar orden**. Si ya recibió, no se puede borrar ni editar: cancela lo que falte o corrige el stock con una toma de inventario."),
    ("Llegó solo una parte del pedido.", "Registra lo que llegó: la orden queda **Recibida parcial**. Cuando llegue el resto, vuelve a registrar la recepción."),
    ("¿Puedo sacar más material del que hay?", "No. El sistema no deja sacar más de lo que hay en el almacén."),
    ("Un material no tiene proveedor. ¿Es un error?", "No. El catálogo es todo lo que puedes almacenar, no solo lo que ya cotizaste."),
    ("¿El sistema hace el pago al proveedor?", "No. Prepara el pedido con su valor exacto y lo registra. La compra y el pago se hacen fuera del sistema."),
    ("Me bloquearon la cuenta.", "Tras 5 contraseñas incorrectas seguidas la cuenta se bloquea 15 minutos. Espera y vuelve a intentar."),
    ("¿Cómo pido ayuda?", "En **Sistema** hay un resumen técnico para copiar y enviar junto con la descripción del problema (no lleva claves)."),
]

CHAPTERS: list[dict] = [
    # ------------------------------------------------------------------------------------------------ 1
    {
        "id": "inicio",
        "title": "Empezar",
        "icon": "home",
        "summary": "Qué es el sistema, cómo entrar, cómo moverte y por dónde empezar.",
        "blocks": ["flow", "compare", "roadmap"],
        "procedures": [
            {
                "title": "Entrar al sistema",
                "goal": "Iniciar sesión con el usuario que te dio el administrador.",
                "where": "Pantalla de inicio",
                "mock": {
                    "title": "Inicia sesión para continuar.",
                    "source": ["login.py"],
                    "rows": [
                        {"field": "Usuario", "kind": "text", "placeholder": "Escribe tu usuario", "mark": 1},
                        {"field": "Contraseña", "kind": "password", "placeholder": "Escribe tu contraseña", "mark": 2},
                        {"buttons": [("Iniciar sesión →", "primary", 3)]},
                    ],
                },
                "steps": [
                    {"title": "Escribe tu usuario", "text": "Es el que te asignó el administrador."},
                    {"title": "Escribe tu contraseña", "text": "Puedes verla con el icono del ojo para comprobar que está bien escrita."},
                    {"title": "Pulsa «Iniciar sesión»", "text": "Entras al **Dashboard**. Si es la primera vez que se usa el sistema, la pantalla pide crear al primer administrador."},
                ],
                "tips": ["Tras **5 contraseñas incorrectas seguidas** la cuenta se bloquea 15 minutos."],
            },
            {
                "title": "Moverte por el sistema",
                "goal": "Conocer el menú lateral y sus accesos.",
                "where": "Menú lateral (a la izquierda)",
                "mock": {
                    "title": "Menú lateral",
                    "source": ["core/shell.py", "ui.py"],
                    "rows": [
                        {"menu": [
                            ("Resumen", ["Dashboard"]),
                            ("Compras y almacén", ["Órdenes de compra", "Proveedores", "Materiales", "Inventario"]),
                            ("Obra y personal", ["Obras", "Asistencia", "Trabajadores"]),
                            ("Análisis", ["Reportes", "Historial", "Respaldo"]),
                            ("Sistema", ["Sistema", "Manual de Usuario"]),
                        ], "active": "Órdenes de compra", "mark": 1},
                        {"buttons": [("Mi cuenta", "ghost", 2), ("Actualizar datos", "ghost", 3), ("Cerrar sesión", "ghost", 4)]},
                    ],
                },
                "steps": [
                    {"title": "Elige una pantalla", "text": "Pulsa su nombre. El menú está ordenado por tareas: compras y almacén, obra y personal, análisis y sistema."},
                    {"title": "Mi cuenta", "text": "Cambia tu contraseña y, si eres administrador, los datos de la empresa."},
                    {"title": "Actualizar datos", "text": "Vuelve a leer todo de la base. Úsalo si otra persona acaba de hacer cambios."},
                    {"title": "Cerrar sesión", "text": "Sal del sistema cuando termines, sobre todo si el equipo lo usan otras personas."},
                ],
                "tips": ["Cada pantalla tiene un botón **Cómo usar** junto al título con una guía rápida.", "Hay **modo oscuro** en el menú lateral."],
            },
            {
                "title": "Tu cuenta y los datos de la empresa",
                "goal": "Cambiar tu contraseña y guardar la razón social y el RUC con los que se compra.",
                "where": "Menú lateral › Mi cuenta",
                "mock": {
                    "title": "Mi cuenta",
                    "source": ["security.py"],
                    "rows": [
                        {"tabs": ["Contraseña", "Empresa y RUC"], "active": 1, "mark": 1},
                        {"note": "Por seguridad, ingresa tu contraseña para ver o cambiar el RUC.", "tone": "info"},
                        {"field": "Tu contraseña", "kind": "password", "mark": 2},
                        {"buttons": [("Mostrar datos de la empresa", "primary", 3)]},
                        {"field": "Razón social", "kind": "text", "value": "Constructora Andina S.A.C.", "mark": 4},
                        {"field": "RUC", "kind": "text", "value": "20131312955", "mark": 4},
                        {"buttons": [("Guardar datos de la empresa", "primary", 5)]},
                    ],
                },
                "steps": [
                    {"title": "Abre la pestaña «Empresa y RUC»", "text": "Solo la ve el administrador. La pestaña **Contraseña** sirve para cambiar tu clave."},
                    {"title": "Ingresa tu contraseña", "text": "El RUC **no se muestra** hasta confirmar que eres tú."},
                    {"title": "Pulsa «Mostrar datos de la empresa»", "text": "Los datos se ven **3 minutos** y se vuelven a ocultar solos (o con el botón **Ocultar**)."},
                    {"title": "Completa razón social y RUC", "text": "El RUC debe tener **11 dígitos**; el sistema comprueba que esté bien escrito con su dígito verificador."},
                    {"title": "Guarda", "text": "Desde ahora cada orden de compra sale con «Facturar a» y el RUC de la empresa."},
                ],
                "tips": ["En el historial el RUC no se escribe: solo queda anotado que cambió."],
            },
        ],
    },
    # ------------------------------------------------------------------------------------------------ 2
    {
        "id": "datos",
        "title": "Preparar los datos",
        "icon": "layers",
        "summary": "Materiales, proveedores con su catálogo y precios, obras y personal: lo que hay que cargar antes de pedir.",
        "blocks": [],
        "procedures": [
            {
                "title": "Registrar un material",
                "goal": "Agregar al catálogo maestro todo lo que el almacén puede manejar.",
                "where": "Materiales › ＋ Nuevo material",
                "mock": {
                    "title": "Agregar material",
                    "source": ["materiales.py"],
                    "rows": [
                        {"sec": "Identificación"},
                        {"fields": [
                            {"field": "Categoría", "kind": "text", "placeholder": "Ej. Concreto", "mark": 1},
                            {"field": "Nombre", "kind": "text", "placeholder": "Ej. Concreto f'c=210", "mark": 1},
                        ]},
                        {"sec": "Datos de cómputo"},
                        {"fields": [
                            {"field": "Densidad (kg/m³, opcional)", "kind": "number", "value": "2400", "mark": 3},
                            {"field": "Métrica de cómputo", "kind": "select", "value": "Volumen (m³)", "mark": 2},
                        ]},
                        {"sec": "Stock del almacén"},
                        {"field": "Stock mínimo (opcional)", "kind": "number", "value": "5", "mark": 4},
                        {"buttons": [("Cancelar", "ghost"), ("Revisar datos", "ghost"), ("Guardar", "primary", 5)]},
                    ],
                },
                "steps": [
                    {"title": "Categoría y nombre", "text": "Juntos identifican al material, así que **no pueden repetirse**. Conserva la especificación técnica en el nombre (resistencia, diámetro, presentación)."},
                    {"title": "Elige la métrica de cómputo", "text": "Es la unidad en que lo presupuestas, lo pides y lo cuentas. Elígela de la lista para que «m3» y «m³» no queden como dos cosas distintas."},
                    {"title": "Densidad (opcional)", "text": "Sirve para convertir volumen en peso. Déjala en 0 si no la conoces."},
                    {"title": "Stock mínimo (opcional)", "text": "Con él, el tablero avisa cuando el stock llega a ese nivel y la sugerencia de compra lo repone."},
                    {"title": "Guarda", "text": "Usa **Revisar datos** si quieres ver un resumen antes de guardar."},
                ],
                "tips": ["Pulsa **ℹ️** en un material para ver su ficha: precios por proveedor, stock y en qué obras se usa."],
                "not_does": ["Que un material no tenga proveedor es normal: el catálogo es todo lo que puedes almacenar, no solo lo que ya cotizaste."],
            },
            {
                "title": "Registrar un proveedor",
                "goal": "Tener su ficha, su RUC y cómo contactarlo.",
                "where": "Proveedores › ＋ Nuevo proveedor",
                "mock": {
                    "title": "Registrar proveedor",
                    "source": ["proveedores.py"],
                    "rows": [
                        {"sec": "Identificación"},
                        {"field": "Nombre del proveedor", "kind": "text", "placeholder": "Ej. Ferretería Norte", "mark": 1},
                        {"field": "RUC (opcional)", "kind": "text", "value": "20100070970", "mark": 2},
                        {"sec": "Contacto"},
                        {"fields": [
                            {"field": "Persona de contacto (opcional)", "kind": "text", "value": "Ana Ruiz", "mark": 3},
                            {"field": "Teléfono", "kind": "text", "value": "+51 987 654 321", "mark": 3},
                        ]},
                        {"field": "Correo (opcional)", "kind": "text", "value": "ventas@norte.pe", "mark": 3},
                        {"sec": "Condiciones de compra"},
                        {"fields": [
                            {"field": "Plazo de entrega habitual (días)", "kind": "number", "value": "5", "mark": 4},
                            {"field": "Monto mínimo de compra", "kind": "number", "value": "500.00", "mark": 4},
                        ]},
                        {"buttons": [("Cancelar", "ghost"), ("Revisar datos", "ghost"), ("Guardar", "primary", 5)]},
                    ],
                },
                "steps": [
                    {"title": "Escribe el nombre", "text": "Es lo único obligatorio."},
                    {"title": "Anota su RUC", "text": "11 dígitos, validados. Sale en la orden de compra y ayuda a tesorería a cuadrar las facturas."},
                    {"title": "Agrega cómo contactarlo", "text": "Escribe el teléfono **con código de país** (por ejemplo `51987654321`) para que el botón de WhatsApp funcione."},
                    {"title": "Condiciones de compra (opcionales)", "text": "El **plazo de entrega** y el **monto mínimo** ayudan a la sugerencia de compra: calcula cuándo llegaría y avisa si el pedido no alcanza el mínimo."},
                    {"title": "Guarda", "text": "Después podrás cargar su catálogo y sus precios."},
                ],
            },
            {
                "title": "Cargar el catálogo y los precios de un proveedor",
                "goal": "Indicar qué materiales vende y a qué precio, para comparar y pedir.",
                "where": "Proveedores › Catálogo",
                "mock": {
                    "title": "Catálogo del proveedor",
                    "source": ["proveedores.py"],
                    "rows": [
                        {"stats": [("Materiales ofrecidos", "24"), ("Disponibles", "20"), ("Con precio", "22"), ("Precios vencidos", "2")]},
                        {"fields": [
                            {"field": "Buscar material", "kind": "text", "placeholder": "Buscar material o categoría…"},
                            {"field": "Estado del catálogo", "kind": "select", "value": "Todos los materiales"},
                        ]},
                        {"table": {"cols": ["Material", "Lo ofrece", "Disponible", "Precio"], "rows": [
                            ["Cemento Portland tipo I", {"pill": "Sí", "tone": "good"}, {"pill": "Sí", "tone": "good"}, "28.50"],
                            ["Varilla corrugada 3/8", {"pill": "Sí", "tone": "good"}, {"pill": "No", "tone": "warn"}, "21.90"],
                            ["Arena gruesa", {"pill": "No", "tone": "gray"}, "—", "—"],
                        ], "mark": 1}},
                        {"buttons": [("Importar precios", "ghost", 2)]},
                        {"caption": "Cada precio muestra cuándo se actualizó («actualizado hace 12 d»)."},
                    ],
                },
                "steps": [
                    {"title": "Marca lo que vende", "text": "Para cada material marca **Lo ofrece**, indica si está **Disponible** y escribe su **precio**. Se guarda solo, sin botón."},
                    {"title": "O importa su lista de precios", "text": "Pulsa **Importar precios** y sube el Excel o CSV que te mandó el proveedor. Verás qué cambia **antes** de aplicarlo."},
                    {"title": "Vigila la vigencia", "text": "Un precio sin actualizar por más de **90 días** se marca como vencido. El filtro **Precio vencido** lista lo que conviene volver a cotizar."},
                ],
                "tips": ["El precio que usa una orden es el del catálogo en ese momento: **no se cambia dentro de la orden**."],
            },
            {
                "title": "Dar de alta una obra",
                "goal": "Crear el destino del material, con su ubicación en el mapa.",
                "where": "Trabajadores › Obras / Proyectos",
                "mock": {
                    "title": "Nueva obra",
                    "source": ["trabajadores.py"],
                    "rows": [
                        {"sec": "Identificación"},
                        {"field": "Nombre de la obra", "kind": "text", "placeholder": "Ej. Torre Central", "mark": 1},
                        {"field": "Dirección", "kind": "text", "placeholder": "Calle y número, distrito, ciudad", "mark": 2},
                        {"sec": "Ubicación"},
                        {"field": "Enlace de Google Maps o coordenadas (opcional, ubicación exacta)", "kind": "text", "placeholder": "Pega aquí el enlace de Google Maps o «-12.0098, -76.9836»", "mark": 3},
                        {"buttons": [("Cancelar", "ghost"), ("Ubicar en el mapa", "ghost", 4), ("Guardar obra", "primary", 5)]},
                    ],
                },
                "steps": [
                    {"title": "Escribe el nombre de la obra", "text": "Es lo único obligatorio. Es el nombre que verás en trabajadores, presupuestos y órdenes."},
                    {"title": "Agrega la dirección", "text": "Con distrito y ciudad para que la búsqueda en el mapa acierte."},
                    {"title": "Pega el enlace de Google Maps (opcional)", "text": "Da la ubicación exacta. También sirven las coordenadas."},
                    {"title": "Revisa el mapa", "text": "**Ubicar en el mapa** muestra el punto sin guardar la obra."},
                    {"title": "Guarda la obra", "text": "Ya puedes asignarle trabajadores, presupuesto y despachos."},
                ],
            },
            {
                "title": "Registrar a un trabajador",
                "goal": "Tener el personal de obra, su cuadrilla y su obra asignada.",
                "where": "Trabajadores › ＋ Nuevo trabajador",
                "mock": {
                    "title": "Registrar trabajador",
                    "source": ["trabajadores.py"],
                    "rows": [
                        {"sec": "Datos personales"},
                        {"field": "Nombre completo", "kind": "text", "placeholder": "Ej. Juan Pérez", "mark": 1},
                        {"fields": [
                            {"field": "Documento (opcional)", "kind": "text", "placeholder": "Ej. 45879632", "mark": 1},
                            {"field": "Teléfono", "kind": "text", "placeholder": "Ej. +51 987 654 321", "mark": 1},
                        ]},
                        {"field": "Puesto (opcional)", "kind": "text", "placeholder": "Ej. Albañil, Operador de grúa", "mark": 1},
                        {"sec": "Asignación"},
                        {"fields": [
                            {"field": "Cuadrilla", "kind": "select", "value": "Albañiles", "mark": 2},
                            {"field": "Obra / Proyecto", "kind": "select", "value": "Torre Central", "mark": 2},
                        ]},
                        {"sec": "Acceso al sistema"},
                        {"field": "Dar acceso al sistema (usuario y contraseña)", "kind": "check", "mark": 3},
                        {"buttons": [("Cancelar", "ghost"), ("Guardar", "primary", 4)]},
                    ],
                },
                "steps": [
                    {"title": "Datos personales", "text": "Solo el nombre completo es obligatorio. Documento, teléfono y puesto son opcionales."},
                    {"title": "Asígnalo", "text": "Elige su **cuadrilla** y su **obra**. Puedes dejarlas vacías y completarlas después. Las cuadrillas y obras se crean en sus paneles del mismo módulo."},
                    {"title": "Acceso al sistema (opcional)", "text": "Marca la casilla solo si esa persona debe entrar al sistema; completa usuario, contraseña y rol."},
                    {"title": "Guarda", "text": "Aparecerá en **Asistencia** para pasar lista."},
                ],
                "warnings": ["Las contraseñas deben tener al menos 8 caracteres, con letras y números."],
            },
        ],
    },
    # ------------------------------------------------------------------------------------------------ 3
    {
        "id": "compras",
        "title": "Pedir material",
        "icon": "order",
        "summary": "Armar la orden de compra con su valor exacto, enviarla al proveedor y registrar la recepción.",
        "blocks": ["states"],
        "procedures": [
            {
                "title": "Crear una orden de compra",
                "goal": "Armar el pedido con proveedor, materiales, IGV y condición de pago, y ver su valor exacto antes de comprar.",
                "where": "Órdenes de compra › ＋ Nueva orden",
                "mock": {
                    "title": "Nueva orden de compra",
                    "source": ["ordenes.py"],
                    "rows": [
                        {"sec": "1. Proveedor y destino"},
                        {"fields": [
                            {"field": "Proveedor", "kind": "select", "value": "Aceros del Sur", "mark": 1},
                            {"field": "Obra destino (opcional)", "kind": "select", "value": "Torre Central", "mark": 1},
                        ]},
                        {"sec": "2. Entrega, moneda, IGV y pago"},
                        {"fields": [
                            {"field": "Fecha prometida de entrega (opcional)", "kind": "date", "placeholder": "DD/MM/YYYY", "mark": 2},
                            {"field": "Moneda", "kind": "select", "value": "Soles (S/)", "mark": 2},
                        ]},
                        {"fields": [
                            {"field": "IGV (18 %)", "kind": "select", "value": "Los precios NO incluyen IGV: se suma 18 %", "mark": 3},
                            {"field": "Condición de pago (informativa)", "kind": "select", "value": "Crédito 30 días", "mark": 3},
                        ]},
                        {"sec": "3. Agrega materiales"},
                        {"fields": [
                            {"field": "Material", "kind": "select", "value": "Concreto · Concreto f'c=210", "mark": 4},
                            {"field": "Cantidad", "kind": "number", "value": "12.00", "mark": 4},
                            {"field": "Precio unit.", "kind": "number", "value": "280.00", "disabled": True, "mark": 4},
                        ]},
                        {"buttons": [("＋ Agregar al pedido", "ghost", 4)]},
                        {"sec": "4. Revisa y crea"},
                        {"lines": [("Concreto f'c=210 · 12 m³ × 280.00", "S/ 3,360.00")]},
                        {"stats": [("Valor de venta", "S/ 3,360.00"), ("IGV (18%)", "S/ 604.80"), ("Importe total", "S/ 3,964.80")], "mark": 5},
                        {"buttons": [("Cancelar", "ghost"), ("Crear orden", "primary", 6)]},
                    ],
                },
                "steps": [
                    {"title": "Elige proveedor y obra", "text": "Toda la orden es de **un proveedor**. La obra destino es opcional; si la eliges, el sistema avisa cuando el pedido supera su presupuesto."},
                    {"title": "Fecha prometida y moneda", "text": "La **fecha prometida** activa el aviso de atraso. Si el proveedor cotiza en dólares, elige la moneda e indica el tipo de cambio."},
                    {"title": "IGV y condición de pago", "text": "Elige cómo cotiza el proveedor: **sin IGV** (se suma 18 %), **con IGV incluido** (el sistema lo separa) o **exonerado**. La **condición de pago** es solo informativa: lo pactado, para saber cuánto y hasta cuándo."},
                    {"title": "Agrega los materiales", "text": "Elige el material y la cantidad. El **precio unitario es fijo**: viene del catálogo del proveedor. Repite por cada material."},
                    {"title": "Revisa los importes", "text": "Verás el **valor de venta**, el **IGV** y el **importe total**, como en una factura. Abajo, **Este mismo pedido con otros proveedores** te dice si alguien lo tiene más barato."},
                    {"title": "Crea la orden", "text": "Queda en estado **Pendiente**. Aún no se envió a nadie."},
                ],
                "tips": ["Si un precio del catálogo está vencido, el sistema te avisa al agregarlo."],
                "not_does": ["Crear la orden **no compra nada**: es el registro del trato con su valor exacto. La compra y el pago se hacen fuera del sistema."],
            },
            {
                "title": "Enviar la orden al proveedor",
                "goal": "Comunicar el pedido por PDF, WhatsApp o correo y dejar anotado el envío.",
                "where": "Órdenes de compra › Ver (detalle de la orden)",
                "mock": {
                    "title": "Orden de compra OC-0007",
                    "source": ["ordenes.py"],
                    "rows": [
                        {"pills": [("Pendiente", "warn")]},
                        {"stats": [("Proveedor", "Aceros del Sur"), ("Obra destino", "Torre Central"), ("Fecha", "2026-10-12"), ("Importe total (con IGV)", "S/ 3,964.80")]},
                        {"caption": "Valor de venta S/ 3,360.00 · IGV 18% S/ 604.80 · IGV sumado a los precios"},
                        {"buttons": [("Marcar como enviada", "ghost", 3), ("Cancelar orden", "ghost"), ("Eliminar", "ghost"), ("Editar orden", "ghost")]},
                        {"buttons": [("PDF", "ghost", 1), ("Enviar por WhatsApp", "ghost", 2), ("Correo", "ghost", 2), ("Duplicar", "ghost")]},
                    ],
                },
                "steps": [
                    {"title": "Descarga el PDF", "text": "Es la orden lista para imprimir o adjuntar: trae el proveedor, «Facturar a» con la razón social y el RUC de la empresa, los materiales y los importes."},
                    {"title": "Envíalo por WhatsApp o correo", "text": "Se abre tu WhatsApp o tu programa de correo con el pedido **ya escrito**. **Tú lo envías**: el sistema no se conecta con el proveedor."},
                    {"title": "Queda anotado el envío", "text": "Al abrir WhatsApp o el correo, una orden pendiente pasa sola a **Enviada** y se guarda la fecha y la hora. También puedes usar **Marcar como enviada**."},
                ],
                "tips": ["**Duplicar** crea otra orden con los mismos materiales y los precios vigentes del catálogo."],
            },
            {
                "title": "Registrar la recepción",
                "goal": "Anotar lo que llegó para que entre al stock del almacén.",
                "where": "Dentro de la orden › Registrar recepción",
                "mock": {
                    "title": "Registrar recepción",
                    "source": ["ordenes.py"],
                    "rows": [
                        {"sec": "1. Indica lo que llegó"},
                        {"table": {"cols": ["Material", "Pendiente", "Recibido ahora"], "rows": [
                            ["Concreto f'c=210", "12 m³", "12"],
                            ["Varilla corrugada 3/8", "300 unid", "180"],
                        ], "mark": 1}},
                        {"buttons": [("Recibir todo lo pendiente", "ghost", 1)]},
                        {"sec": "2. Documento de la entrega"},
                        {"fields": [
                            {"field": "N.º de guía o factura", "kind": "text", "placeholder": "Ej. T001-004521", "mark": 2},
                            {"field": "Entregado por", "kind": "text", "placeholder": "Ej. chofer Luis Prado", "mark": 2},
                        ]},
                        {"field": "Observaciones (faltantes, daños…)", "kind": "text", "placeholder": "Ej. 2 bolsas rotas; faltó 1 varilla", "mark": 3},
                        {"sec": "3. Revisa la entrega"},
                        {"buttons": [("Cancelar", "ghost"), ("Registrar lo indicado", "primary", 4)]},
                    ],
                },
                "steps": [
                    {"title": "Indica lo que llegó", "text": "Escribe en **Recibido ahora** la cantidad de cada línea. Usa 0 si ese material no llegó. No se puede recibir más de lo pedido."},
                    {"title": "Anota el documento", "text": "El **N.º de guía o factura** y quién entregó quedan guardados con la recepción."},
                    {"title": "Registra las observaciones", "text": "Faltantes, material dañado, lo que sea útil para reclamar después."},
                    {"title": "Confirma", "text": "Lo recibido **entra al stock** del almacén. Si llegó todo, la orden queda **Recibida**; si no, **Recibida parcial**."},
                ],
                "tips": ["Sube la foto o el PDF de la factura o la guía en **Documentos adjuntos**, dentro de la orden."],
                "warnings": ["Una orden que ya recibió material **no se puede borrar**: si no continúa, cancélala."],
            },
            {
                "title": "Sugerencia de compra",
                "goal": "Dejar que el sistema calcule qué falta pedir y cree las órdenes.",
                "where": "Órdenes de compra › Sugerencia de compra",
                "mock": {
                    "title": "Sugerencia de compra",
                    "source": ["sugerencias.py"],
                    "rows": [
                        {"stats": [("Materiales por pedir", "6"), ("Proveedores", "2"), ("Total estimado", "4,820.00")]},
                        {"table": {"cols": ["Incluir", "Material", "Proveedor", "Stock", "Por llegar", "Cantidad a pedir", "Precio unit."], "rows": [
                            [{"pill": "Sí", "tone": "good"}, "Cemento Portland tipo I", "Ferretería Norte", "12", "0", "40", "28.50"],
                            [{"pill": "Sí", "tone": "good"}, "Varilla corrugada 3/8", "Aceros del Sur", "30", "100", "70", "21.90"],
                        ], "mark": 1}},
                        {"note": "Aceros del Sur: el pedido suma 1,533.00 y su mínimo de compra es 2,000.00.", "tone": "warn", "mark": 2},
                        {"buttons": [("Crear las órdenes seleccionadas", "primary", 3)]},
                    ],
                },
                "steps": [
                    {"title": "Revisa lo que propone", "text": "Calcula el faltante con los presupuestos de las obras, el stock y lo que ya viene en camino. Asigna cada material al **proveedor más barato**. Puedes quitar líneas o cambiar cantidades."},
                    {"title": "Mira los avisos", "text": "Si un pedido no llega al **monto mínimo** del proveedor, te lo dice y propone materiales bajos del mismo proveedor para completarlo. También avisa de precios vencidos."},
                    {"title": "Crea las órdenes", "text": "Se crea **una orden pendiente por proveedor**, con la fecha prometida calculada con su plazo de entrega."},
                ],
            },
        ],
    },
    # ------------------------------------------------------------------------------------------------ 4
    {
        "id": "almacen",
        "title": "Almacén",
        "icon": "box",
        "summary": "Despachar material a las obras, recibir devoluciones, contar el stock y consultar el kardex.",
        "blocks": ["stock"],
        "procedures": [
            {
                "title": "Despachar material a una obra",
                "goal": "Sacar material del almacén hacia una obra y generar el vale de salida.",
                "where": "Inventario › ＋ Despachar a obra",
                "mock": {
                    "title": "Despachar material a una obra",
                    "source": ["inventario.py"],
                    "rows": [
                        {"sec": "1. Obra y solicitante"},
                        {"fields": [
                            {"field": "Obra destino", "kind": "select", "value": "Torre Central", "mark": 1},
                            {"field": "Solicitante", "kind": "select", "value": "Juan Pérez", "mark": 1},
                        ]},
                        {"fields": [
                            {"field": "Etapa de la obra (opcional)", "kind": "select", "value": "Cimentación", "mark": 2},
                            {"field": "Nota del vale (opcional)", "kind": "text", "placeholder": "Ej. Para el vaciado de losa del piso 3", "mark": 2},
                        ]},
                        {"sec": "2. Materiales"},
                        {"fields": [
                            {"field": "Material", "kind": "select", "value": "Concreto · Concreto f'c=210  (hay 12 m³)", "mark": 3},
                            {"field": "Cantidad (m³)", "kind": "number", "value": "4.00", "mark": 3, "check": "Cantidad ("},
                        ]},
                        {"buttons": [("＋ Agregar al vale", "ghost", 3)]},
                        {"sec": "3. Revisa y confirma"},
                        {"lines": [("Concreto f'c=210 · 4 m³", "")]},
                        {"buttons": [("Cancelar", "ghost"), ("Registrar despacho y generar vale", "primary", 4)]},
                    ],
                },
                "steps": [
                    {"title": "Elige la obra y quién pide", "text": "El trabajador que solicita el material queda anotado en el vale. Primero aparecen los asignados a esa obra."},
                    {"title": "Etapa y nota (opcionales)", "text": "Si la obra tiene etapas, elige a cuál corresponde para compararlo con su presupuesto. La nota explica para qué es."},
                    {"title": "Agrega los materiales", "text": "Solo aparecen materiales **con stock**. Elige uno, la cantidad y pulsa **＋ Agregar al vale**. Puedes poner varios en el mismo vale."},
                    {"title": "Registra y descarga el vale", "text": "El stock baja y obtienes el **vale en PDF**: imprímelo para que quien recibe el material lo firme."},
                ],
                "tips": ["Si te pasas del presupuesto de la obra, el sistema avisa, pero no lo impide."],
                "warnings": ["No se puede sacar más de lo que hay en el almacén."],
            },
            {
                "title": "El vale de salida",
                "goal": "Entender el documento que se genera al despachar.",
                "where": "Inventario › Vales de salida › Ver / PDF",
                "mock": {
                    "title": "Vale de salida VS-0012",
                    "source": ["inventario.py"],
                    "rows": [
                        {"stats": [("Obra", "Torre Central"), ("Etapa", "Cimentación"), ("Solicitado por", "Juan Pérez")]},
                        {"table": {"cols": ["Material", "Unidad", "Cantidad"], "rows": [
                            ["Concreto f'c=210", "m³", "4.00"], ["Varilla corrugada 3/8", "unid", "120.00"],
                        ], "mark": 1}},
                        {"signatures": ["Entrega (almacén)", "Recibe", "V.° B.° de obra"], "mark": 2},
                        {"buttons": [("Enviar por correo", "ghost", 3)]},
                    ],
                },
                "steps": [
                    {"title": "Lo que dice el vale", "text": "Obra y etapa, quién lo solicitó, quién lo registró, la fecha y los materiales con su cantidad."},
                    {"title": "Las firmas", "text": "Lo firman quien **entrega** (almacén), quien **recibe** y, si hace falta, el visto bueno de la obra."},
                    {"title": "Reimprimir o enviar", "text": "En la pestaña **Vales de salida** puedes verlo de nuevo, descargar el PDF, enviarlo por correo y **adjuntar la foto del vale firmado**."},
                ],
            },
            {
                "title": "Devolver material de una obra",
                "goal": "Regresar al almacén lo que sobró en una obra.",
                "where": "Inventario › Devolver de una obra (o Obras › Devolver material)",
                "mock": {
                    "title": "Devolver material de una obra",
                    "source": ["inventario.py"],
                    "rows": [
                        {"sec": "1. Obra y quién devuelve"},
                        {"field": "Obra de origen", "kind": "select", "value": "Torre Central", "mark": 1},
                        {"fields": [
                            {"field": "Quién devuelve (opcional)", "kind": "text", "placeholder": "Ej. Juan Pérez", "mark": 1},
                            {"field": "Nota (opcional)", "kind": "text", "placeholder": "Ej. Sobró del vaciado de losa", "mark": 1},
                        ]},
                        {"sec": "2. Qué se devuelve"},
                        {"table": {"cols": ["Material", "Unidad", "En la obra", "Devolver"], "rows": [
                            ["Concreto f'c=210", "m³", "4", "1"], ["Varilla corrugada 3/8", "unid", "120", "0"],
                        ], "mark": 2}},
                        {"buttons": [("Cancelar", "ghost"), ("Registrar devolución", "primary", 3)]},
                    ],
                },
                "steps": [
                    {"title": "Elige la obra", "text": "Aparece lo que esa obra tiene: lo despachado menos lo ya devuelto. «Quién devuelve» y la nota son opcionales."},
                    {"title": "Escribe cuánto vuelve", "text": "En la columna **Devolver** de cada material. Deja en 0 el resto. No puedes devolver más de lo que la obra recibió."},
                    {"title": "Registra la devolución", "text": "El material **suma al stock** y baja lo consumido por la obra en su presupuesto."},
                ],
            },
            {
                "title": "Tomar inventario físico",
                "goal": "Contar lo que hay en estantería y ajustar el sistema, con el motivo de cada diferencia.",
                "where": "Inventario › Toma de inventario",
                "mock": {
                    "title": "Toma de inventario físico",
                    "source": ["inventario.py"],
                    "rows": [
                        {"field": "Categoría", "kind": "select", "value": "Acero y hierro", "mark": 1},
                        {"field": "Solo materiales con movimientos o stock", "kind": "check", "checked": True, "mark": 1},
                        {"table": {"cols": ["Material", "Unidad", "Sistema", "Contado", "Motivo de la diferencia"], "rows": [
                            ["Varilla corrugada 3/8", "unid", "46", "44", "rotura en transporte"],
                            ["Perfil IPN 200", "unid", "30", "—", ""],
                        ], "mark": 2}},
                        {"stats": [("Contados", "1"), ("Con diferencia", "1"), ("Sin diferencia", "0")]},
                        {"field": "Nota del conteo (opcional)", "kind": "text", "placeholder": "Ej. Conteo mensual de octubre", "mark": 3},
                        {"buttons": [("Cancelar", "ghost"), ("Guardar conteo y ajustar diferencias", "primary", 4)]},
                    ],
                },
                "steps": [
                    {"title": "Elige una categoría", "text": "Cuenta una a la vez. Por omisión solo se listan materiales con movimientos o stock."},
                    {"title": "Escribe lo contado", "text": "En **Contado** anota lo que realmente hay. Lo que dejes vacío **no se toca**. Anota el motivo de cada diferencia."},
                    {"title": "Agrega una nota (opcional)", "text": "Por ejemplo, el mes o la persona que contó."},
                    {"title": "Guarda", "text": "El stock se ajusta (entrada si sobra, salida si falta) y el conteo queda guardado, con el detalle de lo que decía el sistema y lo contado."},
                ],
                "tips": ["Los conteos pasados están en la pestaña **Conteos**."],
            },
            {
                "title": "Entradas, mermas y devoluciones a proveedor",
                "goal": "Registrar movimientos que no son una recepción ni un despacho.",
                "where": "Inventario › Entrada, merma o devolución a proveedor",
                "mock": {
                    "title": "Registra una entrada, una merma o una devolución a proveedor",
                    "source": ["inventario.py"],
                    "rows": [
                        {"sec": "1. Tipo y material"},
                        {"field": "Tipo de movimiento", "kind": "radio", "mark": 2, "selected": 1, "options": [
                            "Entrada (ajuste / compra directa)", "Merma o salida sin obra (préstamo, pérdida…)", "Devolución a un proveedor (sale del almacén)"]},
                        {"field": "Material", "kind": "select", "value": "Cemento · Cemento Portland tipo I", "mark": 3},
                        {"caption": "Stock actual: 120 bolsa"},
                        {"sec": "2. Cantidad y motivo"},
                        {"fields": [
                            {"field": "Cantidad", "kind": "number", "value": "2.00", "mark": 3},
                            {"field": "Nota (opcional)", "kind": "text", "placeholder": "Ej. Ajuste por conteo / material dañado en transporte", "mark": 4},
                        ]},
                        {"stats": [("Stock actual", "120 bolsa"), ("Stock después", "118 bolsa")], "mark": 3},
                        {"buttons": [("Cancelar", "ghost"), ("Guardar movimiento", "primary", 4)]},
                    ],
                },
                "steps": [
                    {"title": "Abre el formulario", "text": "Pulsa **Entrada, merma o devolución a proveedor**."},
                    {"title": "Elige el tipo", "text": "**Entrada** suma stock (compra directa, ajuste). **Merma** da de baja material dañado, perdido o prestado. **Devolución a proveedor** saca lo que llegó mal."},
                    {"title": "Indica material y cantidad", "text": "Verás el **stock actual** y cómo **quedará**. Una salida no puede superar lo que hay."},
                    {"title": "Anota el motivo y guarda", "text": "La nota es opcional pero ayuda a entender el movimiento después. Pulsa **Guardar movimiento**."},
                ],
            },
            {
                "title": "Consultar el kardex",
                "goal": "Ver la historia de un material: cada entrada y salida con su saldo.",
                "where": "Inventario › Kardex",
                "mock": {
                    "title": "Kardex",
                    "source": ["inventario.py", "../utils/kardex.py"],
                    "rows": [
                        {"field": "Material", "kind": "select", "value": "Acero y hierro · Varilla corrugada 3/8", "mark": 1},
                        {"stats": [("Entradas", "100 unid"), ("Salidas", "54 unid"), ("Saldo", "46 unid")]},
                        {"table": {"cols": ["Fecha", "Tipo", "Documento", "Detalle", "Entrada", "Salida", "Saldo"], "rows": [
                            ["2026-10-01 09:00", "Recepción", "OC-0001", "Aceros del Sur", "100", "", "100"],
                            ["2026-10-14 16:45", "Despacho", "VS-0012", "Torre Central · Juan Pérez", "", "54", "46"],
                        ], "mark": 2}},
                    ],
                },
                "steps": [
                    {"title": "Elige el material", "text": "Solo aparecen los que tienen movimientos."},
                    {"title": "Lee el saldo corrido", "text": "Cada fila muestra el documento (orden, vale o conteo) y el **saldo** después de ese movimiento. Si no coincide con el stock actual, el sistema avisa."},
                ],
                "tips": ["Descárgalo en **Excel** o **PDF** con los botones de abajo."],
            },
        ],
    },
    # ------------------------------------------------------------------------------------------------ 5
    {
        "id": "obras",
        "title": "Obras y personal",
        "icon": "building",
        "summary": "Presupuestar cada obra, seguir lo pedido y despachado, y llevar la asistencia.",
        "blocks": [],
        "procedures": [
            {
                "title": "Presupuestar una obra",
                "goal": "Definir cuánto material se espera usar y a qué precio, para compararlo después.",
                "where": "Obras › Materiales › ＋ Material al presupuesto",
                "mock": {
                    "title": "Material del presupuesto",
                    "source": ["obras.py"],
                    "rows": [
                        {"sec": "1. Material"},
                        {"field": "Material", "kind": "select", "value": "Concreto · Concreto f'c=210", "mark": 1},
                        {"field": "Etapa de la obra (opcional)", "kind": "select", "value": "Cimentación", "mark": 2},
                        {"sec": "2. Cantidad y precio"},
                        {"fields": [
                            {"field": "Cantidad prevista (m³)", "kind": "number", "value": "20.00", "mark": 3, "check": "Cantidad prevista ("},
                            {"field": "Precio unit. estimado", "kind": "number", "value": "280.00", "mark": 3},
                        ]},
                        {"sec": "3. Revisa el presupuesto"},
                        {"stats": [("Costo del material", "5,600.00"), ("Presupuesto después", "12,480.00")]},
                        {"buttons": [("Cancelar", "ghost"), ("Guardar en el presupuesto", "primary", 4)]},
                    ],
                },
                "steps": [
                    {"title": "Elige el material", "text": "Si ya está presupuestado, guardar actualiza su cantidad y precio."},
                    {"title": "Etapa (opcional)", "text": "Para presupuestar por fases (cimentación, estructura, acabados…). El mismo material puede estar en varias etapas. Elige **Nueva etapa…** para crear una."},
                    {"title": "Cantidad y precio estimado", "text": "La cantidad usa la métrica del material. El precio se propone con el mejor de tus proveedores; puedes ajustarlo."},
                    {"title": "Guarda", "text": "Desde ahora cada orden y cada despacho se comparan con este presupuesto."},
                ],
            },
            {
                "title": "Seguir una obra",
                "goal": "Comparar presupuesto, pedido, recibido y despachado de un vistazo.",
                "where": "Obras › Materiales",
                "mock": {
                    "title": "Torre Central · Materiales",
                    "source": ["obras.py"],
                    "rows": [
                        {"stats": [("Presupuesto", "18,780"), ("Pedido hasta hoy", "11,410"), ("Saldo del presupuesto", "7,370"), ("Sobre lo presupuestado", "1")], "mark": 1},
                        {"field": "Etapa", "kind": "select", "value": "Todas las etapas", "mark": 2},
                        {"table": {"cols": ["Material", "Presupuesto", "Pedido", "Recibido", "Despachado", "Estado"], "rows": [
                            ["Cemento Portland tipo I", "300", "120", "40", "40", {"pill": "40% pedido", "tone": "info"}],
                            ["Varilla corrugada 3/8", "200", "300", "0", "0", {"pill": "Sobre lo presupuestado", "tone": "warn"}],
                            ["Arena gruesa", "18", "18", "18", "18", {"pill": "Completo", "tone": "good"}],
                        ], "mark": 3}},
                        {"buttons": [("Despachar material", "ghost", 4), ("Devolver material", "ghost", 4)]},
                    ],
                },
                "steps": [
                    {"title": "Lee las tarjetas", "text": "Presupuesto, lo pedido hasta hoy, el saldo y cuántos materiales superan lo presupuestado."},
                    {"title": "Filtra por etapa", "text": "Si la obra tiene etapas, un selector deja ver una etapa o todas."},
                    {"title": "Revisa cada material", "text": "La tabla compara lo presupuestado con lo pedido, recibido y despachado, y marca el estado."},
                    {"title": "Despacha o devuelve desde aquí", "text": "Abren el mismo formulario del Inventario, con esta obra ya elegida."},
                ],
                "tips": ["«Sobre lo presupuestado» es un aviso de presupuesto, no una pérdida."],
            },
            {
                "title": "Pasar lista de asistencia",
                "goal": "Registrar quién fue a qué obra cada día.",
                "where": "Asistencia",
                "mock": {
                    "title": "Asistencia",
                    "source": ["asistencia.py"],
                    "rows": [
                        {"sec": "1. Fecha y trabajadores"},
                        {"fields": [
                            {"field": "Fecha", "kind": "date", "value": "21/10/2026", "mark": 1},
                            {"field": "Mostrar", "kind": "select", "value": "Todos los trabajadores", "mark": 1},
                        ]},
                        {"sec": "2. Prepara la lista"},
                        {"table": {"cols": ["Trabajador", "Cuadrilla", "Estado", "Obra", "Nota (opcional)"], "rows": [
                            ["Juan Pérez", "Albañiles", {"pill": "presente", "tone": "good"}, "Torre Central", ""],
                            ["Luis Prado", "Electricistas", {"pill": "tardanza", "tone": "warn"}, "Torre Central", "Llegó 15 min tarde"],
                            ["Ana Ruiz", "Albañiles", "—", "Torre Central", ""],
                        ], "mark": 2}},
                        {"buttons": [("Marcar pendientes presentes", "ghost", 3)]},
                        {"sec": "3. Revisa y guarda"},
                        {"stats": [("Con estado", "2"), ("Sin registrar", "1")]},
                        {"buttons": [("Descartar cambios visibles", "ghost"), ("Guardar asistencia", "primary", 4)]},
                    ],
                },
                "steps": [
                    {"title": "Elige el día", "text": "Selecciona la fecha y, si quieres, filtra por obra."},
                    {"title": "Marca el estado de cada trabajador", "text": "**Presente, tardanza, permiso o ausente**. «—» significa sin registrar y se omite al guardar. Puedes cambiar la obra de la jornada y escribir una nota."},
                    {"title": "Completa de una vez", "text": "**Marcar pendientes presentes** pone «presente» a las filas visibles sin estado. Todavía es un borrador."},
                    {"title": "Guarda", "text": "Revisa los contadores y pulsa **Guardar asistencia**. No se pueden registrar jornadas futuras."},
                ],
                "tips": ["Los borradores se conservan al cambiar de fecha o filtro durante la sesión."],
            },
            {
                "title": "Entregar el reporte de una obra",
                "goal": "Descargar el estado completo de una obra, listo para imprimir.",
                "where": "Obras › Reporte de la obra (PDF)",
                "mock": {
                    "title": "Obras y presupuesto",
                    "source": ["obras.py"],
                    "rows": [
                        {"field": "Obra", "kind": "select", "value": "Torre Central", "mark": 1},
                        {"stats": [("Presupuesto", "18,780"), ("Pedido hasta hoy", "11,410"), ("Saldo del presupuesto", "7,370"), ("Sobre lo presupuestado", "1")]},
                        {"buttons": [("Reporte de la obra (PDF)", "primary", 2)]},
                        {"tabs": ["Información", "Materiales", "Trabajadores", "Progreso"], "active": 1},
                    ],
                },
                "steps": [
                    {"title": "Elige la obra", "text": "Con el selector de arriba."},
                    {"title": "Pulsa «Reporte de la obra (PDF)»", "text": "Está debajo de las tarjetas, antes de las pestañas."},
                    {"title": "Lee el documento", "text": "Trae seis cifras (presupuesto, pedido, recibido, despachado, saldo y avance), la tabla de materiales con su estado, el avance por etapa y los vales de salida. Importes en soles y sin IGV."},
                ],
            },
        ],
    },
    # ------------------------------------------------------------------------------------------------ 6
    {
        "id": "control",
        "title": "Control y respaldo",
        "icon": "shield",
        "summary": "Reportes, historial de cambios, respaldo de los datos y el módulo Sistema.",
        "blocks": [],
        "procedures": [
            {
                "title": "Sacar reportes",
                "goal": "Descargar la información en Excel o PDF para compartirla o archivarla.",
                "where": "Reportes",
                "mock": {
                    "title": "Reportes",
                    "source": ["reportes.py"],
                    "rows": [
                        {"sec": "1. Elige el contenido"},
                        {"field": "Datos a incluir", "kind": "tags", "mark": 1, "options": [
                            "Materiales", "Proveedores", "Catálogo y precios por proveedor", "Trabajadores", "Órdenes de compra", "Detalle de órdenes",
                            "Stock actual", "Movimientos de inventario", "Asistencia (últimos 90 días)"]},
                        {"buttons": [("Los básicos", "ghost", 1), ("Seleccionar todo", "ghost"), ("Limpiar selección", "ghost")]},
                        {"stats": [("Conjuntos", "9"), ("Registros", "842"), ("Con información", "8")]},
                        {"sec": "2. Descarga tu reporte"},
                        {"buttons": [("⬇ Descargar Excel", "primary", 2), ("⬇ Descargar PDF", "ghost", 2)]},
                    ],
                },
                "steps": [
                    {"title": "Elige el contenido", "text": "«Los básicos» trae lo de siempre. Puedes agregar vales de salida, historial de precios, presupuestos de obra, conteos, recepciones, calificación de proveedores e historial de cambios."},
                    {"title": "Descarga", "text": "**Excel** crea una hoja por conjunto; **PDF** los reúne en un documento con portada y tablas."},
                    {"title": "Revisa la vista previa", "text": "Abajo puedes abrir cada conjunto para comprobar sus datos antes de compartir el archivo."},
                ],
                "tips": ["El reporte de una obra está en **Obras** y el kardex de un material en **Inventario › Kardex**."],
            },
            {
                "title": "Revisar el historial de cambios",
                "goal": "Saber quién creó, editó o eliminó algo, y qué cambió exactamente.",
                "where": "Historial (solo administradores)",
                "mock": {
                    "title": "Historial de cambios",
                    "source": ["historial.py"],
                    "rows": [
                        {"fields": [
                            {"field": "Buscar", "kind": "text", "placeholder": "Buscar un cambio o una persona…", "mark": 1},
                            {"field": "Persona", "kind": "select", "value": "Todas las personas", "mark": 1},
                        ]},
                        {"field": "Solo ediciones con detalle (valor anterior → nuevo)", "kind": "check", "mark": 2},
                        {"note": "Catálogo de «Ferretería Norte»: Cemento Portland (Precio: 27.00 → 28.50) · Luis · hace 5 min", "tone": "info"},
                        {"table": {"cols": ["Campo", "Antes", "Después"], "rows": [["Precio", "27.00", "28.50"]], "mark": 3}},
                    ],
                },
                "steps": [
                    {"title": "Busca o filtra", "text": "Por texto o por persona."},
                    {"title": "Solo ediciones con detalle", "text": "Oculta las acciones simples y deja las ediciones, que traen el valor anterior y el nuevo."},
                    {"title": "Abre «Ver los cambios»", "text": "Muestra la tabla **antes / después** de cada edición (por ejemplo «Precio: 27.00 → 28.50»)."},
                ],
                "not_does": ["El **RUC** de la empresa no se escribe en el historial: solo queda anotado que cambió."],
            },
            {
                "title": "Hacer un respaldo",
                "goal": "Tener una copia de todo fuera del sistema, por si algo se borra por error.",
                "where": "Respaldo (solo administradores)",
                "mock": {
                    "title": "Respaldo de datos",
                    "source": ["respaldo.py"],
                    "rows": [
                        {"sec": "1. Genera el respaldo"},
                        {"field": "Proteger con contraseña (cifrado AES-256)", "kind": "check", "checked": True, "mark": 1},
                        {"field": "Contraseña del respaldo", "kind": "password", "mark": 1},
                        {"buttons": [("Generar respaldo", "primary", 2)]},
                        {"buttons": [("Descargar respaldo (ZIP)", "ghost", 3)]},
                    ],
                },
                "steps": [
                    {"title": "Protégelo con contraseña", "text": "Recomendado: el respaldo incluye datos sensibles. **Guarda la contraseña aparte**: sin ella no se puede abrir ni restaurar."},
                    {"title": "Genera el respaldo", "text": "El sistema reúne todas las tablas en un ZIP con un archivo por tabla."},
                    {"title": "Descárgalo y guárdalo fuera de este equipo", "text": "Disco externo o nube. Un respaldo que solo está en el mismo equipo no sirve si el equipo falla."},
                ],
                "warnings": ["Los documentos adjuntos (fotos y PDF) no van dentro del ZIP: solo se respalda su lista."],
                "tips": ["El respaldo semanal también puede hacerse solo desde GitHub (se explica en la misma pantalla)."],
            },
            {
                "title": "Consultar el estado del sistema",
                "goal": "Ver la versión desplegada, el entorno y pedir soporte con datos útiles.",
                "where": "Sistema",
                "mock": {
                    "title": "Sistema",
                    "source": ["sistema.py"],
                    "rows": [
                        {"stats": [("Versión", "parche 061"), ("Base de datos", "Supabase"), ("Seguridad", "Protegida"), ("Hora del sistema", "21/10/2026 12:30")], "mark": 1},
                        {"sec": "Novedades"},
                        {"note": "**Manual de usuario ilustrado** · parche 061", "tone": "info", "mark": 2},
                        {"sec": "Soporte"},
                        {"note": "Sistema MRP · parche 061 · Datos: Supabase · Protegida · Consultado el 21/10/2026", "tone": "info", "mark": 3},
                    ],
                },
                "steps": [
                    {"title": "Mira las tarjetas de arriba", "text": "Versión desplegada, base de datos (Supabase o prueba), seguridad y hora del sistema."},
                    {"title": "Lee las novedades", "text": "Los últimos cambios del sistema, tomados de su registro de cambios."},
                    {"title": "Copia el resumen técnico", "text": "Al final hay un texto para enviar si necesitas ayuda. **No incluye contraseñas ni claves.**"},
                ],
            },
        ],
    },
]
