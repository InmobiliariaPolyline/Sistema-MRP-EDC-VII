"""Pantalla de acceso: una animación de carga breve, seguida de un login
partido en dos paneles (marca a la izquierda, formulario a la derecha), o
la creación del primer administrador cuando la tabla de usuarios está
vacía (arranque en limpio del sistema)."""
import time

import streamlit as st

from db import repository as repo
from db.auth import hash_password, verify_password
from db.repository import USING_LOCAL
from modules import forms, security, session, ui, ui_styles
from utils import access, icons

SESSION_KEY = "auth_user"
BOOTED_KEY = "_mrp_booted"

_PAGE_RESET = """
#MainMenu, header, footer, div[data-testid="stHeader"] { visibility: hidden; height: 0 !important; min-height: 0 !important; }
section[data-testid="stSidebar"] { display: none; }
div[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
div[data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: 100% !important; }
div[data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"] > * { animation: none !important; }
div[data-testid="stVerticalBlock"] { gap: 0 !important; }
div[data-testid="stElementContainer"] { margin: 0 !important; }
"""

_SHELL_BODY = _PAGE_RESET + """
@property --n { syntax: '<integer>'; initial-value: 0; inherits: false; }
@keyframes lpCount { from { --n: 0; } to { --n: var(--to); } }
@keyframes lpOrbit { to { transform: rotate(360deg); } }
@keyframes lpDrift { 0%, 100% { transform: translate(0, 0) scale(1); } 50% { transform: translate(30px, -40px) scale(1.12); } }
@keyframes lpSheen { from { background-position: 0% 50%; } to { background-position: 200% 50%; } }

div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) { min-height: 100dvh; align-items: stretch; gap: 0 !important; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"] { padding: 0 !important; }

/* panel de marca: malla de color en movimiento, rejilla y órbitas */
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(1) {
  position: relative; overflow: hidden; isolation: isolate; color: #EDEBFB; padding: 3.2rem 3rem !important; display: flex; flex-direction: column; justify-content: space-between;
  background:
    radial-gradient(34rem 26rem at 92% 6%, rgba(255,255,255,.22), transparent 62%),
    radial-gradient(34rem 28rem at 0% 100%, rgba(34,211,238,.32), transparent 60%),
    linear-gradient(150deg, #170C4A, #3A24B8, #5B42F2, #2A1B8F);
  background-size: auto, auto, 240% 240%; animation: mrpGradient 18s ease-in-out infinite;
}
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(1)::before {
  content: ""; position: absolute; inset: 0; z-index: -1; opacity: .55;
  background: linear-gradient(rgba(255,255,255,.07) 1px, transparent 1px) 0 0 / 2.2rem 2.2rem, linear-gradient(90deg, rgba(255,255,255,.07) 1px, transparent 1px) 0 0 / 2.2rem 2.2rem;
  mask-image: radial-gradient(circle at 70% 30%, #000, transparent 72%);
}
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(2) {
  position: relative; background: var(--mrp-bg); display: flex; align-items: center; justify-content: center; padding: 3rem !important;
  background: radial-gradient(40rem 24rem at 100% 0%, var(--mrp-glow-a), transparent 60%), radial-gradient(30rem 24rem at 0% 100%, var(--mrp-glow-b), transparent 60%), var(--mrp-bg);
}
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(2) > div { width: 100%; max-width: 27rem; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(2) div[data-testid="stVerticalBlock"] { gap: 1rem !important; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(1) [data-testid="stVerticalBlock"],
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(1) [data-testid="stElementContainer"] { height: 100%; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) [data-testid="stMarkdownContainer"]:has(.mrp-lp-brand) { display: flex; flex-direction: column; justify-content: space-between; gap: 2.4rem; min-height: calc(100dvh - 6.4rem); }
.mrp-lp-orb { position: absolute; z-index: -1; border-radius: 50%; filter: blur(2px); pointer-events: none; }
.mrp-lp-orb.a { width: 15rem; height: 15rem; right: -4rem; top: 18%; background: radial-gradient(circle at 30% 30%, rgba(255,255,255,.28), rgba(255,255,255,0) 70%); animation: lpDrift 12s ease-in-out infinite; }
.mrp-lp-orb.b { width: 11rem; height: 11rem; left: -3rem; bottom: 26%; background: radial-gradient(circle at 30% 30%, rgba(34,211,238,.4), rgba(34,211,238,0) 70%); animation: lpDrift 15s ease-in-out -4s infinite; }
.mrp-lp-orb.c { width: 22rem; height: 22rem; right: -9rem; bottom: -9rem; border: 2.6rem solid rgba(255,255,255,.06); animation: lpOrbit 40s linear infinite; }

.mrp-lp-brand { display: flex; align-items: center; gap: .85rem; animation: mrpSlideLeft .7s var(--ease-out) both; }
.mrp-lp-brand-badge { position: relative; width: 3rem; height: 3rem; border-radius: .95rem; color: #fff; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.28); backdrop-filter: blur(8px); display: grid; place-items: center; box-shadow: 0 10px 30px -10px rgba(10,6,50,.8); }
.mrp-lp-brand-badge::after { content: ""; position: absolute; inset: -5px; border-radius: 1.2rem; border: 1px solid rgba(255,255,255,.3); animation: mrpBreathe 3.4s ease-in-out infinite; }
.mrp-lp-brand-name { font-weight: 800; letter-spacing: .12em; font-size: .85rem; }
.mrp-lp-hero { animation: mrpUp .9s var(--ease-out) .1s both; }
.mrp-lp-eyebrow { font-size: .74rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: #C9C2F7; margin-bottom: .7rem; }
.mrp-lp-headline { font-size: clamp(2rem, 3.1vw, 2.9rem); letter-spacing: -.035em; font-weight: 800; line-height: 1.12; color: #fff; margin-bottom: 1rem; }
.mrp-lp-headline em { font-style: normal; background: linear-gradient(100deg, #fff 20%, #9BF0FF 45%, #C9B8FF 70%, #fff 90%); background-size: 200% 100%; -webkit-background-clip: text; background-clip: text; color: transparent; animation: lpSheen 6s linear infinite; }
.mrp-lp-copy { font-size: .95rem; color: #D6D1F5; line-height: 1.65; max-width: 27rem; }
.mrp-lp-features { display: flex; flex-direction: column; gap: .7rem; margin-top: 1.8rem; max-width: 28rem; }
.mrp-lp-feature {
  display: flex; align-items: center; gap: .85rem; padding: .85rem 1rem; border-radius: 1rem; font-size: .92rem; font-weight: 650; color: #fff;
  background: rgba(255,255,255,.09); border: 1px solid rgba(255,255,255,.15); backdrop-filter: blur(10px);
  animation: mrpSlideLeft .7s var(--ease-out) both; transition: transform var(--dur-base) var(--ease-out), background var(--dur-base), border-color var(--dur-base);
}
.mrp-lp-feature:nth-child(1) { animation-delay: .35s; } .mrp-lp-feature:nth-child(2) { animation-delay: .5s; } .mrp-lp-feature:nth-child(3) { animation-delay: .65s; }
.mrp-lp-feature:hover { transform: translateX(8px); background: rgba(255,255,255,.15); border-color: rgba(255,255,255,.32); }
.mrp-lp-feature-icon { width: 2.3rem; height: 2.3rem; border-radius: .7rem; background: rgba(255,255,255,.16); display: grid; place-items: center; flex-shrink: 0; transition: transform var(--dur-base) var(--ease-spring); }
.mrp-lp-feature:hover .mrp-lp-feature-icon { transform: rotate(-8deg) scale(1.12); }
.mrp-lp-feature small { display: block; font-weight: 500; font-size: .78rem; color: #D6D1F5; margin-top: .1rem; }
.mrp-lp-divider { border-top: 1px solid rgba(255,255,255,.18); margin: 1.8rem 0 1.2rem; }
.mrp-lp-stat { animation: mrpUp .9s var(--ease-out) .8s both; }
.mrp-lp-stat-value { font-size: 2.3rem; font-weight: 800; color: #fff; font-variant-numeric: tabular-nums; }
.mrp-lp-stat-value.count { animation: lpCount 1.8s var(--ease-out) .9s both; counter-reset: n var(--n); }
.mrp-lp-stat-value.count::after { content: counter(n); }
.mrp-lp-stat-label { font-size: .85rem; color: #C9C2F7; }

.mrp-rp-status { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2.4rem; animation: mrpDown .6s var(--ease-out) both; }
.mrp-rp-status-label { font-size: .78rem; color: var(--mrp-muted); font-weight: 600; letter-spacing: .02em; }
.mrp-rp-status-dot { display: inline-flex; align-items: center; gap: .45rem; font-size: .76rem; font-weight: 700; padding: .3rem .75rem; border-radius: var(--r-full); }
.mrp-rp-status-dot::before { content: ""; width: .5rem; height: .5rem; border-radius: 50%; background: currentColor; animation: mrpPulse 2s ease-out infinite; }
.mrp-rp-status-dot.ok { color: var(--mrp-good); background: var(--mrp-good-bg); }
.mrp-rp-status-dot.local { color: var(--mrp-warn); background: var(--mrp-warn-bg); }
.mrp-rp-eyebrow { font-size: .74rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--mrp-accent); margin-bottom: .5rem; animation: mrpUp .6s var(--ease-out) .05s both; }
.mrp-rp-headline { font-size: 1.95rem; font-weight: 800; letter-spacing: -.03em; line-height: 1.15; color: var(--mrp-text); margin-bottom: .6rem; animation: mrpUp .6s var(--ease-out) .1s both; }
.mrp-rp-copy { font-size: .93rem; color: var(--mrp-muted); margin-bottom: 1.4rem; line-height: 1.65; animation: mrpUp .6s var(--ease-out) .15s both; }

/* formulario: tarjeta de cristal con entrada escalonada */
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) [data-testid="stForm"] { background: var(--mrp-glass); backdrop-filter: blur(14px); border: 1px solid var(--mrp-border); border-radius: 1.4rem; padding: 1.6rem; box-shadow: var(--mrp-shadow-lg); animation: mrpUp .7s var(--ease-out) .2s both; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) [data-testid="stForm"] [data-testid="stElementContainer"] { animation: mrpUp .6s var(--ease-out) both; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) [data-testid="stForm"] [data-testid="stElementContainer"]:nth-child(2) { animation-delay: .3s; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) [data-testid="stForm"] [data-testid="stElementContainer"]:nth-child(3) { animation-delay: .4s; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) [data-testid="stForm"] [data-testid="stElementContainer"]:nth-child(4) { animation-delay: .5s; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) [data-testid="stForm"] [data-testid="stElementContainer"]:nth-child(5) { animation-delay: .6s; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) [data-testid="stForm"] button[kind="primaryFormSubmit"] { min-height: 3rem; font-size: 1rem; }
div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) [data-testid="stPopover"] button { animation: mrpFade .8s ease-out .7s both; }

@media (max-width: 900px) {
  div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) { min-height: auto; }
  div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(1) { padding: 2rem 1.4rem !important; gap: 1.4rem; }
  div[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand) > div[data-testid="stColumn"]:nth-of-type(2) { padding: 1.8rem 1.2rem !important; }
  .mrp-lp-headline { font-size: 1.7rem; }
  .mrp-lp-features { display: none; }
  .mrp-rp-status { margin-bottom: 1.4rem; }
}
"""

