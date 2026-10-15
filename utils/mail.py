"""Enlaces `mailto:` para abrir el programa de correo del usuario con el mensaje ya escrito.

No se envía nada desde el servidor: el usuario revisa el mensaje, adjunta el PDF descargado y lo manda él."""
from __future__ import annotations

from urllib.parse import quote

MAX_BODY = 1500  # los programas de correo cortan los enlaces largos


def mailto_url(to: str | None, subject: str, body: str) -> str:
    """`mailto:` con destinatario (puede ir vacío), asunto y texto. El texto se recorta si es muy largo."""
    body = body if len(body) <= MAX_BODY else body[: MAX_BODY - 40].rstrip() + "\n… (mensaje recortado)"
    address = quote((to or "").strip(), safe="@,.+-_")
    return f"mailto:{address}?subject={quote(subject)}&body={quote(body)}"
