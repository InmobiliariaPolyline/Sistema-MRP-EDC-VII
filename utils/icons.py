"""Iconos vectoriales del sistema (24 × 24, solo trazo): los usan los PDF (`utils/pdf_style.py`) y las ventanas de ayuda.

Son formas simples dibujadas a mano: no dependen de ninguna fuente de iconos ni de internet. `svg()` devuelve un `<svg>`
en línea que toma el color del texto (`currentColor`), así sigue el tema claro u oscuro."""
from __future__ import annotations

import re

ICONS = {
    "order": '<rect x="5" y="3" width="14" height="18" rx="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="12" y2="17"/>',
    "truck": '<rect x="2" y="6" width="12" height="10" rx="1"/><path d="M14 9 L19 9 L22 12 L22 16 L14 16 Z"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
    "box": '<path d="M12 3 L21 7.5 L21 16.5 L12 21 L3 16.5 L3 7.5 Z"/><polyline points="3,7.5 12,12 21,7.5"/><line x1="12" y1="12" x2="12" y2="21"/>',
    "building": '<rect x="5" y="3" width="14" height="18" rx="1"/><line x1="9" y1="7" x2="10" y2="7"/><line x1="14" y1="7" x2="15" y2="7"/><line x1="9" y1="11" x2="10" y2="11"/><line x1="14" y1="11" x2="15" y2="11"/><rect x="10" y="15" width="4" height="6"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21 C4 16 8 14 12 14 C16 14 20 16 20 21"/>',
    "phone": '<rect x="7" y="2" width="10" height="20" rx="2"/><line x1="11" y1="18" x2="13" y2="18"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><polyline points="3,7 12,13 21,7"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="16" y1="3" x2="16" y2="7"/>',
    "coin": '<circle cx="12" cy="12" r="9"/><path d="M15 9 C14 8 13 7.5 12 7.5 C10.5 7.5 9.5 8.3 9.5 9.5 C9.5 12 14.5 11 14.5 14 C14.5 15.2 13.5 16.5 12 16.5 C10.8 16.5 9.8 16 9 15"/><line x1="12" y1="6" x2="12" y2="18"/>',
    "pin": '<path d="M12 21 L6 11 C4.5 8 6.5 4 12 4 C17.5 4 19.5 8 18 11 Z"/><circle cx="12" cy="10" r="2"/>',
    "check": '<circle cx="12" cy="12" r="9"/><polyline points="8,12.5 11,15.5 16,9"/>',
    "alert": '<path d="M12 3 L22 20 L2 20 Z"/><line x1="12" y1="9" x2="12" y2="14"/><line x1="12" y1="17" x2="12" y2="17.5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><polyline points="12,7 12,12 16,14"/>',
    "note": '<path d="M5 21 L5 5 C5 4 6 3 7 3 L17 3 C18 3 19 4 19 5 L19 15 L13 21 Z"/><polyline points="13,21 13,15 19,15"/>',
    "chart": '<line x1="4" y1="20" x2="20" y2="20"/><rect x="6" y="12" width="3" height="8"/><rect x="11" y="7" width="3" height="13"/><rect x="16" y="4" width="3" height="16"/>',
    "layers": '<polyline points="3,9 12,4 21,9 12,14 3,9"/><polyline points="3,13 12,18 21,13"/>',
    "list": '<line x1="9" y1="6" x2="20" y2="6"/><line x1="9" y1="12" x2="20" y2="12"/><line x1="9" y1="18" x2="20" y2="18"/><circle cx="5" cy="6" r="1"/><circle cx="5" cy="12" r="1"/><circle cx="5" cy="18" r="1"/>',
    "sign": '<path d="M4 20 C8 20 8 12 11 12 C13 12 12 17 14 17 C16 17 17 14 20 14"/><line x1="4" y1="22" x2="20" y2="22"/>',
    "undo": '<polyline points="9,5 4,10 9,15"/><path d="M4 10 L15 10 C18 10 20 12 20 15 C20 18 18 20 15 20 L11 20"/>',
    "scale": '<line x1="12" y1="4" x2="12" y2="20"/><line x1="7" y1="20" x2="17" y2="20"/><path d="M4 8 L20 8"/><path d="M4 8 L2 14 L7 14 Z"/><path d="M20 8 L17 14 L22 14 Z"/>',
    "info": '<circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16"/><line x1="12" y1="8" x2="12" y2="8.5"/>',
    "shield": '<path d="M12 3 L20 6 L20 12 C20 17 16.5 20 12 21 C7.5 20 4 17 4 12 L4 6 Z"/><polyline points="9,12 11,14 15,10"/>',
    "download": '<line x1="12" y1="4" x2="12" y2="15"/><polyline points="7,11 12,16 17,11"/><line x1="5" y1="20" x2="19" y2="20"/>',
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "bulb": '<path d="M9 18 L15 18"/><path d="M10 21 L14 21"/><path d="M12 3 C8.5 3 6 5.5 6 8.5 C6 10.7 7.2 12 8.5 13.3 C9.2 14 9.5 14.7 9.5 16 L14.5 16 C14.5 14.7 14.8 14 15.5 13.3 C16.8 12 18 10.7 18 8.5 C18 5.5 15.5 3 12 3 Z"/>',
    "arrow": '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="13,6 19,12 13,18"/>',
    "home": '<path d="M3 11 L12 4 L21 11"/><path d="M5 10 L5 20 L19 20 L19 10"/><rect x="10" y="14" width="4" height="6"/>',
    "search": '<circle cx="11" cy="11" r="6"/><line x1="16" y1="16" x2="20" y2="20"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11 L8 8 C8 5.5 9.8 4 12 4 C14.2 4 16 5.5 16 8 L16 11"/>',
    "x": '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
    "calendar2": '<rect x="3" y="5" width="18" height="16" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/>',
    "tool": '<path d="M14 6 C14 4 16 3 18 4 L15.5 6.5 L17.5 8.5 L20 6 C21 8 20 10 18 10 C17.5 10 17 10 16.5 9.8 L8 18.3 C7 19.3 5.5 19.3 4.6 18.4 C3.7 17.5 3.7 16 4.7 15 L13.2 6.5 C13 6.3 13 6.2 13 6 Z"/>',
}


