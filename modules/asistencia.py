"""Módulo de Asistencia: pasar lista por día (quién fue a qué obra) y ver el
resumen por trabajador y por obra."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import forms, ui

STATUSES = ["presente", "tardanza", "permiso", "ausente"]
BLANK = "—"
NO_SITE = "Sin obra"
STATUS_COLORS = {"presente": "green", "tardanza": "amber", "permiso": "blue", "ausente": "red"}
DRAFTS_KEY = "_att_drafts"
EDITOR_SEED_KEY = "_att_editor_seed"
ALL_WORKERS = "Todos los trabajadores"


def _clear_filter() -> None:
    st.session_state["att_filter"] = ALL_WORKERS


def _capture_editor_draft(day: str, editor_key: str, seed: list[dict]) -> None:
    """Captura las celdas antes de otra recarga; los índices se ligan a IDs estables."""
    changes = st.session_state.get(editor_key, {}).get("edited_rows", {})
    drafts = st.session_state.setdefault(DRAFTS_KEY, {}).setdefault(day, {})
    for index, original in enumerate(seed):
        row = {field: original[field] for field in ("Estado", "Obra", "Nota")}
        row.update({field: value for field, value in changes.get(index, {}).items() if field in row})
        drafts[original["worker_id"]] = row


def _discard_visible_drafts(day: str, worker_ids: list[str]) -> None:
    drafts = st.session_state.get(DRAFTS_KEY, {}).get(day, {})
    for worker_id in worker_ids:
        drafts.pop(worker_id, None)
    st.session_state.pop(EDITOR_SEED_KEY, None)


def render() -> None:
    ui.page_header(
        "Personal",
        "Asistencia",
        "Pasa lista cada día: quién vino, a qué obra fue y quién faltó.",
    )
    tab_list, tab_summary = st.tabs(["Pasar lista", "Resumen"])
    with tab_list:
        ui.tip("Elige un estado y una obra en cada fila. «Marcar pendientes presentes» prepara el borrador; «Guardar asistencia» confirma los registros visibles.")
        _render_roll_call()
    with tab_summary:
        _render_summary()


def _render_roll_call() -> None:
    workers = repo.list_workers()
    if workers.empty:
        ui.empty_state("Aún no hay trabajadores", "Registra trabajadores en el módulo Trabajadores para comenzar a pasar lista.", icon="👷")
        return
    workers = workers[workers["active"].fillna(True).astype(bool)]
    if workers.empty:
        ui.empty_state("No hay trabajadores activos", "Activa trabajadores desde su módulo para incluirlos en la lista de asistencia.", icon="👷")
        return
    total_workers = len(workers)
    sites = repo.list_project_sites()
    site_names = [NO_SITE] + sites["name"].tolist()
    site_by_name = dict(zip(sites["name"], sites["id"]))

    forms.section("1. Fecha y trabajadores", "El filtro usa la obra asignada a cada trabajador. Puedes cambiar la obra de la jornada en la tabla.")
    c1, c2 = st.columns([2, 3])
    day = c1.date_input("Fecha", value=date.today(), max_value=date.today(), key="att_date")
    site_filter = c2.selectbox("Mostrar", [ALL_WORKERS] + sites["name"].tolist(), key="att_filter",
                               help="Filtra por la obra en la que están asignados.")
    if site_filter != ALL_WORKERS:
        workers = workers[workers["site_name"] == site_filter]
    ui.result_count(len(workers), total_workers, noun="trabajadores activos")
    if site_filter != ALL_WORKERS:
        st.button("Mostrar todos", key="att_clear_filter", on_click=_clear_filter)
    if workers.empty:
        ui.empty_state("No hay trabajadores en esta obra", "Prueba «Mostrar todos» o asigna trabajadores a esta obra desde su módulo.", icon="🔎")
        return

    day_key = day.isoformat()
    existing = repo.list_attendance(day.isoformat(), day.isoformat())
    saved = {r["worker_id"]: r for r in existing.to_dict("records")}
    drafts = st.session_state.setdefault(DRAFTS_KEY, {}).setdefault(day_key, {})

    table = pd.DataFrame(
        {
            "worker_id": workers["id"].tolist(),
            "Trabajador": workers["full_name"].tolist(),
            "Cuadrilla": workers["group_name"].fillna("").tolist(),
            "Estado": [saved[w]["status"] if w in saved else BLANK for w in workers["id"]],
            "Obra": [
                (saved[w]["site_name"] or NO_SITE) if w in saved else (s or NO_SITE)
                for w, s in zip(workers["id"], workers["site_name"])
            ],
            "Nota": [(saved[w]["note"] or "") if w in saved else "" for w in workers["id"]],
        }
    )

    for index, row in table.iterrows():
        for field, value in drafts.get(row["worker_id"], {}).items():
            table.at[index, field] = value

    # Mantener una base estable mientras el editor aplica sus deltas. Al cambiar
    # fecha/filtro o hacer una acción de borrador, se crea otra base y clave.
    scope = (day_key, site_filter, tuple(table["worker_id"]), tuple(site_names))
    seed = st.session_state.get(EDITOR_SEED_KEY)
    if not seed or seed["scope"] != scope or seed["key"] not in st.session_state:
        revision = st.session_state.get("_att_editor_revision", 0) + 1
        st.session_state["_att_editor_revision"] = revision
        seed = {"scope": scope, "rows": table.to_dict("records"), "key": f"att_editor_{revision}"}
        st.session_state[EDITOR_SEED_KEY] = seed
    seeded_table = pd.DataFrame(seed["rows"])
    worker_ids = seeded_table["worker_id"].tolist()

    forms.section("2. Prepara la lista", "Las ediciones quedan en borrador durante esta sesión, incluso si cambias de fecha u obra.")
    st.caption("«—» omite la fila al guardar; no elimina un registro existente. «Sin obra» es válido. La nota es opcional.")
    edited = st.data_editor(
        seeded_table.drop(columns=["worker_id"]),
        hide_index=True,
        width="stretch",
        disabled=["Trabajador", "Cuadrilla"],
        column_config={
            "Estado": st.column_config.SelectboxColumn(options=[BLANK] + STATUSES, required=True,
                                                       help="Presente, tardanza, permiso o ausente. «—» no registra esta fila."),
            "Obra": st.column_config.SelectboxColumn(options=site_names, required=True,
                                                     help="Obra de esta jornada; puede diferir de la asignación habitual."),
            "Nota": st.column_config.TextColumn("Nota (opcional)", max_chars=500,
                                                 help="Ej. Llegó 15 minutos tarde. Hasta 500 caracteres."),
        },
        key=seed["key"],
        on_change=_capture_editor_draft,
        args=(day_key, seed["key"], seed["rows"]),
    )

    visible = edited.reset_index(drop=True).to_dict("records")
    for worker_id, row in zip(worker_ids, visible):
        drafts[worker_id] = {field: row[field] for field in ("Estado", "Obra", "Nota")}

    if st.button("✅ Marcar pendientes presentes", key="att_mark_present", width="stretch",
                 help="Completa solo las filas visibles con «—» y conserva obras, notas y otros estados. No guarda registros."):
        marked = 0
        for worker_id, row in zip(worker_ids, visible):
            if row["Estado"] == BLANK:
                drafts[worker_id]["Estado"] = "presente"
                marked += 1
        if marked:
            st.session_state.pop(EDITOR_SEED_KEY, None)
            st.rerun()
        else:
            st.info("Todas las filas visibles ya tienen un estado. Revisa la lista antes de guardar.")

    forms.section("3. Revisa y guarda", f"Fecha: {day:%d/%m/%Y}. Solo se guardan los trabajadores visibles que tienen un estado.")
    ready = sum(row["Estado"] in STATUSES for row in visible)
    c_ready, c_pending = st.columns(2)
    c_ready.metric("Con estado", ready)
    c_pending.metric("Sin registrar", len(visible) - ready)
    breakdown = [f"{status.capitalize()}: {sum(row['Estado'] == status for row in visible)}" for status in STATUSES]
    st.caption(" · ".join(breakdown))
    cancel, save = st.columns([1, 2])
    if cancel.button("Descartar cambios visibles", key="att_discard", width="stretch",
                     help="Restaura los registros guardados de estas filas. Conserva borradores de otras fechas y trabajadores ocultos."):
        _discard_visible_drafts(day_key, worker_ids)
        st.rerun()
    if save.button("Guardar asistencia", type="primary", width="stretch", key="att_save"):
        issues = []
        records = []
        if day > date.today():
            issues.append("Fecha: no puedes registrar una jornada futura.")
        for worker_id, row in zip(worker_ids, visible):
            status = row["Estado"]
            if status == BLANK:
                continue
            name = row["Trabajador"]
            if status not in STATUSES:
                issues.append(f"{name}: elige un estado de asistencia válido.")
            if row["Obra"] not in site_names:
                issues.append(f"{name}: elige una obra de la lista o «{NO_SITE}».")
            note = "" if pd.isna(row["Nota"]) else str(row["Nota"]).strip()
            issues.extend(f"{name}: {issue}" for issue in forms.validate({"Nota (opcional)": note}))
            records.append((worker_id, row["Obra"], status, note or None))
        if not records:
            issues.append("Estado: elige al menos un estado o usa «Marcar pendientes presentes» antes de guardar.")
        if forms.errors(issues):
            return
        for worker_id, site_name, status, note in records:
            repo.set_attendance(
                worker_id, site_by_name.get(site_name), day_key, status, note,
            )
        _discard_visible_drafts(day_key, worker_ids)
        ui.flash(f"Asistencia del {day:%d/%m/%Y} guardada ({len(records)} registros).", "📋")
        st.rerun()


def _render_summary() -> None:
    c1, c2 = st.columns([2, 3])
    days = c1.selectbox("Periodo", [7, 15, 30, 90], index=2, format_func=lambda d: f"Últimos {d} días", key="att_days")
    end = date.today()
    start = end - timedelta(days=days - 1)
    records = repo.list_attendance(start.isoformat(), end.isoformat())
    if records.empty:
        ui.empty_state("Sin asistencia en este periodo", "Prueba un periodo más amplio o guarda una jornada en «Pasar lista».", icon="📋")
        return

    counts = records.pivot_table(index="worker_name", columns="status", values="id", aggfunc="count", fill_value=0)
    for status in STATUSES:
        if status not in counts.columns:
            counts[status] = 0
    counts = counts[STATUSES]
    total = int(counts.to_numpy().sum())
    present = int(counts["presente"].sum() + counts["tardanza"].sum())
    ui.stat_grid(
        [
            ui.stat_card("📋", total, "Registros", f"últimos {days} días"),
            ui.stat_card("✅", f"{present / total * 100:.0f}%" if total else "—", "Asistencia", "presentes + tardanzas"),
            ui.stat_card("🚫", int(counts["ausente"].sum()), "Faltas", "ausencias registradas", warn=int(counts["ausente"].sum()) > 0),
        ]
    )

    st.markdown('<div class="mrp-eyebrow">Por trabajador</div>', unsafe_allow_html=True)
    st.dataframe(
        counts.rename(columns=str.capitalize).reset_index().rename(columns={"worker_name": "Trabajador"}),
        hide_index=True,
        width="stretch",
    )

    by_site = records[records["status"].isin(["presente", "tardanza"])]
    if not by_site.empty:
        st.markdown('<div class="mrp-eyebrow">Por obra (jornadas trabajadas)</div>', unsafe_allow_html=True)
        site_counts = by_site.assign(site_name=by_site["site_name"].fillna(NO_SITE)).groupby("site_name").size().reset_index(name="Jornadas")
        st.dataframe(site_counts.rename(columns={"site_name": "Obra"}), hide_index=True, width="stretch")

    with st.expander("Detalle día por día"):
        detail = records.assign(site_name=records["site_name"].fillna(NO_SITE))[["work_date", "worker_name", "site_name", "status", "note"]]
        st.dataframe(
            detail.rename(columns={"work_date": "Fecha", "worker_name": "Trabajador", "site_name": "Obra", "status": "Estado", "note": "Nota"}),
            hide_index=True,
            width="stretch",
        )
