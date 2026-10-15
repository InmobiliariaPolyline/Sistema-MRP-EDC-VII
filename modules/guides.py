"""Guías de uso por módulo (el botón «❓ Cómo usar» que aparece junto al título).
Se buscan por el título de la página; cada una explica para qué sirve, los
pasos y un ejemplo."""

GUIDES: dict[str, str] = {
    "Dashboard": """
**Para qué sirve:** una lectura rápida de cómo va todo.

- **Tarjetas:** cuántos materiales, proveedores y órdenes abiertas hay.
- **Gráficos:** gasto por mes, gasto por proveedor y órdenes por estado.
- **⏰ Alerta amarilla:** órdenes abiertas hace demasiado tiempo (el límite en días se cambia en *Órdenes de compra*).
- **Mapa:** todas las obras con ubicación.

*Ejemplo:* si ves «3 órdenes abiertas hace más de 3 días», entra a Órdenes de compra y llama al proveedor.
""",
    "Proveedores": """
**Para qué sirve:** tener a quién llamar y qué vende cada uno.

1. **＋ Nuevo proveedor:** escribe nombre y teléfono *con código de país* (ej. `51987654321`) para que WhatsApp funcione.
2. **Catálogo:** marca *Lo ofrece*, si está *Disponible* y su *precio*. Esos precios alimentan el comparador y la sugerencia de compra.
3. **📥 Importar precios:** sube el Excel o CSV que te mandó el proveedor. Se enlaza cada fila con tu catálogo y ves qué cambia antes de aplicar. Si no tiene formato, descarga la plantilla.
4. Cada cambio de precio queda en el historial automáticamente.
5. **Vigencia de precios:** cada precio muestra cuándo se actualizó; si pasa de la vigencia (90 días, ajustable en la ficha) se marca como vencido y avisa al crear una orden y en la sugerencia de compra. El filtro «Precio vencido» lista lo que conviene volver a cotizar.
6. **Plazo de entrega y mínimo de compra** (al editar el proveedor): la sugerencia de compra calcula cuándo llegaría el pedido y avisa si no alcanza el mínimo, proponiendo materiales bajos del mismo proveedor para completarlo.
7. **Calificación:** cada proveedor recibe una nota de 0 a 100 según sus órdenes: entrega a tiempo respecto de la fecha prometida (60 %) y cantidades completas (40 %). Aparece en la lista y en su ficha.
""",
    "Materiales": """
**Para qué sirve:** el catálogo maestro de todo lo que el almacén puede manejar.

- **ℹ️** abre la ficha del material: densidad, precios por proveedor, stock y en qué obras se usa.
- **＋ Nuevo material:** categoría + nombre (no pueden repetirse juntos), densidad (kg/m³), métrica de compra (ej. *Volumen (m³)*) y **stock mínimo**.
- **Stock mínimo:** si lo defines, el tablero avisa cuando el stock llega a ese nivel y la sugerencia de compra lo repone.
- Que un material no tenga proveedor es normal: el catálogo es todo lo que puedes almacenar, no solo lo que ya cotizaste.
""",
    "Órdenes de compra": """
**Para qué sirve:** pedir material a un proveedor y seguir el pedido hasta que llega al almacén.

1. **＋ Nueva orden:** proveedor, obra destino (opcional) y materiales con su cantidad. El **precio unitario es el del catálogo del proveedor y no se puede cambiar en la orden** (solo sube el total al pedir más); si hay que cambiarlo, edítalo en Proveedores → Catálogo. **💡 Comparar cotizaciones** te dice si otro proveedor es más barato; si eliges obra, avisa cuando el pedido supera su presupuesto.
2. **Estados:** Pendiente → Enviada → Recibida (o Parcial si llegó solo una parte).
3. **📦 Registrar recepción:** anota lo que llegó; entra al stock del almacén. No se puede recibir más de lo pedido.
3a0. **✉️ Correo:** abre tu programa de correo con el pedido escrito y el correo del proveedor; adjunta el PDF descargado y envía (no se manda nada desde el servidor). Igual que WhatsApp, marca la orden como enviada.
3a. **Envío al proveedor:** al abrir **💬 Enviar por WhatsApp** una orden pendiente pasa sola a «enviada» y queda anotada la fecha y hora (también con «Marcar como enviada»).
3b. **Entrega, moneda e IGV (opcionales):** al crear o editar una orden puedes indicar la **fecha prometida de entrega** (si pasa y la orden sigue abierta, se marca como atrasada en la lista, en el detalle y en el dashboard), la **moneda** (soles o dólares, con su tipo de cambio) y si se **suma el IGV (18 %)** al total.
3c. **Recepción contra documento:** al registrar una recepción anota el **N.º de guía o factura**, quién entregó y las **observaciones** (faltantes, daños). Cada recepción queda guardada en «Recepciones registradas» dentro de la orden.
3d. **📎 Documentos adjuntos:** en el detalle de la orden sube la foto o el PDF de la factura, la guía de remisión o la cotización (hasta 10 MB; PDF, PNG, JPG o WEBP). «Abrir» los descarga o los muestra. También se pueden adjuntar al vale de salida firmado y al conteo de inventario. Necesita la clave de servicio de Supabase.
4. **✏️ Editar orden:** corrige cantidades, precios, obra o notas mientras no haya recibido material.
5. Una orden que ya recibió material **no se borra** (el stock quedaría descuadrado): si no continúa, cancélala.
6. **Sugerencia de compra:** calcula qué falta pedir según los presupuestos de las obras, el stock y lo que ya viene en camino, y crea las órdenes agrupadas por el proveedor más barato.
""",
    "Inventario": """
**Para qué sirve:** saber qué hay en el almacén y llevar la cuenta de lo que sale hacia las obras.

- **Entra** con las recepciones de las órdenes de compra (y con entradas de ajuste).
- **Sale** con un **despacho a obra**: cuando alguien pide material, pulsa **＋ Despachar a obra**, elige la obra y quién lo pide, agrega los materiales y confirma. Se descuenta del almacén y se genera un **vale de salida en PDF** para firmar.
- Si te pasas del presupuesto de la obra, el sistema avisa (no lo impide).
- **Devolver de una obra:** lo que sobra en una obra vuelve al almacén y suma al stock. Solo se puede devolver lo que la obra recibió (despachado menos devuelto); también está en la pestaña Materiales de cada obra.
- **Toma de inventario:** cuenta lo que hay en estantería, categoría por categoría. Escribe lo contado (lo que dejes vacío no se toca), anota el motivo de cada diferencia y se ajusta el stock. Cada conteo queda guardado en la pestaña **Conteos**.
- **Entrada, merma o devolución a proveedor:** para dar de baja material dañado o prestado, o devolver al proveedor lo que llegó mal.
- No se puede sacar más de lo que hay. La pestaña **Vales de salida** guarda todos los vales para reimprimirlos y enviarlos por correo.
- **Kardex:** elige un material y verás todas sus entradas y salidas en orden con el saldo después de cada una; si no coincide con el stock actual, avisa.

*Ejemplo:* Juan Pérez pide 4 m³ de concreto para Torre Central → Despachar a obra → Torre Central, Juan Pérez, Concreto 4 → Registrar → descargar el vale.
""",
    "Obras y presupuesto": """
**Para qué sirve:** ver todo de una obra en un solo lugar.

- **Información:** dirección, mapa y enlace a Google Maps.
- **Materiales:** presupuesto frente a lo pedido, recibido y **despachado** desde el almacén; ℹ️ para informarte de un material y **🚚 Despachar material** para sacar del almacén hacia esta obra.
- **Trabajadores:** quién está asignado y cuántas jornadas asistió.
- **Progreso:** porcentajes de pedido, recepción y despacho.

Primero define el presupuesto con **＋ Material al presupuesto** (cantidad prevista y precio estimado).

**Por etapas:** en el mismo formulario puedes indicar la **etapa** (cimentación, estructura, acabados…). El mismo material puede presupuestarse en varias etapas. Cuando la obra tiene etapas, la pestaña Materiales deja elegir una para ver su presupuesto frente a lo despachado en esa etapa, y al despachar material puedes indicar a qué etapa corresponde.
""",
    "Asistencia": """
**Para qué sirve:** llevar quién fue a qué obra cada día.

1. Elige la **fecha** (y, si quieres, filtra por obra).
2. En la tabla cambia *Estado* (presente, tardanza, permiso, ausente) y la *Obra* de cada trabajador. «—» = sin registrar.
3. **✅ Marcar pendientes presentes** completa las filas visibles sin estado. Todavía es un borrador.
4. Revisa la lista y pulsa **Guardar asistencia** para confirmar. Los borradores se conservan durante la sesión al cambiar de fecha o filtro; **Descartar cambios visibles** restaura lo guardado.

La pestaña *Resumen* cuenta asistencias y faltas de los últimos días.
""",
    "Reportes": """
**Para qué sirve:** sacar la información del sistema a Excel o PDF.

1. Elige qué conjuntos de datos incluir. «Los básicos» trae lo de siempre; además puedes agregar **vales de salida** (y su detalle), **historial de precios**, **presupuestos de obra** (con etapa), **conteos de inventario**, **recepciones de órdenes**, **calificación de proveedores** e **historial de cambios**.
2. Descarga **Excel** (una hoja por conjunto) o **PDF**.
3. El **reporte de una obra** (presupuesto frente a lo pedido, recibido y despachado, por material y por etapa, con sus vales) se descarga en PDF desde **Obras**, botón «📄 Reporte de la obra».
4. El **kardex** de un material (cada entrada y salida con el saldo) está en **Inventario → Kardex**, con descarga en Excel y PDF.
""",
    "Trabajadores": """
**Para qué sirve:** el personal de obra.

1. Crea **cuadrillas** y **obras** (en la obra puedes pegar el *enlace de Google Maps* para la ubicación exacta).
2. **＋ Nuevo trabajador:** nombre, documento, teléfono, puesto, cuadrilla y obra.
3. Si alguien debe entrar al sistema, dale acceso (usuario, contraseña y rol).
""",
    "Respaldo de datos": """
**Para qué sirve:** tener una copia de todo fuera del sistema, por si algo se borra por error.

1. Marca **Proteger con contraseña** (recomendado) y escribe una contraseña que guardes aparte.
2. **Generar respaldo** y luego **Descargar** el ZIP: trae un archivo por tabla y se abre con Excel (si no lo cifraste).
3. Guárdalo fuera de este equipo (disco externo o nube).
4. Para restaurar se usa `scripts/restore_backup.py` (está explicado en la misma pantalla).

También puede hacerse solo cada semana desde GitHub (ver la sección 3 de la pantalla).
""",
    "Historial de cambios": """
**Valor anterior y nuevo:** cuando se edita un material, un proveedor, un precio del catálogo, una orden (incluidas sus líneas), el estado de una orden o el presupuesto de una obra, el historial anota qué cambió: «Precio: 10 → 12». Abre «Ver los cambios» para ver la tabla antes/después, o marca «Solo ediciones con detalle» para filtrarlas.

**Para qué sirve:** auditoría: quién creó, editó, recibió o eliminó algo, y cuándo.

Usa el buscador o filtra por persona. Solo lo ven los administradores.
""",
}


def guide_for(eyebrow: str, title: str) -> str | None:
    if title in GUIDES:
        return GUIDES[title]
    if eyebrow.upper().startswith("CENTRO DE CONTROL"):
        return GUIDES["Dashboard"]
    return None
