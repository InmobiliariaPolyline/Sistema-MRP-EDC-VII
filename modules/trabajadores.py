"""Módulo de Trabajadores (antes «Usuarios»): catálogo de personal de obra
—información personal, cuadrilla y obra donde trabajan, con su ubicación
en el mapa— y, cuando haga falta, el acceso al sistema (usuario/contraseña)
para quienes también deban entrar a administrarlo."""
import html
import math

import pandas as pd
import streamlit as st

from db import repository as repo
from db.auth import hash_password
from modules import forms, ui
from utils.geocode import google_maps_search_url, parse_coordinates, search_address

ROLES = ["operador", "admin"]
NO_GROUP = "Sin cuadrilla"
NO_SITE = "Sin obra asignada"


def render(user: dict) -> None:
    if user["role"] != "admin":
        ui.page_header("Trabajadores", "Trabajadores")
        st.error("Solo un administrador puede gestionar trabajadores.")
        return

    clicked = ui.page_header(
        "Personal de obra",
        "Trabajadores",
        "Información personal, cuadrilla y obra donde trabaja cada uno.",
        action_label="＋ Nuevo trabajador",
        action_key="new_worker_open",
    )
    if clicked:
        _new_worker_dialog()

    col1, col2 = st.columns(2)
    with col1:
        _render_groups_panel()
    with col2:
        _render_sites_panel()

    _render_workers_list()


# ---------------------------------------------------------------------------
# Cuadrillas y obras (catálogos de apoyo)
# ---------------------------------------------------------------------------

def _render_groups_panel() -> None:
    if st.session_state.pop("_group_reset_pending", False):
        st.session_state.pop("_group_name", None)
    groups = repo.list_work_groups()
    with st.expander(f"Cuadrillas ({len(groups)})"):
        forms.header("Nueva cuadrilla", "Agrupa al personal por especialidad o equipo.")
        with st.form("new_group_form"):
            name = st.text_input(
                "Nombre de la cuadrilla", placeholder="Ej. Electricistas", key="_group_name",
                max_chars=forms.RULES["Nombre de la cuadrilla"]["max"], help="Obligatorio. Usa un nombre que el equipo reconozca.",
            )
            cancel_col, save_col = st.columns([1, 2])
            submitted = save_col.form_submit_button("Agregar", type="primary", width="stretch")
            cancel = cancel_col.form_submit_button("Cancelar", width="stretch")
        if cancel:
            st.session_state["_group_reset_pending"] = True
            st.rerun()
        if submitted:
            if not forms.errors(forms.validate({"Nombre de la cuadrilla": name.strip()})):
                try:
                    repo.create_work_group(name.strip())
                except Exception:
                    st.error("No se pudo crear la cuadrilla. Tus datos se conservan; inténtalo de nuevo.")
                else:
                    st.session_state["_group_reset_pending"] = True
                    ui.flash(f"Cuadrilla «{name.strip()}» creada.")
                    st.rerun()

        forms.section("Cuadrillas registradas")
        ui.result_count(len(groups), len(groups), noun="cuadrillas")
        if groups.empty:
            ui.empty_state("Sin cuadrillas", "Crea una cuadrilla arriba para asignarle trabajadores.", icon="👷")
        for row in groups.to_dict("records"):
            c1, c2 = st.columns([4, 1])
            c1.write(row["name"])
            if c2.button("🗑", key=f"del_group_{row['id']}", help="Eliminar cuadrilla"):
                ui.confirm_delete(
                    f"¿Eliminar la cuadrilla «{row['name']}»? Los trabajadores quedarán sin cuadrilla.",
                    lambda gid=row["id"], nm=row["name"]: _delete_group(gid, nm),
                )


