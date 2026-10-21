"""Manual de usuario: punto de entrada del módulo (se muestra desde el menú «Sistema › Manual de Usuario»).

El contenido está en `manual_data.py` y el dibujo en `manual_ui.py`; aquí solo se conecta con el menú."""
from modules import manual_ui


def show() -> None:
    manual_ui.render()