def svg(name: str, size: int = 20, stroke: float = 1.9, color: str = "currentColor") -> str:
    """Icono como `<svg>` en línea (para HTML). `color` puede ser «currentColor» o un color CSS."""
    return (
        f'<svg class="mrp-ico" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>'
    )


# Iconos añadidos para sustituir a los emojis de la interfaz
ICONS.update({
    "trash": '<polyline points="4,7 20,7"/><path d="M9 7 V4 H15 V7"/><path d="M6 7 L7 21 H17 L18 7"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>',
    "edit": '<path d="M4 20 L4 16 L16 4 L20 8 L8 20 Z"/><line x1="13" y1="7" x2="17" y2="11"/>',
    "send": '<path d="M21 3 L3 10 L10 13 L13 21 Z"/><line x1="10" y1="13" x2="21" y2="3"/>',
    "helmet": '<path d="M4 17 V15 C4 10 7.5 6 12 6 C16.5 6 20 10 20 15 V17 Z"/><line x1="2.5" y1="17" x2="21.5" y2="17"/><line x1="12" y1="6" x2="12" y2="12"/>',
    "receipt": '<path d="M6 3 H18 V21 L15 19 L12 21 L9 19 L6 21 Z"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="9" y1="12" x2="15" y2="12"/>',
    "factory": '<path d="M3 21 V10 L9 14 V10 L15 14 V6 H19 V21 Z"/><line x1="7" y1="18" x2="8" y2="18"/><line x1="12" y1="18" x2="13" y2="18"/>',
    "shop": '<path d="M4 9 L6 4 H18 L20 9"/><path d="M4 9 C4 11 7 11 8 9 C9 11 12 11 12 9 C12 11 15 11 16 9 C17 11 20 11 20 9"/><path d="M5 11 V20 H19 V11"/>',
    "star": '<polygon points="12,3 14.7,9 21,9.6 16.2,13.8 17.7,20 12,16.7 6.3,20 7.8,13.8 3,9.6 9.3,9"/>',
    "key": '<circle cx="8" cy="15" r="4"/><line x1="11" y1="12" x2="20" y2="4"/><line x1="17" y1="7" x2="19" y2="9"/>',
    "idcard": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M6 16 C6 14.5 7.5 14 9 14 C10.5 14 12 14.5 12 16"/><line x1="14" y1="10" x2="18" y2="10"/><line x1="14" y1="14" x2="18" y2="14"/>',
    "ban": '<circle cx="12" cy="12" r="9"/><line x1="5.6" y1="5.6" x2="18.4" y2="18.4"/>',
    "ruler": '<path d="M3 17 L17 3 L21 7 L7 21 Z"/><line x1="7" y1="13" x2="9" y2="15"/><line x1="10" y1="10" x2="12" y2="12"/><line x1="13" y1="7" x2="15" y2="9"/>',
    "trend": '<polyline points="3,17 9,11 13,15 21,6"/><polyline points="15,6 21,6 21,12"/>',
    "database": '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6 V18 C4 19.7 7.6 21 12 21 C16.4 21 20 19.7 20 18 V6"/><path d="M4 12 C4 13.7 7.6 15 12 15 C16.4 15 20 13.7 20 12"/>',
    "grid": '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    "file": '<path d="M6 3 H14 L19 8 V21 H6 Z"/><polyline points="14,3 14,8 19,8"/>',
    "clipboard": '<rect x="5" y="4" width="14" height="17" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/><line x1="9" y1="11" x2="15" y2="11"/><line x1="9" y1="15" x2="15" y2="15"/>',
    "clip": '<path d="M20 11 L12 19 C9.5 21.5 5.5 17.5 8 15 L15 8 C16.5 6.5 18.5 8.5 17 10 L10 17"/>',
    "tag": '<path d="M3 12 V4 H11 L21 14 L14 21 Z"/><circle cx="7.5" cy="8.5" r="1"/>',
    "map": '<polygon points="3,6 9,4 15,6 21,4 21,18 15,20 9,18 3,20"/><line x1="9" y1="4" x2="9" y2="18"/><line x1="15" y1="6" x2="15" y2="20"/>',
    "chat": '<path d="M4 5 H20 V16 H12 L7 20 V16 H4 Z"/>',
    "sparkle": '<path d="M12 3 L14 10 L21 12 L14 14 L12 21 L10 14 L3 12 L10 10 Z"/>',
    "refresh": '<path d="M20 12 A8 8 0 1 1 17.5 6.3"/><polyline points="20,4 20,9 15,9"/>',
    "upload": '<line x1="12" y1="16" x2="12" y2="5"/><polyline points="7,9 12,4 17,9"/><line x1="5" y1="20" x2="19" y2="20"/>',
    "eye": '<path d="M2 12 C5 7 8.5 5 12 5 C15.5 5 19 7 22 12 C19 17 15.5 19 12 19 C8.5 19 5 17 2 12 Z"/><circle cx="12" cy="12" r="3"/>',
    "discount": '<circle cx="12" cy="12" r="9.5"/><line x1="8" y1="16" x2="16" y2="8"/><circle cx="8.8" cy="8.8" r="1.5"/><circle cx="15.2" cy="15.2" r="1.5"/>',
    "arrow_down": '<line x1="12" y1="5" x2="12" y2="19"/><polyline points="6,13 12,19 18,13"/>',
    "arrow_up": '<line x1="12" y1="19" x2="12" y2="5"/><polyline points="6,11 12,5 18,11"/>',
})