def _render_sites_panel() -> None:
    if st.session_state.pop("_site_reset_pending", False):
        _reset_site_form()
    sites = repo.list_project_sites()
    with st.expander(f"Obras / Proyectos ({len(sites)})"):
        forms.header("Nueva obra", "Registra la obra y, si la conoces, su ubicación para verla en el mapa.")
        with st.form("new_site_form"):
            forms.section("Identificación", "Solo el nombre es obligatorio. La dirección y el punto del mapa son opcionales.")
            name = st.text_input(
                "Nombre de la obra", placeholder="Ej. Torre Central", key="_site_name",
                max_chars=forms.RULES["Nombre de la obra"]["max"], help="Nombre que se mostrará en trabajadores, presupuestos y órdenes.",
            )
            address = st.text_input(
                "Dirección", placeholder="Calle y número, distrito, ciudad", key="_site_address",
                max_chars=forms.RULES["Dirección"]["max"], help="Opcional. Incluye distrito y ciudad para mejorar la búsqueda.",
            )
            forms.section("Ubicación", "Pega un punto exacto o busca una dirección para revisar el mapa antes de guardar.")
            pin = st.text_input(
                "Enlace de Google Maps o coordenadas (opcional, ubicación exacta)",
                placeholder="Pega aquí el enlace de Google Maps o «-12.0098, -76.9836»",
                key="_site_pin", max_chars=2048,
                help="El buscador gratuito solo conoce la calle, no el número de puerta. "
                "Para el punto exacto: busca la dirección en Google Maps, copia el enlace de la barra "
                "de direcciones (o «Compartir → Copiar enlace») y pégalo aquí.",
            )
            cancel_col, save_col = st.columns([1, 2])
            save = save_col.form_submit_button("Guardar obra", type="primary", width="stretch")
            cancel = cancel_col.form_submit_button("Cancelar", width="stretch")
            search = st.form_submit_button("🔍 Ubicar en el mapa", width="stretch", help="Busca y muestra la ubicación sin guardar la obra.")

        if cancel:
            st.session_state["_site_reset_pending"] = True
            st.rerun()
        location_input = (address.strip(), pin.strip())
        if (search or save) and st.session_state.get("_site_geocode_input") != location_input:
            _clear_site_location()

        if search:
            _clear_site_location()
            if not forms.errors(forms.validate({"Dirección": address.strip()})):
                with st.spinner("Buscando ubicación…"):
                    exact = parse_coordinates(pin)
                    found = search_address(address) if not pin.strip() and address.strip() else []
                if exact:
                    st.session_state["_site_geocode"] = {**exact, "exact": True}
                    st.session_state["_site_geocode_input"] = location_input
                elif pin.strip():
                    st.warning("No reconocí ese enlace o coordenadas. Pega el enlace completo de Google Maps o «lat, lon».")
                elif found:
                    st.session_state["_site_candidates"] = found
                    st.session_state["_site_geocode"] = {**found[0], "exact": False}
                    st.session_state["_site_geocode_input"] = location_input
                elif not address.strip():
                    st.warning("Escribe una dirección o pega un enlace de Google Maps para ubicar la obra.")
                else:
                    st.warning("No se encontró esa dirección. Prueba con distrito y ciudad, o pega el enlace de Google Maps.")

        candidates = st.session_state.get("_site_candidates")
        if candidates and len(candidates) > 1:
            current = st.session_state.get("_site_geocode") or {}
            index = next((i for i, c in enumerate(candidates) if c["lat"] == current.get("lat") and c["lon"] == current.get("lon")), 0)
            chosen = st.selectbox(
                "Resultados encontrados (elige el correcto)", list(range(len(candidates))), index=index, key="_site_candidate_pick",
                format_func=lambda i: f"{candidates[i]['display_name']} ({candidates[i]['lat']:.5f}, {candidates[i]['lon']:.5f})",
            )
            st.session_state["_site_geocode"] = {**candidates[chosen], "exact": False}

        geocode = st.session_state.get("_site_geocode")
        if geocode:
            forms.section("Vista previa de la ubicación", "Este punto se asociará a la obra al guardar.")
            st.caption(f"📍 {geocode['display_name']}")
            if not geocode.get("exact"):
                st.caption(
                    "⚠️ Ubicación aproximada (OpenStreetMap suele ubicar solo la calle). "
                    "Para el punto exacto pega el enlace de Google Maps arriba."
                )
            st.map(pd.DataFrame([{"lat": geocode["lat"], "lon": geocode["lon"]}]), zoom=17 if geocode.get("exact") else 15)
            st.markdown(
                f'<a class="mrp-link" href="{google_maps_search_url(coords=(geocode["lat"], geocode["lon"]))}" '
                'target="_blank" rel="noopener">🗺️ Abrir estas coordenadas en Google Maps</a>',
                unsafe_allow_html=True,
            )
            st.button("Quitar ubicación", key="_site_clear_location", on_click=_remove_site_location, help="Conserva el nombre y la dirección de la obra.")
        elif address.strip():
            st.markdown(
                f'<a class="mrp-link" href="{google_maps_search_url(address.strip())}" target="_blank" rel="noopener">'
                "🗺️ Buscar esta dirección en Google Maps</a>",
                unsafe_allow_html=True,
            )

        if save:
            errors = forms.validate({"Nombre de la obra": name.strip(), "Dirección": address.strip()})
            geocode = st.session_state.get("_site_geocode")
            if pin.strip() and not geocode and not errors:
                with st.spinner("Comprobando ubicación exacta…"):
                    exact = parse_coordinates(pin)
                if exact:
                    geocode = {**exact, "exact": True}
                else:
                    errors.append("Enlace de Google Maps o coordenadas (opcional, ubicación exacta): pega un enlace válido o coordenadas «lat, lon», o deja el campo vacío.")
            if geocode and not _has_coordinates(geocode.get("lat"), geocode.get("lon")):
                errors.append("Ubicación: revisa la latitud y longitud antes de guardar.")
            if not forms.errors(errors):
                lat = geocode["lat"] if geocode else None
                lon = geocode["lon"] if geocode else None
                try:
                    repo.create_project_site(name.strip(), address.strip() or None, lat, lon)
                except Exception:
                    st.error("No se pudo guardar la obra. Tus datos se conservan; inténtalo de nuevo.")
                else:
                    st.session_state["_site_reset_pending"] = True
                    ui.flash(f"Obra «{name.strip()}» guardada.")
                    st.rerun()

        forms.section("Obras registradas")
        ui.result_count(len(sites), len(sites), noun="obras")
        if sites.empty:
            ui.empty_state("Sin obras", "Registra una obra arriba para asignar personal y consultar su ubicación.", icon="🏗️")
        for row in sites.to_dict("records"):
            c1, c2 = st.columns([4, 1])
            if _has_coordinates(row.get("latitude"), row.get("longitude")):
                url = google_maps_search_url(coords=(float(row["latitude"]), float(row["longitude"])))
                c1.markdown(f'{html.escape(row["name"])} <a class="mrp-link" href="{url}" target="_blank" rel="noopener">📍 Ver en Google Maps</a>', unsafe_allow_html=True)
            else:
                c1.write(row["name"])
            if c2.button("🗑", key=f"del_site_{row['id']}", help="Eliminar obra"):
                ui.confirm_delete(
                    f"¿Eliminar la obra «{row['name']}»? Los trabajadores y órdenes asignados quedarán sin obra.",
                    lambda sid=row["id"], nm=row["name"]: _delete_site(sid, nm),
                )


