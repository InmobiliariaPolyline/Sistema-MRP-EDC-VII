"""Editar una obra ya creada: nombre, dirección y ubicación en el mapa.

Se abre desde Obras (ficha de la obra) y desde Trabajadores (lista de obras). Al guardar solo cambia lo que se tocó y el cambio
queda en el Historial. Las órdenes, presupuestos y trabajadores de la obra no se ven afectados: siguen unidos a ella."""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from db import repository as repo
from modules import forms, ui
from utils import icons
from utils.geocode import google_maps_search_url, parse_coordinates, search_address

_KEYS = ("name", "address", "pin", "loc", "found", "pick", "removed")


def _key(site_id: str, name: str) -> str:
    return f"site_edit_{site_id}_{name}"


def clear(site_id: str) -> None:
    for name in _KEYS:
        st.session_state.pop(_key(site_id, name), None)


def has_coordinates(latitude: object, longitude: object) -> bool:
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return False
    return math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180


def name_taken(name: str, site_id: str, sites: pd.DataFrame) -> bool:
    """¿Otra obra ya se llama así? (sin distinguir mayúsculas ni espacios de más)."""
    wanted = " ".join(name.split()).casefold()
    return any(" ".join(str(r["name"]).split()).casefold() == wanted for r in sites.to_dict("records") if r["id"] != site_id)


def changes_for(site: dict, name: str, address: str | None, lat: float | None, lon: float | None) -> list[dict]:
    """Lo que cambió respecto de lo guardado, en el formato del Historial."""
    out = []
    if name != site["name"]:
        out.append({"field": "Nombre", "before": site["name"], "after": name})
    if (address or None) != (site.get("address") or None):
        out.append({"field": "Dirección", "before": site.get("address"), "after": address})
    had = has_coordinates(site.get("latitude"), site.get("longitude"))
    before = f"{float(site['latitude']):.5f}, {float(site['longitude']):.5f}" if had else None
    after = f"{lat:.5f}, {lon:.5f}" if lat is not None and lon is not None else None
    if before != after:
        out.append({"field": "Ubicación", "before": before, "after": after})
    return out