_BOOT_BODY = _PAGE_RESET + """
@property --p { syntax: '<integer>'; initial-value: 0; inherits: false; }
@keyframes bootBar { from { width: 0; } to { width: 100%; } }
@keyframes bootPct { from { --p: 0; } to { --p: 100; } }
@keyframes bootStep { 0%, 4% { opacity: 0; transform: translateY(8px); } 10%, 22% { opacity: 1; transform: none; } 28%, 100% { opacity: 0; transform: translateY(-8px); } }
@keyframes bootRing { to { transform: rotate(360deg); } }
@keyframes bootLetter { from { opacity: 0; transform: translateY(14px) scale(.9); filter: blur(4px); } to { opacity: 1; transform: none; filter: none; } }
@keyframes bootOut { to { opacity: 0; transform: scale(1.03); } }

div[data-testid="stMainBlockContainer"] { min-height: 100dvh; display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden; isolation: isolate;
  background:
    radial-gradient(40rem 30rem at 82% 0%, rgba(255,255,255,.2), transparent 62%),
    radial-gradient(40rem 32rem at 0% 100%, rgba(34,211,238,.3), transparent 60%),
    linear-gradient(150deg, #140A42, #3A24B8, #5B42F2, #24167F);
  background-size: auto, auto, 260% 260%; animation: mrpGradient 14s ease-in-out infinite;
}
div[data-testid="stMainBlockContainer"]::before { content: ""; position: absolute; inset: 0; z-index: -1; opacity: .6;
  background: linear-gradient(rgba(255,255,255,.06) 1px, transparent 1px) 0 0 / 2.4rem 2.4rem, linear-gradient(90deg, rgba(255,255,255,.06) 1px, transparent 1px) 0 0 / 2.4rem 2.4rem;
  mask-image: radial-gradient(circle at 50% 45%, #000, transparent 68%); }
div[data-testid="stMainBlockContainer"] > div { width: 100%; max-width: 24rem; }
.mrp-boot { position: relative; display: flex; flex-direction: column; align-items: center; text-align: center; padding: 1rem; animation: bootOut .5s var(--ease-in-out) 2.5s forwards; }
.mrp-boot-stage { position: relative; width: 8.5rem; height: 8.5rem; display: grid; place-items: center; margin-bottom: 1.6rem; }
.mrp-boot-ring { position: absolute; inset: 0; border-radius: 50%; border: 1.5px solid rgba(255,255,255,.18); border-top-color: rgba(255,255,255,.85); animation: bootRing 2.4s linear infinite; }
.mrp-boot-ring.two { inset: .9rem; border-color: rgba(155,240,255,.14); border-bottom-color: rgba(155,240,255,.8); animation-duration: 3.4s; animation-direction: reverse; }
.mrp-boot-ring.three { inset: -.9rem; border-color: rgba(255,255,255,.07); border-left-color: rgba(255,255,255,.4); animation-duration: 5s; }
.mrp-boot-badge { position: relative; width: 4.6rem; height: 4.6rem; border-radius: 1.4rem; color: #fff; display: grid; place-items: center; background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.3); backdrop-filter: blur(10px); box-shadow: 0 20px 50px -14px rgba(8,4,40,.9); animation: mrpPop .7s var(--ease-spring) both; }
.mrp-boot-badge .mrp-mark { width: 2.6rem; height: 2.6rem; }
.mrp-boot-title { display: flex; justify-content: center; gap: .02em; color: #fff; font-weight: 800; font-size: 1.35rem; letter-spacing: .16em; margin-bottom: .2rem; }
.mrp-boot-title span { display: inline-block; animation: bootLetter .6s var(--ease-out) both; }
.mrp-boot-sub { color: #C9C2F7; font-size: .85rem; margin-bottom: 2rem; animation: mrpFade .9s ease-out .9s both; }
.mrp-boot-track { width: 100%; height: .42rem; border-radius: 99px; background: rgba(255,255,255,.14); overflow: hidden; position: relative; }
.mrp-boot-bar { position: relative; height: 100%; width: 0; border-radius: 99px; background: linear-gradient(90deg, #9BF0FF, #fff); box-shadow: 0 0 18px rgba(155,240,255,.9); animation: bootBar 2.4s var(--ease-in-out) .1s forwards; }
.mrp-boot-bar::after { content: ""; position: absolute; inset: 0; background: linear-gradient(100deg, transparent 30%, rgba(255,255,255,.7) 50%, transparent 70%); background-size: 200% 100%; animation: mrpShimmer 1.1s linear infinite; }
.mrp-boot-meta { display: flex; justify-content: space-between; align-items: center; width: 100%; margin-top: .8rem; color: #D6D1F5; font-size: .8rem; }
.mrp-boot-steps { position: relative; height: 1.1rem; flex: 1; text-align: left; }
.mrp-boot-steps span { position: absolute; inset: 0; opacity: 0; animation: bootStep 2.6s ease-in-out both; }
.mrp-boot-steps span:nth-child(1) { animation-delay: 0s; } .mrp-boot-steps span:nth-child(2) { animation-delay: .6s; } .mrp-boot-steps span:nth-child(3) { animation-delay: 1.2s; } .mrp-boot-steps span:nth-child(4) { animation-delay: 1.9s; }
.mrp-boot-steps span:nth-child(4) { animation-name: bootStepLast; }
@keyframes bootStepLast { 0% { opacity: 0; transform: translateY(8px); } 12%, 100% { opacity: 1; transform: none; } }
.mrp-boot-pct { font-variant-numeric: tabular-nums; font-weight: 800; color: #fff; animation: bootPct 2.4s var(--ease-in-out) .1s forwards; counter-reset: p var(--p); min-width: 3rem; text-align: right; }
.mrp-boot-pct::after { content: counter(p) "%"; }
"""