def _clear_site_location() -> None:
    for key in ("_site_geocode", "_site_candidates", "_site_geocode_input", "_site_candidate_pick"):
        st.session_state.pop(key, None)


def _reset_site_form() -> None:
    _clear_site_location()
    for key in ("_site_name", "_site_address", "_site_pin"):
        st.session_state.pop(key, None)


def _remove_site_location() -> None:
    _clear_site_location()
    st.session_state.pop("_site_pin", None)


def _has_coordinates(latitude: object, longitude: object) -> bool:
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return False
    return math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180


def _delete_group(group_id: str, name: str) -> None:
    repo.delete_work_group(group_id)
    ui.flash(f"Cuadrilla «{name}» eliminada.", "🗑️")


def _delete_site(site_id: str, name: str) -> None:
    repo.delete_project_site(site_id)
    ui.flash(f"Obra «{name}» eliminada.", "🗑️")


def _delete_worker(worker_id: str, name: str) -> None:
    repo.delete_worker(worker_id)
    ui.flash(f"Trabajador «{name}» eliminado.", "🗑️")


def _revoke_access(worker_id: str, user_id: str, name: str) -> None:
    repo.revoke_worker_access(worker_id, user_id)
    ui.flash(f"Se quitó el acceso al sistema de {name}.", "🔒")


