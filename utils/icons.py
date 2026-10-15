"""Iconos vectoriales del sistema (24 × 24, solo trazo): los usan los PDF (`utils/pdf_style.py`) y las ventanas de ayuda.

Son formas simples dibujadas a mano: no dependen de ninguna fuente de iconos ni de internet. `svg()` devuelve un `<svg>`
en línea que toma el color del texto (`currentColor`), así sigue el tema claro u oscuro."""
from __future__ import annotations

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
    "tool": '<path d="M14 6 C14 4 16 3 18 4 L15.5 6.5 L17.5 8.5 L20 6 C21 8 20 10 18 10 C17.5 10 17 10 16.5 9.8 L8 18.3 C7 19.3 5.5 19.3 4.6 18.4 C3.7 17.5 3.7 16 4.7 15 L13.2 6.5 C13 6.3 13 6.2 13 6 Z"/>',
}


def svg(name: str, size: int = 20, stroke: float = 1.9, color: str = "currentColor") -> str:
    """Icono como `<svg>` en línea (para HTML). `color` puede ser «currentColor» o un color CSS."""
    return (
        f'<svg class="mrp-ico" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>'
    )
