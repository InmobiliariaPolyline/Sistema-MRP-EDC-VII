"""Contacto rápido con un proveedor: enlaces de llamada, WhatsApp, Gmail, Outlook y correo del equipo, con mensajes ya escritos.

Cada mensaje preestablecido sirve para algo distinto (cotizar, consultar disponibilidad, pedir precios, seguimiento, entrega,
comprobantes). El sistema no se conecta con el proveedor: solo abre la ventana de WhatsApp o del correo con el texto listo
y la persona lo revisa y lo envía."""
from __future__ import annotations

import re
from urllib.parse import quote


def whatsapp_number(phone: str | None) -> str:
    """Solo dígitos, con el código de Perú (51) si el número es un celular de 9 dígitos."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 9 and digits.startswith("9"):
        digits = "51" + digits
    return digits


def dial_number(phone: str | None) -> str:
    return re.sub(r"[^\d+]", "", phone or "")


def _greeting(contact: str | None) -> str:
    first = (contact or "").strip().split(" ")[0]
    return f"Hola {first}, buen día." if first else "Hola, buen día."


def messages(contact: str | None = None, company: str | None = None, supplier: str | None = None) -> list[dict]:
    """Mensajes preestablecidos: [{key, label, hint, subject, body}]."""
    who = (company or "").strip()
    intro = f"Le escribe {who}." if who else "Le escribimos desde obra."
    hello = _greeting(contact)
    sign = "Quedo atento a su respuesta. Gracias." if not who else f"Quedo atento a su respuesta. Gracias.\n{who}"
    return [
        {"key": "cotizacion", "label": "Solicitar cotización", "hint": "Pide precios actualizados", "subject": "Solicitud de cotización",
         "body": f"{hello} {intro} ¿Podría enviarme su cotización actualizada de los materiales que manejan, con precio unitario y tiempo de entrega?\n{sign}"},
        {"key": "disponibilidad", "label": "Consultar disponibilidad", "hint": "¿Hay stock de lo que necesito?", "subject": "Consulta de disponibilidad de materiales",
         "body": f"{hello} {intro} Quisiera confirmar si cuentan con stock disponible de los materiales que les solicitaremos esta semana.\n{sign}"},
        {"key": "precios", "label": "Pedir lista de precios", "hint": "Excel o PDF vigente", "subject": "Lista de precios vigente",
         "body": f"{hello} {intro} ¿Me puede compartir su lista de precios vigente en Excel o PDF para actualizar nuestro catálogo?\n{sign}"},
        {"key": "seguimiento", "label": "Seguimiento de un pedido", "hint": "Estado y fecha de entrega", "subject": "Seguimiento de nuestro pedido",
         "body": f"{hello} {intro} Quisiera conocer el estado de nuestro pedido y la fecha estimada de entrega.\n{sign}"},
        {"key": "entrega", "label": "Coordinar entrega en obra", "hint": "Día, hora y dirección", "subject": "Coordinación de entrega en obra",
         "body": f"{hello} {intro} Quisiera coordinar la entrega de nuestro pedido en obra: día, horario y persona que recibe.\n{sign}"},
        {"key": "comprobante", "label": "Pedir factura o comprobante", "hint": "Documento de la compra", "subject": "Envío de factura o comprobante",
         "body": f"{hello} {intro} ¿Podría enviarnos la factura o el comprobante de la última compra para nuestro registro?\n{sign}"},
    ]


def whatsapp_url(phone: str | None, text: str) -> str:
    return f"https://wa.me/{whatsapp_number(phone)}?text={quote(text)}"


def gmail_url(email: str, subject: str, body: str) -> str:
    return f"https://mail.google.com/mail/?view=cm&fs=1&to={quote(email)}&su={quote(subject)}&body={quote(body)}"


def outlook_url(email: str, subject: str, body: str) -> str:
    return f"https://outlook.live.com/owa/?path=/mail/action/compose&to={quote(email)}&subject={quote(subject)}&body={quote(body)}"


def mailto_url(email: str, subject: str, body: str) -> str:
    return f"mailto:{quote(email)}?subject={quote(subject)}&body={quote(body)}"