# ---------------------------------------------------------------------------
# Alta y edición de trabajador
# ---------------------------------------------------------------------------

def _worker_fields(worker: dict | None, groups: pd.DataFrame, sites: pd.DataFrame) -> dict:
    """Campos comunes del formulario de alta y de edición."""
    forms.section("Datos personales", "El nombre completo es obligatorio. Documento, teléfono y puesto son opcionales.")
    full_name = st.text_input(
        "Nombre completo", value=worker["full_name"] if worker else "", placeholder="Ej. Juan Pérez",
        max_chars=forms.RULES["Nombre completo"]["max"], help="Nombre y apellidos que se mostrarán en el directorio y en Asistencia.",
    )
    c1, c2 = st.columns(2)
    document_id = c1.text_input(
        "Documento (opcional)", value=(worker.get("document_id") or "") if worker else "",
        placeholder="Ej. 45879632", max_chars=forms.RULES["Documento (opcional)"]["max"],
        help="DNI, carné de extranjería u otro documento. Se conserva como texto.",
    )
    phone = c2.text_input(
        "Teléfono",
        value=(worker.get("phone") or "") if worker else "",
        placeholder="Ej. +51 987 654 321", max_chars=forms.RULES["Teléfono"]["max"],
        help="Opcional. Incluye el código de país para abrir WhatsApp.",
    )
    position = st.text_input(
        "Puesto (opcional)", value=(worker.get("position") or "") if worker else "", placeholder="Ej. Albañil, Operador de grúa",
        max_chars=forms.RULES["Puesto (opcional)"]["max"], help="Especialidad o función que realiza en la obra.",
    )

    forms.section("Asignación", "Puedes dejar la cuadrilla y la obra sin asignar y completarlas más adelante.")
    # Seleccionar por id evita confundir cuadrillas u obras con el mismo nombre.
    group_names = groups.set_index("id")["name"].to_dict() if not groups.empty else {}
    site_names = sites.set_index("id")["name"].to_dict() if not sites.empty else {}
    group_options = [None] + list(group_names)
    site_options = [None] + list(site_names)
    current_group = worker.get("work_group_id") if worker else None
    current_site = worker.get("project_site_id") if worker else None
    c3, c4 = st.columns(2)
    group_id = c3.selectbox(
        "Cuadrilla", group_options, index=group_options.index(current_group) if current_group in group_options else 0,
        format_func=lambda gid: group_names.get(gid, NO_GROUP), help="Opcional. Las cuadrillas se administran desde el panel del directorio.",
    )
    site_id = c4.selectbox(
        "Obra / Proyecto", site_options, index=site_options.index(current_site) if current_site in site_options else 0,
        format_func=lambda sid: site_names.get(sid, NO_SITE), help="Opcional. La ubicación de la obra aparecerá en la ficha del trabajador.",
    )
    if groups.empty or sites.empty:
        st.caption("Crea cuadrillas y obras en sus paneles del directorio cuando necesites asignarlas.")
    return {
        "full_name": full_name.strip(),
        "document_id": document_id.strip() or None,
        "phone": phone.strip() or None,
        "position": position.strip() or None,
        "group_id": group_id,
        "site_id": site_id,
    }


