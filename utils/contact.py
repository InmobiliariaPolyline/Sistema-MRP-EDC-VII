"""Contacto rápido: enlaces de llamada, WhatsApp, Gmail, Outlook y correo del equipo, con mensajes ya escritos y bien presentados.

Hay dos públicos con mensajes completamente distintos:

- **proveedores** (trato de «usted»): cotizar, consultar disponibilidad, pedir precios, seguimiento de pedidos, coordinar entregas
  y pedir comprobantes;
- **trabajadores** (trato de «tú», son parte del equipo): convocatoria de trabajo, recordatorio de asistencia, cambio de obra o
  turno, material listo en almacén, aviso de seguridad, reporte del día y entrega de documentos.

Cada mensaje se arma con piezas (título, saludo, párrafos, listas, datos con campos por completar y despedida) y se escribe según
el canal: en WhatsApp con su formato (*negrita*, _cursiva_), en el correo como texto limpio con sangría. El sistema no envía
nada: abre WhatsApp o el correo con el texto listo y la persona lo revisa, completa lo que falta (____) y lo envía."""
from __future__ import annotations

import re
from urllib.parse import quote

BLANK = "____"
BULLET = "•"
INDENT = "   "


def whatsapp_number(phone: str | None) -> str:
    """Solo dígitos, con el código de Perú (51) si el número es un celular de 9 dígitos."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 9 and digits.startswith("9"):
        digits = "51" + digits
    return digits


def dial_number(phone: str | None) -> str:
    return re.sub(r"[^\d+]", "", phone or "")


# Piezas de un mensaje: ("p", texto) · ("list", [ítems]) · ("kv", [(dato, valor)]) con ____ donde falta completar
def _supplier_specs() -> list[dict]:
    return [
        {"key": "cotizacion", "label": "Solicitar cotización", "hint": "Precios, plazo y condiciones", "title": "Solicitud de cotización",
         "parts": [("p", "Estamos actualizando nuestro catálogo de proveedores."), ("p", "Le agradeceré enviarnos su cotización con:"),
                   ("list", ["Precio unitario actualizado (indicando si incluye IGV)", "Disponibilidad y plazo de entrega", "Condiciones de pago", "Pedido mínimo, si lo hubiera"])]},
        {"key": "disponibilidad", "label": "Consultar disponibilidad", "hint": "¿Hay stock de lo que necesito?", "title": "Consulta de disponibilidad",
         "parts": [("p", "Quisiéramos confirmar si cuentan con stock de los materiales que les solicitaremos esta semana:"),
                   ("kv", [("Material", BLANK), ("Cantidad aproximada", BLANK), ("Fecha requerida", BLANK)])]},
        {"key": "precios", "label": "Pedir lista de precios", "hint": "Excel o PDF vigente", "title": "Lista de precios vigente",
         "parts": [("p", "¿Podría compartirnos su lista de precios vigente, en Excel o PDF?"), ("p", "La usaremos para actualizar nuestro catálogo y comparar ofertas.")]},
        {"key": "seguimiento", "label": "Seguimiento de un pedido", "hint": "Estado y fecha de entrega", "title": "Seguimiento de pedido",
         "parts": [("p", "Quisiéramos conocer el estado de nuestro pedido y la fecha estimada de entrega:"), ("kv", [("Orden de compra", BLANK), ("Material", BLANK)])]},
        {"key": "entrega", "label": "Coordinar entrega en obra", "hint": "Día, hora y dirección", "title": "Coordinación de entrega",
         "parts": [("p", "Para coordinar la entrega de nuestro pedido en obra, le comparto los datos:"),
                   ("kv", [("Obra", BLANK), ("Dirección", BLANK), ("Día y hora", BLANK), ("Persona que recibe", BLANK)])]},
        {"key": "comprobante", "label": "Pedir factura o comprobante", "hint": "Documento de la compra", "title": "Envío de comprobante",
         "parts": [("p", "¿Podría enviarnos la factura o el comprobante de nuestra última compra?"), ("kv", [("Orden de compra", BLANK), ("Fecha de entrega", BLANK)])]},
    ]


def _worker_specs(site: str | None, role: str | None) -> list[dict]:
    return [
        {"key": "convocatoria", "label": "Convocar a trabajar", "hint": "Obra, hora y punto de encuentro", "title": "Convocatoria de trabajo",
         "parts": [("p", "Te confirmamos tu jornada en obra:"),
                   ("kv", [("Obra", site or BLANK), ("Puesto", role or BLANK), ("Hora de ingreso", BLANK), ("Punto de encuentro", BLANK)]),
                   ("p", "Responde OK para confirmar que recibiste este mensaje.")]},
        {"key": "asistencia", "label": "Recordar la asistencia", "hint": "Puntualidad y qué traer", "title": "Recordatorio de asistencia",
         "parts": [("p", "Te recordamos que hoy se pasa lista en obra. Por favor:"),
                   ("list", ["Llega 10 minutos antes de la hora de ingreso", "Trae tu DNI y tus implementos de seguridad", "Avísanos con anticipación si no puedes asistir"])]},
        {"key": "cambio", "label": "Cambio de obra o turno", "hint": "Nueva obra, horario y fecha", "title": "Cambio de obra o turno",
         "parts": [("p", "Se ha modificado tu asignación:"), ("kv", [("Nueva obra", BLANK), ("Turno u horario", BLANK), ("Desde el", BLANK)]),
                   ("p", "Ante cualquier duda, comunícate con el encargado de obra.")]},
        {"key": "material", "label": "Material listo en almacén", "hint": "Recoger con su vale", "title": "Material listo en almacén",
         "parts": [("p", "Hay material listo en almacén para llevar a obra:"), ("kv", [("Obra", site or BLANK), ("Vale", BLANK), ("Recoger en", f"almacén, antes de las {BLANK}")]),
                   ("p", "Presenta tu DNI para retirarlo.")]},
        {"key": "seguridad", "label": "Aviso de seguridad", "hint": "Normas y equipos de protección", "title": "Aviso de seguridad",
         "parts": [("p", "Recuerda cumplir las normas de seguridad en obra:"),
                   ("list", ["Casco, chaleco y botas con punta de acero", "Arnés en todo trabajo en altura", "Reporta de inmediato cualquier incidente o condición insegura"])]},
        {"key": "reporte", "label": "Pedir el reporte del día", "hint": "Avance, material e incidencias", "title": "Reporte del día",
         "parts": [("p", "Por favor, envíame el avance de hoy:"), ("list", ["Trabajos realizados", "Material usado o faltante", "Incidencias o retrasos"])]},
        {"key": "documentos", "label": "Pedir documentos", "hint": "Registro del trabajador", "title": "Entrega de documentos",
         "parts": [("p", "Necesitamos estos documentos para completar tu registro:"),
                   ("list", ["Copia de tu DNI", "Examen médico vigente", "Contacto de emergencia (nombre y teléfono)"]), ("p", "Puedes enviarlos por este mismo chat.")]},
    ]


def _first_name(name: str | None) -> str:
    return (name or "").strip().split(" ")[0]


def render(spec: dict, channel: str, greeting: str, closing: str, signature: str | None) -> str:
    """Un mensaje armado con sangría y párrafos. `channel`: «whatsapp» (con *negrita* y _cursiva_) o «email» (texto limpio)."""
    wa = channel == "whatsapp"
    blocks: list[str] = []
    if wa:
        blocks.append(f"*{spec['title']}*")
    blocks.append(greeting)
    for kind, content in spec["parts"]:
        if kind == "p":
            blocks.append(content)
        elif kind == "list":
            blocks.append("\n".join(f"{INDENT}{BULLET}  {item}" for item in content))
        elif kind == "kv":
            blocks.append("\n".join(f"{INDENT}{BULLET}  " + (f"*{key}:*" if wa else f"{key}:") + f" {value}" for key, value in content))
    blocks.append(closing)
    if signature:
        blocks.append(f"_{signature}_" if wa else f"Saludos cordiales,\n{signature}")
    return "\n\n".join(blocks)


def messages(
    contact: str | None = None, company: str | None = None, audience: str = "supplier", site: str | None = None, role: str | None = None,
) -> list[dict]:
    """Mensajes preestablecidos del público indicado: [{key, label, hint, subject, whatsapp, email, body}].
    `body` es el texto del correo (se conserva por compatibilidad)."""
    first, who = _first_name(contact), (company or "").strip()
    if audience == "worker":
        specs = _worker_specs(site, role)
        greeting = f"Hola {first}, buen día." if first else "Hola, buen día."
        closing = "Gracias por tu apoyo."
    else:
        specs = _supplier_specs()
        greeting = f"Buen día, {first}:" if first else "Buen día:"
        if who:
            specs = [{**s, "parts": [("p", f"Le escribe {who}.")] + s["parts"]} for s in specs]
        closing = "Quedo atento a su respuesta. Muchas gracias."
    signature = who or ("Equipo de obra" if audience == "worker" else None)
    out = []
    for spec in specs:
        email = render(spec, "email", greeting, closing, signature)
        out.append({"key": spec["key"], "label": spec["label"], "hint": spec["hint"], "subject": spec["title"],
                    "whatsapp": render(spec, "whatsapp", greeting, closing, signature), "email": email, "body": email})
    return out


def whatsapp_url(phone: str | None, text: str) -> str:
    return f"https://wa.me/{whatsapp_number(phone)}?text={quote(text)}"


def gmail_url(email: str, subject: str, body: str) -> str:
    return f"https://mail.google.com/mail/?view=cm&fs=1&to={quote(email)}&su={quote(subject)}&body={quote(body)}"


def outlook_url(email: str, subject: str, body: str) -> str:
    return f"https://outlook.live.com/owa/?path=/mail/action/compose&to={quote(email)}&subject={quote(subject)}&body={quote(body)}"


def mailto_url(email: str, subject: str, body: str) -> str:
    return f"mailto:{quote(email)}?subject={quote(subject)}&body={quote(body)}"