# emoji → (icono propio, icono Material de Streamlit). Sirve para los componentes en HTML (`glyph`) y para los botones,
# pestañas, desplegables y avisos de Streamlit (`material`).
EMOJI = {
    "📦": ("box", "inventory_2"), "🏬": ("building", "warehouse"), "⚠️": ("alert", "warning"), "⚠": ("alert", "warning"),
    "🚚": ("truck", "local_shipping"), "🧾": ("receipt", "receipt_long"), "🏭": ("factory", "factory"), "🏪": ("shop", "storefront"),
    "🧱": ("layers", "layers"), "👷": ("helmet", "engineering"), "🏗️": ("building", "construction"), "🏗": ("building", "construction"),
    "🔎": ("search", "search"), "🔍": ("search", "search"), "🕘": ("clock", "schedule"), "🕒": ("clock", "schedule"), "⏱️": ("clock", "timer"),
    "📅": ("calendar", "calendar_month"), "📍": ("pin", "location_on"), "🗺️": ("map", "map"), "✅": ("check", "check_circle"),
    "🚫": ("ban", "block"), "📋": ("clipboard", "assignment"), "📄": ("file", "description"), "🗂️": ("layers", "folder"),
    "📎": ("clip", "attach_file"), "🗑️": ("trash", "delete"), "🗑": ("trash", "delete"), "✏️": ("edit", "edit"), "ℹ️": ("info", "info"),
    "📞": ("phone", "call"), "✉️": ("mail", "mail"), "💬": ("chat", "chat"), "💰": ("coin", "payments"), "💳": ("coin", "credit_card"),
    "⚖️": ("scale", "balance"), "📐": ("ruler", "straighten"), "📈": ("trend", "trending_up"), "🧩": ("grid", "extension"),
    "🗄️": ("database", "database"), "🔒": ("lock", "lock"), "🔑": ("key", "key"), "🏢": ("building", "business"), "🙍": ("user", "person"),
    "🪪": ("idcard", "badge"), "⭐": ("star", "star"), "📝": ("note", "edit_note"), "📤": ("send", "send"), "📥": ("download", "download"),
    "⬇️": ("arrow_down", "download"), "⬇": ("arrow_down", "download"), "↩️": ("undo", "undo"), "➕": ("plus", "add"), "✖": ("x", "close"),
    "🔄": ("refresh", "sync"), "💡": ("bulb", "lightbulb"), "✨": ("sparkle", "auto_awesome"), "🏷️": ("tag", "sell"),
    "⏰": ("clock", "alarm"), "📒": ("note", "menu_book"), "🧮": ("grid", "calculate"),
}
_EMOJI_BY_LENGTH = sorted(EMOJI, key=len, reverse=True)