@st.dialog("Registrar trabajador")
def _new_worker_dialog() -> None:
    groups = repo.list_work_groups()
    sites = repo.list_project_sites()
    forms.header("Nuevo trabajador", "Registra al personal, asigna su equipo y obra y, si lo necesita, crea su acceso al sistema.")
    with st.form("new_worker_form"):
        fields = _worker_fields(None, groups, sites)
        forms.section("Acceso al sistema", "Opcional. Marca la casilla y completa las credenciales solo si debe ingresar a la aplicación.")
        grant_access = st.checkbox("Dar acceso al sistema (usuario y contraseña)")
        with st.expander("Configurar usuario y contraseña", expanded=grant_access):
            username, password, role = _access_fields()
        cancel_col, save_col = st.columns([1, 2])
        save = save_col.form_submit_button("Guardar", type="primary", width="stretch")
        cancel = cancel_col.form_submit_button("Cancelar", width="stretch")
        preview = st.form_submit_button("Revisar datos", width="stretch", help="Revisa el trabajador sin guardar ni crear una cuenta.")
    if cancel:
        st.rerun()
    if preview:
        _worker_preview(fields, groups, sites)
        st.caption(f"Acceso solicitado: @{username or 'usuario pendiente'} · {role}" if grant_access else "Sin acceso al sistema")
    if save:
        errors = _worker_errors(fields)
        if grant_access:
            errors += _access_errors(username, password, role)
        if forms.errors(errors):
            return
        try:
            password_hash = hash_password(password) if grant_access else None
            worker_id = repo.create_worker(
                fields["full_name"], fields["document_id"], fields["phone"], fields["position"], fields["group_id"], fields["site_id"]
            )
        except Exception:
            st.error("No se pudo registrar al trabajador. Tus datos se conservan; inténtalo de nuevo.")
            return
        if grant_access:
            try:
                repo.grant_worker_access(worker_id, username, password_hash, fields["full_name"], role)
            except Exception:
                ui.flash(f"Trabajador «{fields['full_name']}» registrado. No se pudo crear su acceso; usa «Dar acceso» en el directorio para reintentar.", "⚠️")
                st.rerun()

        ui.flash(f"Trabajador «{fields['full_name']}» registrado.")
        st.rerun()


@st.dialog("Editar trabajador")
def _edit_worker_dialog(worker: dict) -> None:
    groups = repo.list_work_groups()
    sites = repo.list_project_sites()
    forms.header("Editar trabajador", "Actualiza sus datos personales, cuadrilla y obra asignada.")
    with st.form(f"edit_worker_form_{worker['id']}"):
        fields = _worker_fields(worker, groups, sites)
        if worker.get("username"):
            st.caption(f"Acceso actual: @{worker['username']} · {worker.get('role') or 'operador'}")
        cancel_col, save_col = st.columns([1, 2])
        save = save_col.form_submit_button("Guardar cambios", type="primary", width="stretch")
        cancel = cancel_col.form_submit_button("Cancelar", width="stretch")
        preview = st.form_submit_button("Revisar datos", width="stretch", help="Muestra el resumen y la ubicación sin guardar.")
    if cancel:
        st.rerun()
    if preview:
        _worker_preview(fields, groups, sites)
    if save:
        if forms.errors(_worker_errors(fields)):
            return
        try:
            repo.update_worker(
                worker["id"], fields["full_name"], fields["document_id"], fields["phone"], fields["position"], fields["group_id"], fields["site_id"]
            )
        except Exception:
            st.error("No se pudo actualizar al trabajador. Tus datos se conservan; inténtalo de nuevo.")
            return
        ui.flash(f"Trabajador «{fields['full_name']}» actualizado.")
        st.rerun()


@st.dialog("Dar acceso al sistema")
def _grant_access_dialog(worker: dict) -> None:
    forms.header("Dar acceso al sistema", f"Crea una cuenta para {worker['full_name']}.")
    with st.form(f"grant_access_form_{worker['id']}"):
        forms.section("Credenciales", "Usuario y contraseña son obligatorios para crear la cuenta.")
        username, password, role = _access_fields()
        cancel_col, save_col = st.columns([1, 2])
        save = save_col.form_submit_button("Dar acceso", type="primary", width="stretch")
        cancel = cancel_col.form_submit_button("Cancelar", width="stretch")
        preview = st.form_submit_button("Revisar acceso", width="stretch", help="Muestra el usuario y el rol; la contraseña permanece oculta.")
    if cancel:
        st.rerun()
    if preview:
        forms.section("Vista previa", "La cuenta todavía no se ha creado.")
        st.write(worker["full_name"])
        st.caption(f"Usuario: @{username or 'pendiente'} · Rol: {role}")
    if save:
        if forms.errors(_access_errors(username, password, role)):
            return
        try:
            repo.grant_worker_access(worker["id"], username, hash_password(password), worker["full_name"], role)
        except Exception:
            st.error("No se pudo crear el acceso. Revisa que el usuario siga disponible e inténtalo de nuevo.")
            return
        ui.flash(f"Acceso creado para {worker['full_name']}.", "🔑")
        st.rerun()


def _worker_errors(fields: dict) -> list[str]:
    return forms.validate({
        "Nombre completo": fields["full_name"],
        "Documento (opcional)": fields["document_id"],
        "Teléfono": fields["phone"],
        "Puesto (opcional)": fields["position"],
    })


