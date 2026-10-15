"""Bloque reutilizable de documentos adjuntos (facturas, guías de remisión, vales firmados, fotos).

    attachments_ui.render("orden", order_id)

Muestra los archivos ya subidos (con «Abrir» para descargarlos y verlos) y permite subir otros.
El archivo solo se lee de la base al pulsar «Abrir», para no descargar todo en cada pantalla."""
from __future__ import annotations

import streamlit as st

from db import repository as repo
from modules import ui
from utils import attachments as rules


def _stamp(value) -> str:
    return str(value)[:16].replace("T", " ")


def render(entity_type: str, entity_id: str, *, expanded: bool = False, key: str | None = None) -> None:
    key = key or f"{entity_type}_{entity_id}"
    files = repo.list_attachments(entity_type, entity_id)
    count = len(files)
    label = f"📎 Documentos adjuntos ({count})" if count else "📎 Documentos adjuntos"
    open_key, uploader_key = f"att_open_{key}", f"att_up_n_{key}"
    with st.expander(label, expanded=expanded or count > 0 and st.session_state.get(open_key) is not None):
        if files.empty:
            st.caption(
                f"Aún no hay documentos de esta {rules.ENTITY_TYPES.get(entity_type, 'ficha')}. "
                "Sube la foto o el PDF de la factura, la guía de remisión o el vale firmado."
            )
        for row in files.to_dict("records"):
            c1, c2, c3 = st.columns([6, 1.6, 1])
            c1.markdown(
                f'<div class="mrp-row-name">{row["filename"]}</div>'
                f'<div class="mrp-row-sub">{rules.human_size(row["size_bytes"])} · {_stamp(row["created_at"])} · {row.get("uploaded_by") or "sistema"}</div>',
                unsafe_allow_html=True,
            )
            if c2.button("Abrir", key=f"att_view_{row['id']}", width="stretch"):
                st.session_state[open_key] = row["id"]
            if c3.button("🗑", key=f"att_del_{row['id']}", help="Quitar documento"):
                ui.confirm_delete(
                    f"¿Quitar «{row['filename']}»? El archivo se borra y no se puede recuperar.",
                    lambda aid=row["id"], name=row["filename"]: _delete(aid, name),
                )
            if st.session_state.get(open_key) == row["id"]:
                _show(row["id"], open_key)

        st.markdown("**Subir un documento**")
        n = st.session_state.get(uploader_key, 0)
        upload = st.file_uploader(
            "PDF o imagen (máx. 10 MB)", type=[e.lstrip(".") for e in rules.ALLOWED], key=f"att_file_{key}_{n}", label_visibility="collapsed",
        )
        if upload is not None and st.button("Guardar documento", type="primary", key=f"att_save_{key}"):
            try:
                repo.add_attachment(entity_type, entity_id, upload.name, upload.getvalue(), ui.current_actor())
            except ValueError as exc:
                st.error(str(exc))
                return
            st.session_state[uploader_key] = n + 1  # vacía el selector de archivos
            ui.flash(f"Documento «{upload.name}» adjuntado a su {rules.ENTITY_TYPES.get(entity_type, 'ficha')}.", "📎")
            st.rerun()


def _show(attachment_id: str, open_key: str) -> None:
    try:
        meta, content = repo.read_attachment(attachment_id)
    except ValueError as exc:
        st.error(str(exc))
        return
    if (meta.get("content_type") or "").startswith("image/"):
        st.image(content, caption=meta["filename"], width="stretch")
    st.download_button(
        f"Descargar {meta['filename']}", data=content, file_name=meta["filename"], mime=meta.get("content_type") or "application/octet-stream",
        key=f"att_dl_{attachment_id}", icon=":material/download:",
    )
    if st.button("Cerrar vista", key=f"att_close_{attachment_id}"):
        st.session_state.pop(open_key, None)
        st.rerun()


def _delete(attachment_id: str, name: str) -> None:
    try:
        repo.delete_attachment(attachment_id)
    except ValueError as exc:
        ui.flash(f"No se pudo quitar «{name}»: {exc}", "⚠️", log=False)
        return
    ui.flash(f"Documento «{name}» quitado.", "🗑️")