def glyph(token: str, size: int = 20, stroke: float = 1.9) -> str:
    """Un emoji o el nombre de un icono → `<svg>` en línea. Lo que no se reconoce se devuelve tal cual (escapado por quien llama)."""
    token = (token or "").strip()
    name = EMOJI.get(token, (token, ""))[0]
    return svg(name, size, stroke) if name in ICONS else token


def material(token: str, default: str = "") -> str:
    """Un emoji → icono de Streamlit (`:material/nombre:`) para botones, pestañas, desplegables y avisos."""
    pair = EMOJI.get((token or "").strip())
    return f":material/{pair[1]}:" if pair else default


def split_lead(text: str) -> tuple[str, str]:
    """«🗑 Eliminar» → («:material/delete:», «Eliminar»). Si el texto no empieza con un emoji conocido: («», texto)."""
    for emoji in _EMOJI_BY_LENGTH:
        if text.startswith(emoji):
            return material(emoji), text[len(emoji):].lstrip("  ️")
    return "", text


_BY_MATERIAL = {pair[1]: pair[0] for pair in EMOJI.values()}
_TOKEN = re.compile(r":material/(\w+):|" + "|".join(re.escape(e) for e in _EMOJI_BY_LENGTH))


def render_tokens(html_text: str, size: int = 16, stroke: float = 2.0) -> str:
    """En un texto HTML ya armado, cambia cada emoji o `:material/nombre:` por su icono vectorial (para `unsafe_allow_html`)."""
    def swap(match: re.Match) -> str:
        token = match.group(0)
        name = _BY_MATERIAL.get(match.group(1)) if match.group(1) else EMOJI[token][0]
        return svg(name, size, stroke) if name in ICONS else token
    return _TOKEN.sub(swap, html_text)


def brand_mark(size: int = 24, animated: bool = False) -> str:
    """Marca del sistema: un cubo isométrico con un nodo al centro (material que fluye entre proveedor, almacén y obra).
    Con `animated` el trazo se dibuja solo al aparecer (pantalla de carga y acceso)."""
    draw = " mrp-mark-draw" if animated else ""
    return (
        f'<svg class="mrp-mark{draw}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="{size}" height="{size}" fill="none" '
        'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path class="mrp-mark-a" pathLength="100" d="M24 5 L41 14.5 L41 33.5 L24 43 L7 33.5 L7 14.5 Z"/>'
        '<path class="mrp-mark-b" pathLength="100" d="M7 14.5 L24 24 L41 14.5"/>'
        '<path class="mrp-mark-c" pathLength="100" d="M24 24 L24 43"/>'
        '<circle class="mrp-mark-d" cx="24" cy="24" r="2.6" fill="currentColor" stroke="none"/>'
        "</svg>"
    )