def _access_fields() -> tuple[str, str, str]:
    c1, c2 = st.columns(2)
    username = c1.text_input(
        "Usuario", placeholder="Ej. jperez", max_chars=forms.RULES["Usuario"]["max"],
        help=f"De {forms.RULES['Usuario']['min']} a {forms.RULES['Usuario']['max']} caracteres: letras sin tilde, números, punto, guion o guion bajo.",
    )
    password = c2.text_input(
        "Contraseña", type="password", placeholder="Al menos 6 caracteres", max_chars=72,
        help="Al menos 6 caracteres. Combina letras, números y símbolos y evita contraseñas previsibles.",
    )
    role = st.selectbox("Rol de acceso", ROLES, help="Operador: tareas operativas. Admin: también administra el personal y sus accesos.")
    return username.strip(), password, role


def _access_errors(username: str, password: str, role: str) -> list[str]:
    errors = forms.validate({"Usuario": username})
    if not password or not password.strip():
        errors.append("Contraseña: completa este campo obligatorio.")
    elif len(password) < 6:
        errors.append("Contraseña: utiliza al menos 6 caracteres.")
    elif len(password.encode("utf-8")) > 72:
        errors.append("Contraseña: es demasiado larga; utiliza menos caracteres.")
    if role not in ROLES:
        errors.append("Rol de acceso: selecciona operador o admin.")
    if not errors:
        try:
            existing = repo.get_user_by_username(username)
        except Exception:
            errors.append("Usuario: no se pudo comprobar su disponibilidad. Inténtalo de nuevo.")
        else:
            if existing:
                errors.append(f"Usuario: ya existe una cuenta con el nombre «{username}».")
    return errors


def _worker_preview(fields: dict, groups: pd.DataFrame, sites: pd.DataFrame) -> None:
    forms.section("Vista previa", "Estos datos todavía no se han guardado.")
    group_names = groups.set_index("id")["name"].to_dict() if not groups.empty else {}
    with st.container(border=True):
        st.write(fields["full_name"] or "Nombre pendiente")
        st.caption(" · ".join(value for value in [fields["position"], fields["document_id"]] if value) or "Sin puesto ni documento")
        st.write(f"Teléfono: {fields['phone'] or 'sin registrar'}")
        st.write(f"Cuadrilla: {group_names.get(fields['group_id'], NO_GROUP)}")
        site_match = sites[sites["id"] == fields["site_id"]] if not sites.empty else sites
        if site_match.empty:
            st.write(NO_SITE)
        else:
            site = site_match.to_dict("records")[0]
            st.write(f"Obra: {site['name']}")
            if site.get("address"):
                st.caption(site["address"])
            if _has_coordinates(site.get("latitude"), site.get("longitude")):
                st.map(pd.DataFrame([{"lat": float(site["latitude"]), "lon": float(site["longitude"])}]), zoom=13)


# ---------------------------------------------------------------------------
# Directorio
# ---------------------------------------------------------------------------

ALL_GROUPS = "Todas las cuadrillas"
ALL_SITES = "Todas las obras"


