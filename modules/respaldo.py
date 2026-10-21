"""Módulo Respaldo: descarga una copia completa de la base (todas las tablas) en un ZIP,
con cifrado opcional, y explica cómo restaurarla."""


import streamlit as st

from core.version import APP_VERSION
from db import repository as repo
from modules import forms, security, ui
from utils.backup import to_zip
from utils import clock

LAST_KEY = "_last_backup"


def render() -> None:
    ui.page_header(
        "Seguridad",
        "Respaldo de datos",
        "Una copia completa de todo lo registrado (materiales, proveedores, órdenes, stock, vales, obras, asistencia…) para guardarla fuera del sistema.",
    )

    forms.section("1. Genera el respaldo", "Se descarga un ZIP con un archivo CSV por tabla; se puede abrir con Excel. Los documentos adjuntos (fotos y PDF) no van dentro del ZIP: solo se respalda su lista; los archivos viven en el depósito «adjuntos» de Supabase.")
    with st.container(border=True):
        encrypt = st.checkbox(
            "Proteger con contraseña (cifrado AES-256)", value=True, key="backup_encrypt",
            help="Recomendado: el respaldo incluye los datos de las cuentas de acceso. Sin la contraseña no se puede abrir.",
        )
        password = None
        if encrypt:
            password = st.text_input("Contraseña del respaldo", type="password", key="backup_password",
                                     help="Guárdala aparte: sin ella el respaldo no se puede abrir ni restaurar.")
        if st.button("Generar respaldo", type="primary", icon=":material/backup:", width="stretch"):
            issues = security.password_issues(password) if encrypt else []
            if forms.errors(issues):
                return
            try:
                tables = repo.dump_tables()
                data = to_zip(tables, password if encrypt else None, APP_VERSION)
            except Exception as exc:
                ui.db_error(exc, "No se pudo generar el respaldo. Inténtalo de nuevo.")
                return
            st.session_state[LAST_KEY] = {
                "data": data, "stamp": clock.now(), "encrypted": encrypt,
                "rows": {name: len(df) for name, df in tables.items()},
            }
            ui.log(f"Respaldo generado ({sum(len(d) for d in tables.values())} filas, {'cifrado' if encrypt else 'sin cifrar'}).")

    last = st.session_state.get(LAST_KEY)
    if last:
        total = sum(last["rows"].values())
        st.success(
            f"Respaldo listo: {len(last['rows'])} tablas y {total} filas, "
            f"{'cifrado' if last['encrypted'] else 'sin cifrar'}. Descárgalo y guárdalo fuera de este equipo.",
            icon=":material/check_circle:",
        )
        st.download_button(
            "Descargar respaldo (ZIP)", data=last["data"], file_name=f"respaldo_mrp_{last['stamp']:%Y%m%d_%H%M}.zip",
            mime="application/zip", type="primary", width="stretch", icon=":material/download:",
        )
        with st.expander("Contenido del respaldo"):
            st.dataframe(
                [{"Tabla": name, "Filas": rows} for name, rows in last["rows"].items()], hide_index=True, width="stretch",
            )

    forms.section("2. Restaurar", "Para volver a cargar un respaldo (por ejemplo, tras borrar datos por error).")
    st.markdown(
        "La restauración se hace desde un equipo con el proyecto, con la clave de servicio configurada:\n\n"
        "```bash\npython scripts/restore_backup.py ruta/al/respaldo.zip --password TU_CLAVE\n```\n"
        "Carga las tablas en orden y se puede repetir sin duplicar datos; no borra lo que hoy existe y no esté en el respaldo."
    )
    forms.section("3. Respaldo automático semanal", "GitHub puede generarlo solo, cifrado, cada semana.")
    st.caption(
        "En el repositorio, Settings → Secrets → Actions, agrega SUPABASE_URL, SUPABASE_SERVICE_KEY y BACKUP_PASSWORD. "
        "El flujo «Respaldo semanal» (Actions) guarda el ZIP cifrado 30 días. Sin BACKUP_PASSWORD no se ejecuta, para no subir datos sin cifrar."
    )
