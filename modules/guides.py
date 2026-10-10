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
2. **Catálogo:** marca *Lo ofrece*, si está *Disponible* ahora y su *precio*. Esos precios alimentan el comparador de cotizaciones.
3. Los botones 📞 💬 ✉️ contactan al proveedor con un clic.
""",
    "Materiales": """
**Para qué sirve:** el catálogo maestro de materiales.

- **ℹ️** abre la ficha del material: densidad, qué significa, precios por proveedor, stock y en qué obras se usa.
- **＋ Nuevo material:** categoría + nombre (no se pueden repetir juntos), densidad (kg/m³) y la métrica con la que se compra (ej. *Volumen (m³)*).
- La etiqueta verde «Mejor» es el precio más bajo entre proveedores con disponibilidad.
""",
    "Órdenes de compra": """
**Para qué sirve:** pedir materiales a un proveedor y seguir el pedido.

1. **＋ Nueva orden:** elige proveedor, obra destino y agrega materiales con cantidad y precio. El desplegable **💡 Comparar cotizaciones** te dice si otro proveedor es más barato.
2. **Estados:** Pendiente → Enviada → Recibida (o Parcial si llegó solo una parte).
3. **📦 Registrar recepción:** anota lo que llegó; se suma al inventario.
4. **PDF / WhatsApp / Duplicar:** imprime la orden, envíala escrita por WhatsApp o repítela.

*Ejemplo:* pediste 12 m³ de concreto y llegaron 5: escribe 5 en «Recibido ahora»; la orden queda *Parcial* con 7 pendientes.
""",
    "Inventario": """
**Para qué sirve:** saber cuánto hay de cada material.

- El stock **sube** con las recepciones de órdenes y con *Entradas* manuales.
- **Baja** con *Consumo en una obra* o *Salidas* (merma, préstamo).
- No se puede sacar más de lo que hay.

*Ejemplo:* **＋ Movimiento → Consumo en una obra →** Concreto, 2 m³, obra «Torre Central».
""",
    "Obras y presupuesto": """
**Para qué sirve:** ver todo de una obra en un solo lugar.

- **Información:** dirección, mapa y enlace a Google Maps.
- **Materiales:** presupuesto vs. pedido, recibido y consumido; ℹ️ para informarte de un material.
- **Trabajadores:** quién está asignado y cuántas jornadas asistió.
- **Progreso:** porcentajes de pedido, recepción y consumo.

Primero define el presupuesto con **＋ Material al presupuesto** (cantidad prevista y precio estimado).
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

1. Elige qué conjuntos de datos incluir.
2. Descarga **Excel** (una hoja por conjunto) o **PDF**.
""",
    "Trabajadores": """
**Para qué sirve:** el personal de obra.

1. Crea **cuadrillas** y **obras** (en la obra puedes pegar el *enlace de Google Maps* para la ubicación exacta).
2. **＋ Nuevo trabajador:** nombre, documento, teléfono, puesto, cuadrilla y obra.
3. Si alguien debe entrar al sistema, dale acceso (usuario, contraseña y rol).
""",
    "Historial de cambios": """
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