def _render_workers_list() -> None:
    st.markdown('<div class="mrp-eyebrow">Directorio</div>', unsafe_allow_html=True)
    st.markdown('<div class="mrp-panel-title">Trabajadores registrados</div>', unsafe_allow_html=True)

    df = repo.list_workers()
    if df.empty:
        ui.empty_state("Registra tu primer trabajador", "Usa «＋ Nuevo trabajador». Puedes crear cuadrillas y obras desde los paneles de arriba.", icon="👷")
        return

    total = len(df)
    ui.stat_grid([
        ui.stat_card("👷", total, "Trabajadores"),
        ui.stat_card("🏗️", int(df["site_name"].notna().sum()), "Con obra asignada"),
        ui.stat_card("🔑", int(df["user_id"].notna().sum()), "Con acceso al sistema"),
    ])
    f1, f2, f3 = st.columns([3, 2, 2])
    query = f1.text_input(
        "Buscar", placeholder="Buscar por nombre, documento, teléfono o puesto…", key="wk_q", max_chars=120,
    )
    groups = sorted(df["group_name"].dropna().unique().tolist())
    sites = sorted(df["site_name"].dropna().unique().tolist())
    group_options = list(dict.fromkeys([ALL_GROUPS, NO_GROUP] + groups))
    site_options = list(dict.fromkeys([ALL_SITES, NO_SITE] + sites))
    if st.session_state.get("wk_group", ALL_GROUPS) not in group_options:
        st.session_state["wk_group"] = ALL_GROUPS
    if st.session_state.get("wk_site", ALL_SITES) not in site_options:
        st.session_state["wk_site"] = ALL_SITES
    group_filter = f2.selectbox("Cuadrilla", group_options, key="wk_group")
    site_filter = f3.selectbox("Obra", site_options, key="wk_site")
    if query.strip() or group_filter != ALL_GROUPS or site_filter != ALL_SITES:
        st.button("Limpiar filtros", key="wk_reset", on_click=_reset_worker_filters)

    if group_filter == NO_GROUP:
        df = df[df["group_name"].isna()]
    elif group_filter != ALL_GROUPS:
        df = df[df["group_name"] == group_filter]
    if site_filter == NO_SITE:
        df = df[df["site_name"].isna()]
    elif site_filter != ALL_SITES:
        df = df[df["site_name"] == site_filter]
    df = ui.filter_df(df, query, ["full_name", "document_id", "phone", "position"])

    ui.result_count(len(df), total, noun="trabajadores")
    if df.empty:
        ui.empty_state("Sin coincidencias", "Prueba otra búsqueda o limpia los filtros para ver todo el personal.", icon="🔎")
        return
    df = ui.paginate(df, key="workers_directory")

    for row in df.to_dict("records"):
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([4, 2.6, 2.6, 1, 1])
            with c1:
                sub = " · ".join(x for x in [row.get("position"), row.get("document_id")] if x) or row.get("phone") or "Sin datos"
                st.markdown(ui.row_name_sub(ui.avatar(row["full_name"]), row["full_name"], sub), unsafe_allow_html=True)
            with c2:
                pills = ui.pill(row.get("group_name") or "Sin cuadrilla", "purple")
                pills += " " + ui.pill(row.get("site_name") or "Sin obra", "gray")
                st.markdown(pills, unsafe_allow_html=True)
            with c3:
                if row.get("user_id"):
                    if st.button("Quitar acceso", key=f"revoke_{row['id']}", width="stretch"):
                        ui.confirm_delete(
                            f"¿Quitar el acceso al sistema de {row['full_name']}? Su cuenta de usuario se elimina; el trabajador se conserva.",
                            lambda wid=row["id"], uid=row["user_id"], nm=row["full_name"]: _revoke_access(wid, uid, nm),
                        )
                else:
                    if st.button("Dar acceso", key=f"grant_{row['id']}", width="stretch"):
                        _grant_access_dialog(row)
            with c4:
                if st.button("✏️", key=f"edit_worker_{row['id']}", help="Editar trabajador"):
                    _edit_worker_dialog(row)
            with c5:
                if st.button("🗑", key=f"del_worker_{row['id']}", help="Eliminar trabajador"):
                    ui.confirm_delete(
                        f"¿Eliminar al trabajador «{row['full_name']}»?",
                        lambda wid=row["id"], nm=row["full_name"]: _delete_worker(wid, nm),
                    )

            if row.get("phone"):
                st.markdown(ui.contact_links(row["phone"], None), unsafe_allow_html=True)
            if row.get("username"):
                st.caption(f"Acceso al sistema: @{row['username']} ({row.get('role') or 'operador'})")

            if _has_coordinates(row.get("latitude"), row.get("longitude")):
                with st.expander(f"📍 Ubicación — {row.get('site_name') or ''}"):
                    if row.get("site_address"):
                        st.caption(row["site_address"])
                    st.map(pd.DataFrame([{"lat": row["latitude"], "lon": row["longitude"]}]), zoom=13)


def _reset_worker_filters() -> None:
    st.session_state["wk_q"] = ""
    st.session_state["wk_group"] = ALL_GROUPS
    st.session_state["wk_site"] = ALL_SITES
    st.session_state["workers_directory_page"] = 1