@st.dialog("Editar obra", width="large")
def edit_dialog(site: dict) -> None:
    sid = site["id"]
    forms.header(f"Editar «{site['name']}»", "Cambia el nombre, la dirección o el punto del mapa. Lo demás (órdenes, presupuesto, trabajadores) sigue unido a la obra.")
    sites = repo.list_project_sites()
    if _key(sid, "loc") not in st.session_state:
        st.session_state[_key(sid, "loc")] = (
            {"lat": float(site["latitude"]), "lon": float(site["longitude"]), "display_name": "Ubicación guardada", "exact": True}
            if has_coordinates(site.get("latitude"), site.get("longitude")) else None
        )

    forms.section("Identificación", "El nombre se muestra en trabajadores, presupuestos y órdenes.")
    name = st.text_input("Nombre de la obra", value=site["name"], key=_key(sid, "name"), max_chars=forms.RULES["Nombre de la obra"]["max"])
    address = st.text_input("Dirección", value=site.get("address") or "", key=_key(sid, "address"), max_chars=forms.RULES["Dirección"]["max"],
                            placeholder="Calle y número, distrito, ciudad", help="Opcional. Incluye distrito y ciudad para mejorar la búsqueda.")

    forms.section("Ubicación", "Pega un punto exacto o busca la dirección para revisar el mapa antes de guardar.")
    pin = st.text_input("Enlace de Google Maps o coordenadas (opcional, ubicación exacta)", key=_key(sid, "pin"), max_chars=2048,
                        placeholder="Pega aquí el enlace de Google Maps o «-12.0098, -76.9836»")
    if st.button(":material/search: Ubicar en el mapa", key=_key(sid, "search"), width="stretch", help="Busca y muestra la ubicación sin guardar todavía."):
        exact = parse_coordinates(pin) if pin.strip() else None
        if exact:
            st.session_state[_key(sid, "loc")] = {**exact, "exact": True}
            st.session_state.pop(_key(sid, "found"), None)
        elif pin.strip():
            st.warning("No reconocí ese enlace o coordenadas. Pega el enlace completo de Google Maps o «lat, lon».")
        elif not address.strip():
            st.warning("Escribe una dirección o pega un enlace de Google Maps para ubicar la obra.")
        else:
            with st.spinner("Buscando ubicación…"):
                found = search_address(address)
            if found:
                st.session_state[_key(sid, "found")] = found
                st.session_state[_key(sid, "loc")] = {**found[0], "exact": False}
                st.session_state.pop(_key(sid, "pick"), None)
            else:
                st.warning("No se encontró esa dirección. Prueba con distrito y ciudad, o pega el enlace de Google Maps.")

    found = st.session_state.get(_key(sid, "found"))
    if found and len(found) > 1:
        current = st.session_state.get(_key(sid, "loc")) or {}
        index = next((i for i, c in enumerate(found) if c["lat"] == current.get("lat") and c["lon"] == current.get("lon")), 0)
        chosen = st.selectbox("Resultados encontrados (elige el correcto)", list(range(len(found))), index=index, key=_key(sid, "pick"),
                              format_func=lambda i: f"{found[i]['display_name']} ({found[i]['lat']:.5f}, {found[i]['lon']:.5f})")
        st.session_state[_key(sid, "loc")] = {**found[chosen], "exact": False}

    loc = st.session_state.get(_key(sid, "loc"))
    if loc:
        st.caption(f":material/location_on: {loc['display_name']}" + ("" if loc.get("exact") else " · aproximada (OpenStreetMap suele ubicar solo la calle)"))
        st.map(pd.DataFrame([{"lat": loc["lat"], "lon": loc["lon"]}]), zoom=17 if loc.get("exact") else 15)
        st.markdown(icons.render_tokens(f'<a class="mrp-link" href="{google_maps_search_url(coords=(loc["lat"], loc["lon"]))}" target="_blank" rel="noopener">:material/map: Abrir en Google Maps</a>'),
                    unsafe_allow_html=True)
        if st.button(":material/location_off: Quitar ubicación", key=_key(sid, "remove"), help="Deja la obra sin punto en el mapa; conserva el nombre y la dirección."):
            st.session_state[_key(sid, "loc")] = None
            st.session_state.pop(_key(sid, "found"), None)
            st.rerun(scope="fragment")
    else:
        st.caption("Esta obra no tiene ubicación en el mapa.")
    if address.strip() != (site.get("address") or "") and loc and loc.get("display_name") == "Ubicación guardada":
        st.caption(":material/info: Cambiaste la dirección pero el punto del mapa sigue siendo el anterior. Pulsa «Ubicar en el mapa» si quieres actualizarlo.")

    cancel, save = st.columns([1, 2])
    if cancel.button(":material/close: Cancelar", key=_key(sid, "cancel"), width="stretch"):
        clear(sid)
        st.rerun()
    if save.button(":material/save: Guardar cambios", key=_key(sid, "save"), type="primary", width="stretch"):
        issues = forms.validate({"Nombre de la obra": name.strip(), "Dirección": address.strip()})
        if name.strip() and name_taken(name, sid, sites):
            issues.append("Nombre de la obra: ya existe otra obra con ese nombre.")
        if loc and not has_coordinates(loc.get("lat"), loc.get("lon")):
            issues.append("Ubicación: revisa la latitud y longitud antes de guardar.")
        if forms.errors(issues):
            return
        lat = float(loc["lat"]) if loc else None
        lon = float(loc["lon"]) if loc else None
        changes = changes_for(site, " ".join(name.split()), address.strip() or None, lat, lon)
        if not changes:
            st.info("No hay cambios que guardar.")
            return
        try:
            repo.update_project_site(sid, " ".join(name.split()), address.strip() or None, lat, lon)
        except Exception as exc:
            ui.db_error(exc, "No se pudo guardar la obra. Tus datos se conservan; inténtalo de nuevo.")
            return
        ui.log_change(f"Obra «{' '.join(name.split())}» editada", "obra", sid, changes, icon=":material/edit:")
        clear(sid)
        st.rerun()
