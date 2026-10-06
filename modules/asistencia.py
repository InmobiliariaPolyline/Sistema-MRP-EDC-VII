"""Módulo de Asistencia: pasar lista por día (quién fue a qué obra) y ver el
resumen por trabajador y por obra."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import ui

STATUSES = ["presente", "tardanza", "permiso", "ausente"]
BLANK = "—"
NO_SITE = "Sin obra"
STATUS_COLORS = {"presente": "green", "tardanza": "amber", "permiso": "blue", "ausente": "red"}


def render() -> None:
    ui.page_header(
        "Personal",
        "Asistencia",
        "Pasa lista cada día: quién vino, a qué obra fue y quién faltó.",
    )
    tab_list, tab_summary = st.tabs(["Pasar lista", "Resumen"])
    ui.tip("Ejemplo: en la tabla pulsa la celda «Estado» de cada trabajador y elige presente / ausente; luego «Guardar asistencia». «—» significa sin registrar.")
    with tab_list:
        _render_roll_call()
    with tab_summary:
        _render_summary()


def _render_roll_call() -> None:
    workers = repo.list_workers()
    if workers.empty:
        st.info("Todavía no hay trabajadores registrados (módulo Trabajadores).")
        return
    workers = workers[workers["active"].fillna(True).astype(bool)]
    sites = repo.list_project_sites()
    site_names = [NO_SITE] + sites["name"].tolist()
    site_by_name = dict(zip(sites["name"], sites["id"]))

    c1, c2 = st.columns([2, 3])
    day = c1.date_input("Fecha", value=date.today(), max_value=date.today(), key="att_date")
    site_filter = c2.selectbox("Mostrar", ["Todos los trabajadores"] + sites["name"].tolist(), key="att_filter",
                               help="Filtra por la obra en la que están asignados.")
    if site_filter != "Todos los trabajadores":
        workers = workers[workers["site_name"] == site_filter]
    if workers.empty:
        st.info("Nadie está asignado a esa obra.")
        return

    existing = repo.list_attendance(day.isoformat(), day.isoformat())
    saved = {r["worker_id"]: r for r in existing.to_dict("records")}

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

    edited = st.data_editor(
        table.drop(columns=["worker_id"]),
        hide_index=True,
        use_container_width=True,
        disabled=["Trabajador", "Cuadrilla"],
        column_config={
            "Estado": st.column_config.SelectboxColumn(options=[BLANK] + STATUSES, required=True),
            "Obra": st.column_config.SelectboxColumn(options=site_names, required=True),
            "Nota": st.column_config.TextColumn(),
        },
        key=f"att_editor_{day.isoformat()}_{site_filter}",
    )

    c_a, c_b = st.columns([2, 2])
    if c_a.button("✅ Marcar todos presentes", use_container_width=True):
        for worker_id, site_name in zip(table["worker_id"], table["Obra"]):
            if worker_id not in saved:
                repo.set_attendance(worker_id, site_by_name.get(site_name), day.isoformat(), "presente", None)
        ui.flash(f"Asistencia del {day:%d/%m/%Y}: todos presentes.", "📋")
        st.rerun()
    if c_b.button("Guardar asistencia", type="primary", use_container_width=True):
        count = 0
        for i, row in edited.reset_index(drop=True).iterrows():
            if row["Estado"] == BLANK:
                continue
            repo.set_attendance(
                table.loc[i, "worker_id"],
                site_by_name.get(row["Obra"]),
                day.isoformat(),
                row["Estado"],
                (row["Nota"] or "").strip() or None,
            )
            count += 1
        ui.flash(f"Asistencia del {day:%d/%m/%Y} guardada ({count} registros).", "📋")
        st.rerun()


def _render_summary() -> None:
    c1, c2 = st.columns([2, 3])
    days = c1.selectbox("Periodo", [7, 15, 30, 90], index=2, format_func=lambda d: f"Últimos {d} días", key="att_days")
    end = date.today()
    start = end - timedelta(days=days - 1)
    records = repo.list_attendance(start.isoformat(), end.isoformat())
    if records.empty:
        st.info("No hay asistencia registrada en este periodo.")
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
            ui.stat_card("✅", f"{present / total * 100:.0f}%", "Asistencia", "presentes + tardanzas"),
            ui.stat_card("🚫", int(counts["ausente"].sum()), "Faltas", "ausencias registradas", warn=int(counts["ausente"].sum()) > 0),
        ]
    )

    st.markdown('<div class="mrp-eyebrow">Por trabajador</div>', unsafe_allow_html=True)
    st.dataframe(
        counts.rename(columns=str.capitalize).reset_index().rename(columns={"worker_name": "Trabajador"}),
        hide_index=True,
        use_container_width=True,
    )

    by_site = records[records["status"].isin(["presente", "tardanza"])]
    if not by_site.empty:
        st.markdown('<div class="mrp-eyebrow">Por obra (jornadas trabajadas)</div>', unsafe_allow_html=True)
        site_counts = by_site.assign(site_name=by_site["site_name"].fillna(NO_SITE)).groupby("site_name").size().reset_index(name="Jornadas")
        st.dataframe(site_counts.rename(columns={"site_name": "Obra"}), hide_index=True, use_container_width=True)

    with st.expander("Detalle día por día"):
        detail = records.assign(site_name=records["site_name"].fillna(NO_SITE))[["work_date", "worker_name", "site_name", "status", "note"]]
        st.dataframe(
            detail.rename(columns={"work_date": "Fecha", "worker_name": "Trabajador", "site_name": "Obra", "status": "Estado", "note": "Nota"}),
            hide_index=True,
            use_container_width=True,
        )