_SHELL_CSS = "<style>" + ui_styles._minify(_SHELL_BODY) + "</style>"
_BOOT_CSS = "<style>" + ui_styles._minify(_BOOT_BODY) + "</style>"


def is_logged_in() -> bool:
    return SESSION_KEY in st.session_state


def current_user() -> dict:
    return st.session_state[SESSION_KEY]


def logout() -> None:
    st.session_state.pop(SESSION_KEY, None)
    session.forget()


def render() -> None:
    if not st.session_state.get(BOOTED_KEY):
        _render_boot()
        return

    st.markdown(_SHELL_CSS, unsafe_allow_html=True)
    left, right = st.columns([1, 1])

    with left:
        _render_brand_panel()

    with right:
        ui.show_flash()
        _render_status_line()
        if repo.count_users() == 0:
            _render_bootstrap()
        else:
            _render_login()


def _render_boot() -> None:
    """Pantalla de carga: marca que se dibuja, anillos, barra con porcentaje y mensajes; todo en CSS, así que fluye sin saltos."""
    st.markdown(_BOOT_CSS, unsafe_allow_html=True)
    letters = "".join(f'<span style="animation-delay:{0.25 + i * 0.05:.2f}s">{c}</span>' for i, c in enumerate("SISTEMA MRP"))
    steps = ["Preparando tu espacio de trabajo", "Organizando la interfaz", "Verificando la conexión", "Todo listo"]
    steps_html = "".join(f"<span>{s}…</span>" if i < 3 else f"<span>{s}</span>" for i, s in enumerate(steps))
    st.markdown(
        '<div class="mrp-boot">'
        '<div class="mrp-boot-stage"><div class="mrp-boot-ring"></div><div class="mrp-boot-ring two"></div><div class="mrp-boot-ring three"></div>'
        f'<div class="mrp-boot-badge">{icons.brand_mark(42, animated=True)}</div></div>'
        f'<div class="mrp-boot-title">{letters.replace("> <", ">&nbsp;<")}</div>'
        '<div class="mrp-boot-sub">Materiales, proveedores y obras</div>'
        '<div class="mrp-boot-track"><div class="mrp-boot-bar"></div></div>'
        f'<div class="mrp-boot-meta"><div class="mrp-boot-steps">{steps_html}</div><div class="mrp-boot-pct"></div></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    time.sleep(2.7)
    st.session_state[BOOTED_KEY] = True
    st.rerun()


def _render_brand_panel() -> None:
    try:
        suppliers_count = len(repo.list_suppliers())
    except Exception:
        suppliers_count = None

    stat_html = ""
    if suppliers_count is not None:
        noun = "proveedor" if suppliers_count == 1 else "proveedores"
        stat_html = (
            '<div class="mrp-lp-stat">'
            f'<div class="mrp-lp-stat-value count" style="--to:{suppliers_count}"></div>'
            f'<div class="mrp-lp-stat-label">{noun} registrados</div>'
            "</div>"
        )

    st.markdown(
        '<div class="mrp-lp-orb a"></div><div class="mrp-lp-orb b"></div><div class="mrp-lp-orb c"></div>'
        '<div class="mrp-lp-brand">'
        f'<div class="mrp-lp-brand-badge">{icons.brand_mark(28, animated=True)}</div>'
        '<div class="mrp-lp-brand-name">SISTEMA MRP</div>'
        "</div>"
        '<div class="mrp-lp-hero">'
        '<div class="mrp-lp-eyebrow">Control de materiales</div>'
        '<div class="mrp-lp-headline">Cada material, con<br/><em>un proveedor claro.</em></div>'
        '<div class="mrp-lp-copy">Consulta el catálogo, prepara tus pedidos y mantén '
        "el almacén y las obras al día desde un solo panel.</div>"
        '<div class="mrp-lp-features">'
        f'<div class="mrp-lp-feature"><div class="mrp-lp-feature-icon">{icons.svg("layers", 18, 2)}</div><div>Catálogo de materiales<small>Densidad, métrica y mejor precio</small></div></div>'
        f'<div class="mrp-lp-feature"><div class="mrp-lp-feature-icon">{icons.svg("chat", 18, 2)}</div><div>Contacto directo<small>Llama o escribe por WhatsApp</small></div></div>'
        f'<div class="mrp-lp-feature"><div class="mrp-lp-feature-icon">{icons.svg("building", 18, 2)}</div><div>Compras y obras<small>Órdenes, stock, asistencia y avance</small></div></div>'
        "</div>"
        "</div>"
        "<div>"
        '<div class="mrp-lp-divider"></div>'
        f"{stat_html}"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_status_line() -> None:
    if USING_LOCAL:
        label, kind = "Modo local (SQLite)", "local"
    else:
        label, kind = "Conectado a Supabase", "ok"
    st.markdown(
        '<div class="mrp-rp-status">'
        '<div class="mrp-rp-status-label">Acceso al sistema</div>'
        f'<div class="mrp-rp-status-dot {kind}">{label}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _render_login() -> None:
    st.markdown(
        '<div class="mrp-rp-eyebrow">Bienvenido</div>'
        '<div class="mrp-rp-headline">Inicia sesión para continuar.</div>'
        '<div class="mrp-rp-copy">Entra con tu usuario y contraseña para gestionar '
        "materiales y proveedores.</div>",
        unsafe_allow_html=True,
    )
    if st.session_state.pop("_access_expired", False):
        st.warning("Tu acceso temporal terminó. Pide al administrador que lo reactive; tu usuario y contraseña se conservan.", icon=":material/schedule:")
    with st.form("login_form"):
        username = st.text_input("Usuario", placeholder="Escribe tu usuario", help="Usa el usuario que te asignó el administrador.")
        password = st.text_input("Contraseña", type="password", placeholder="Escribe tu contraseña", help="Puedes mostrarla con el icono del ojo.")
        submitted = st.form_submit_button("Iniciar sesión  →", type="primary", width="stretch")
    with st.popover("¿Necesitas ayuda para ingresar?"):
        st.write("Escribe tu usuario y contraseña y pulsa «Iniciar sesión». Si no tienes acceso, solicita una cuenta al administrador de tu obra.")

    if not submitted:
        return

    issues = []
    if not username.strip():
        issues.append("Usuario: escribe tu usuario de acceso.")
    if not password:
        issues.append("Contraseña: escribe tu contraseña.")
    if forms.errors(issues):
        return

    wait = security.lock_remaining(username)
    if wait:
        st.error(f"Demasiados intentos fallidos. Espera {security.minutes(wait)} para volver a intentarlo.", icon=":material/lock_clock:")
        return
    user = repo.get_user_by_username(username.strip())
    if not user or not user.get("active", True) or not verify_password(password, user["password_hash"]):
        left, locked = security.register_failure(username)
        if locked:
            st.error(f"Demasiados intentos fallidos. Acceso bloqueado {security.minutes(locked)}.", icon=":material/lock_clock:")
        else:
            st.error(f"Usuario o contraseña incorrectos. Te quedan {left} intento(s).")
        return
    if not access.allowed(user):
        st.error(
            "Tu acceso temporal venció o todavía no está activo. Pide al administrador que lo reactive; tu usuario y contraseña se conservan.",
            icon=":material/schedule:",
        )
        return
    security.register_success(username)

    st.session_state[SESSION_KEY] = session.user_state(user)
    session.remember(user["username"])
    st.rerun()


def _render_bootstrap() -> None:
    st.markdown(
        '<div class="mrp-rp-eyebrow">Primer acceso</div>'
        '<div class="mrp-rp-headline">Crea el administrador.</div>'
        '<div class="mrp-rp-copy">Todavía no hay usuarios registrados; esta cuenta '
        "quedará como Administrador del sistema.</div>",
        unsafe_allow_html=True,
    )
    with st.form("bootstrap_form"):
        name = st.text_input("Nombre completo", placeholder="Ej. Ana Pérez", max_chars=forms.RULES["Nombre completo"]["max"])
        username = st.text_input("Usuario", placeholder="Ej. aperez", max_chars=forms.RULES["Usuario"]["max"], help="Letras sin tildes, números, punto, guion y guion bajo.")
        password = st.text_input("Contraseña", type="password", help="Al menos 8 caracteres, con letras y números.")
        password2 = st.text_input("Repetir contraseña", type="password", help="Escribe la misma contraseña para confirmar.")
        submitted = st.form_submit_button("Crear administrador  →", type="primary", width="stretch")

    if not submitted:
        return

    issues = forms.validate({"Nombre completo": name, "Usuario": username})
    if password != password2:
        issues.append("Repetir contraseña: ambas contraseñas deben coincidir.")
    issues += security.password_issues(password, username)
    if forms.errors(issues):
        return

    repo.create_user(username.strip(), hash_password(password), name.strip(), "admin")
    ui.flash("Administrador creado. Ya puedes iniciar sesión.", log=False)
    st.rerun()
