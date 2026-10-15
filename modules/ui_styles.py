"""Sistema visual: paleta (claro/oscuro), tipografía, superficies, botones,
campos, pestañas, diálogos y componentes `.mrp-*`. Todo se controla con
variables CSS, así que cambiar de tema solo cambia los valores de abajo."""

LIGHT = """
--mrp-bg:#F2F3FA;--mrp-surface:#FFFFFF;--mrp-raised:#FFFFFF;--mrp-field:#F5F6FC;
--mrp-text:#141A33;--mrp-muted:#5C6685;--mrp-border:#E2E5F1;--mrp-accent:#6B57F5;
--mrp-soft:#EEEAFF;--mrp-hover:#F8F6FF;
--mrp-grad:linear-gradient(135deg,#7C66FF 0%,#5A3FF0 100%);
--mrp-shadow:0 1px 2px rgba(20,26,51,.04),0 10px 28px -8px rgba(20,26,51,.10);
--mrp-shadow-lg:0 2px 4px rgba(20,26,51,.05),0 22px 48px -12px rgba(60,45,160,.22);
--mrp-good:#16794A;--mrp-good-bg:#E6F7EE;--mrp-bad:#C0343F;--mrp-bad-bg:#FDECEE;
--mrp-warn:#94600F;--mrp-warn-bg:#FFF3DA;--mrp-info:#2459A8;--mrp-info-bg:#E8F1FF;
--mrp-teal:#0E8A8A;--mrp-teal-bg:#E1F6F5;
--mrp-glow-a:rgba(124,102,255,.14);--mrp-glow-b:rgba(34,211,238,.08);
color-scheme:light;
"""
DARK = """
--mrp-bg:#0B1020;--mrp-surface:#131A2F;--mrp-raised:#1B2442;--mrp-field:#0F1629;
--mrp-text:#EEF1FC;--mrp-muted:#A7B2CE;--mrp-border:#28345A;--mrp-accent:#A596FF;
--mrp-soft:#2A2356;--mrp-hover:#1C2546;
--mrp-grad:linear-gradient(135deg,#8B79FF 0%,#5F45F2 100%);
--mrp-shadow:0 1px 2px rgba(0,0,0,.25),0 12px 30px -10px rgba(0,0,0,.55);
--mrp-shadow-lg:0 2px 4px rgba(0,0,0,.3),0 24px 52px -14px rgba(0,0,0,.7);
--mrp-good:#7FE0AB;--mrp-good-bg:#143B30;--mrp-bad:#FFA9B1;--mrp-bad-bg:#47232F;
--mrp-warn:#F3CD7E;--mrp-warn-bg:#41341D;--mrp-info:#A8CBFF;--mrp-info-bg:#1F3558;
--mrp-teal:#6FE0DC;--mrp-teal-bg:#133B3F;
--mrp-glow-a:rgba(139,121,255,.20);--mrp-glow-b:rgba(34,211,238,.08);
color-scheme:dark;
"""
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,.stApp,input,textarea,button {font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;-webkit-font-smoothing:antialiased;}
@keyframes mrpUp {from {opacity:0;transform:translateY(10px);} to {opacity:1;transform:none;}}
@keyframes mrpPop {from {opacity:0;transform:scale(.97);} to {opacity:1;transform:none;}}

/* ---------- Lienzo ---------- */
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"] {
  background:radial-gradient(900px 420px at 88% -8%,var(--mrp-glow-a),transparent 62%),
             radial-gradient(760px 420px at -4% 0%,var(--mrp-glow-b),transparent 58%),var(--mrp-bg);
  color:var(--mrp-text);}
[data-testid="stHeader"] {background:transparent;backdrop-filter:blur(8px);}
[data-testid="stMainBlockContainer"] {max-width:1480px;padding:2.2rem 2.6rem 4rem;}

/* ---------- Sidebar (siempre oscuro) ---------- */
[data-testid="stSidebar"] {background:linear-gradient(185deg,#0E1230 0%,#171043 58%,#21155C 100%);border-right:0;}
[data-testid="stSidebarContent"] {padding-top:.4rem;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {color:#9CA6CC!important;}
[data-testid="stSidebar"] hr {border-color:rgba(255,255,255,.10)!important;}
[data-testid="stSidebar"] [data-testid="stAlertContainer"]:has([data-testid]) {background:rgba(255,255,255,.08)!important;border:1px solid rgba(255,255,255,.14)!important;}
[data-testid="stSidebar"] [data-testid="stAlertContainer"] p,[data-testid="stSidebar"] [data-testid="stAlertContainer"] svg {color:#D8DCF3!important;fill:#D8DCF3!important;}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,[data-testid="stSidebar"] label p {color:#D8DCF3!important;}
.st-key-mrp_sidebar_navigation [data-testid="stVerticalBlock"],.st-key-mrp_sidebar_navigation {gap:3px;}
.st-key-mrp_sidebar_navigation button[kind] {justify-content:flex-start;gap:6px;padding:10px 14px;min-height:42px;background:transparent!important;border:1px solid transparent!important;color:#C9CFEE!important;box-shadow:none!important;border-radius:12px!important;font-weight:600!important;}
.st-key-mrp_sidebar_navigation button[kind] {text-align:left;}
.st-key-mrp_sidebar_navigation button[kind]>div {justify-content:flex-start!important;width:100%;gap:10px;}
.st-key-mrp_sidebar_navigation button[kind] p {color:#C9CFEE!important;font-size:14px;text-align:left;}
.st-key-mrp_sidebar_navigation button[kind] svg,.st-key-mrp_sidebar_navigation button[kind] [data-testid="stIconMaterial"] {color:#A9B2DC!important;fill:#A9B2DC!important;}
.st-key-mrp_sidebar_navigation button[kind="secondary"]:hover {background:rgba(255,255,255,.08)!important;border-color:rgba(255,255,255,.08)!important;}
.st-key-mrp_sidebar_navigation button[kind="secondary"]:hover p {color:#FFFFFF!important;}
.st-key-mrp_sidebar_navigation button[kind="primary"] {background:var(--mrp-grad)!important;border:1px solid rgba(255,255,255,.18)!important;box-shadow:0 8px 20px -6px rgba(110,90,255,.7)!important;filter:none;}
.st-key-mrp_sidebar_navigation button[kind="primary"] p,.st-key-mrp_sidebar_navigation button[kind="primary"] [data-testid="stIconMaterial"] {color:#FFFFFF!important;}
[data-testid="stSidebar"] button[kind="secondary"]:not(.st-key-mrp_sidebar_navigation button) {background:rgba(255,255,255,.07)!important;border-color:rgba(255,255,255,.14)!important;color:#EDEFFC!important;}
[data-testid="stSidebar"] button[kind="secondary"]:not(.st-key-mrp_sidebar_navigation button) p {color:#EDEFFC!important;}
.mrp-brand {display:flex;align-items:center;gap:12px;margin:6px 0 14px;}
.mrp-brand-badge {width:42px;height:42px;display:grid;place-items:center;background:var(--mrp-grad);border-radius:13px;font-size:20px;box-shadow:0 8px 20px -6px rgba(110,90,255,.8);}
.mrp-brand-name {font-size:16px;font-weight:800;color:#FFFFFF;letter-spacing:-.2px;}
.mrp-brand-sub {font-size:12px;color:#9CA6CC;}
.mrp-usercard {display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:14px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.10);margin:0 0 12px;}
.mrp-usercard .mrp-avatar {background:var(--mrp-grad);color:#fff;border-radius:50%;width:34px;height:34px;min-width:34px;font-size:14px;}
.mrp-usercard-name {font-size:13px;font-weight:700;color:#FFFFFF;line-height:1.2;}
.mrp-usercard-role {font-size:11px;color:#A9B2DC;}
.mrp-sidebar-section {font-size:10px;color:#7F89B6;font-weight:700;text-transform:uppercase;letter-spacing:.12em;margin:14px 6px 6px;}

/* ---------- Superficies ---------- */
[data-testid="stVerticalBlock"] {border-color:var(--mrp-border)!important;border-radius:18px;gap:.85rem;}
[data-testid="stLayoutWrapper"]>[data-testid="stVerticalBlock"]:has(.mrp-row) {background:var(--mrp-surface);box-shadow:var(--mrp-shadow);transition:transform .18s,border-color .18s,box-shadow .18s,background .18s;position:relative;}
[data-testid="stLayoutWrapper"]>[data-testid="stVerticalBlock"]:has(.mrp-row):hover {background:var(--mrp-hover);border-color:var(--mrp-accent)!important;box-shadow:var(--mrp-shadow-lg);transform:translateY(-1px);}
[data-testid="stLayoutWrapper"]>[data-testid="stVerticalBlock"]:has(.mrp-panel-title),[data-testid="stLayoutWrapper"]>[data-testid="stVerticalBlock"]:has(.mrp-panel-title) {background:var(--mrp-surface);box-shadow:var(--mrp-shadow);}
[data-testid="stForm"] {border-color:var(--mrp-border);background:var(--mrp-surface);border-radius:20px;padding:22px;box-shadow:var(--mrp-shadow);}
[data-testid="stExpander"] {background:var(--mrp-surface);border:1px solid var(--mrp-border)!important;border-radius:16px!important;box-shadow:var(--mrp-shadow);overflow:hidden;}
[data-testid="stExpander"] summary,[data-testid="stExpander"] summary p {color:var(--mrp-text);font-weight:600;}
[data-testid="stDataFrame"] {border:1px solid var(--mrp-border);border-radius:16px;overflow:hidden;box-shadow:var(--mrp-shadow);}
hr {border-color:var(--mrp-border)!important;}

/* ---------- Botones ---------- */
button[kind] {border-radius:12px!important;min-height:42px;font-weight:600!important;letter-spacing:-.1px;transition:transform .15s,background .15s,box-shadow .15s,border-color .15s;}
button[kind="primary"],button[kind="primaryFormSubmit"] {background:var(--mrp-grad)!important;color:#FFF!important;border:1px solid rgba(255,255,255,.14)!important;box-shadow:0 8px 20px -8px rgba(100,80,245,.75);}
button[kind="primary"]:hover,button[kind="primaryFormSubmit"]:hover {box-shadow:0 12px 26px -8px rgba(100,80,245,.85);transform:translateY(-1px);filter:brightness(1.06);}
button[kind="primary"]:active,button[kind="primaryFormSubmit"]:active {transform:translateY(0);}
button[kind="secondary"],button[kind="secondaryFormSubmit"],button[kind="tertiary"] {color:var(--mrp-text)!important;background:var(--mrp-surface)!important;border:1px solid var(--mrp-border)!important;box-shadow:0 1px 2px rgba(20,26,51,.04);}
button[kind="secondary"]:hover,button[kind="secondaryFormSubmit"]:hover {background:var(--mrp-soft)!important;border-color:var(--mrp-accent)!important;color:var(--mrp-accent)!important;transform:translateY(-1px);}
button[kind]:disabled {opacity:.5;cursor:not-allowed;box-shadow:none;filter:none;transform:none;}
button:focus-visible,a:focus-visible,[role="tab"]:focus-visible {outline:3px solid var(--mrp-accent)!important;outline-offset:3px;}
button[kind="primary"] p,button[kind="primaryFormSubmit"] p {color:#FFFFFF!important;}
[data-testid="stDownloadButton"] button,[data-testid="stLinkButton"] a {border-radius:12px!important;}

/* ---------- Campos ---------- */
[data-testid="stWidgetLabel"] p,[data-testid="stMarkdownContainer"] p,[data-testid="stMarkdownContainer"] li,[data-testid="stMarkdownContainer"] h1,[data-testid="stMarkdownContainer"] h2,[data-testid="stMarkdownContainer"] h3 {color:var(--mrp-text);}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p {color:var(--mrp-muted)!important;}
[data-testid="stWidgetLabel"] p {font-size:12.5px;font-weight:600;line-height:1.45;letter-spacing:.01em;}
[data-testid="stMetricValue"],[data-testid="stMetricLabel"],[data-testid="stMetricLabel"] p {color:var(--mrp-text)!important;}
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div {background:var(--mrp-field)!important;border:1px solid var(--mrp-border);border-radius:12px!important;min-height:44px;transition:border-color .15s,box-shadow .15s,background .15s;}
[data-baseweb="input"]:hover,[data-baseweb="textarea"]:hover,[data-baseweb="select"]>div:hover {border-color:color-mix(in srgb,var(--mrp-accent) 45%,var(--mrp-border));}
[data-baseweb="base-input"],[data-baseweb="input"] input,[data-baseweb="textarea"] textarea {background:transparent!important;color:var(--mrp-text)!important;caret-color:var(--mrp-accent);}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within,[data-baseweb="select"]>div:focus-within {border-color:var(--mrp-accent)!important;background:var(--mrp-surface)!important;box-shadow:0 0 0 4px color-mix(in srgb,var(--mrp-accent) 18%,transparent);}
input::placeholder,textarea::placeholder {color:var(--mrp-muted)!important;opacity:.7;}
[data-baseweb="select"] span,[data-baseweb="select"] div,[data-baseweb="select"] input {color:var(--mrp-text);}
[data-baseweb="select"] svg,[data-testid="stNumberInput"] button svg,[data-testid="stHeader"] svg {fill:var(--mrp-muted);color:var(--mrp-muted);}
[data-baseweb="popover"]>div,[data-baseweb="menu"],[role="listbox"],[data-testid="stPopoverBody"],[data-testid="stTooltipContent"] {background:var(--mrp-raised)!important;color:var(--mrp-text)!important;border:1px solid var(--mrp-border)!important;border-radius:14px!important;box-shadow:var(--mrp-shadow-lg)!important;}
[role="option"],[data-baseweb="menu"] li {color:var(--mrp-text)!important;background:transparent!important;border-radius:8px;}
[role="option"]:hover,[data-baseweb="menu"] li:hover,[role="option"][aria-selected="true"] {background:var(--mrp-soft)!important;}
[data-baseweb="tag"] {background:var(--mrp-soft)!important;color:var(--mrp-accent)!important;border-radius:8px!important;}
[data-testid="stToggle"] label p {font-weight:600;}
[data-testid="stSidebar"] [data-testid="stToggle"] label p {color:#D8DCF3!important;}
[data-testid="stCheckbox"] label {font-weight:500;}

/* ---------- Pestañas (segmentadas) ---------- */
[data-baseweb="tab-list"] {gap:4px;background:var(--mrp-field);border:1px solid var(--mrp-border);border-radius:14px;padding:4px;width:fit-content;max-width:100%;overflow-x:auto;}
[data-baseweb="tab-highlight"],[data-baseweb="tab-border"] {display:none!important;}
[data-baseweb="tab"] {color:var(--mrp-muted);padding:9px 16px;border-radius:10px;font-weight:600;background:transparent;transition:background .15s,color .15s;}
[data-baseweb="tab"]:hover {color:var(--mrp-text);}
[data-baseweb="tab"][aria-selected="true"] {color:var(--mrp-accent);background:var(--mrp-surface);box-shadow:0 1px 3px rgba(20,26,51,.12);font-weight:700;}
[data-baseweb="tab-panel"] {padding-top:1rem;}

/* ---------- Diálogos, avisos, toast, progreso ---------- */
[data-testid="stDialog"] {backdrop-filter:blur(6px);background:rgba(8,12,30,.50);}
[data-testid="stDialog"] [role="dialog"] {background:var(--mrp-surface);color:var(--mrp-text);border:1px solid var(--mrp-border);border-radius:24px!important;box-shadow:0 30px 100px rgba(0,0,0,.35);animation:mrpPop .22s ease-out;max-height:calc(100dvh - 32px);overflow-y:auto;scrollbar-gutter:stable;}
[data-testid="stDialog"] [role="dialog"]>div:first-child {background:var(--mrp-surface);}
[data-testid="stDialog"] h2 {font-weight:800;letter-spacing:-.4px;}
[data-testid="stAlertContainer"] {border-radius:14px!important;border:1px solid var(--mrp-border)!important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {background:var(--mrp-info-bg)!important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {background:var(--mrp-good-bg)!important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {background:var(--mrp-warn-bg)!important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {background:var(--mrp-bad-bg)!important;}
[data-testid="stAlertContainer"] p {color:var(--mrp-text)!important;}
[data-testid="stToast"] {background:var(--mrp-raised)!important;color:var(--mrp-text)!important;border:1px solid var(--mrp-border)!important;border-radius:14px!important;box-shadow:var(--mrp-shadow-lg)!important;}
[data-testid="stProgress"] [role="progressbar"] {background:var(--mrp-field)!important;border-radius:99px;overflow:hidden;}
[data-testid="stProgress"] [role="progressbar"]>div {background:var(--mrp-grad)!important;border-radius:99px;}
::-webkit-scrollbar {width:9px;height:9px;}::-webkit-scrollbar-track {background:transparent;}::-webkit-scrollbar-thumb {background:color-mix(in srgb,var(--mrp-muted) 35%,transparent);border-radius:20px;}

/* ---------- Encabezado de página ---------- */
.mrp-eyebrow {display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--mrp-accent);background:var(--mrp-soft);border-radius:99px;padding:4px 11px;margin-bottom:10px;}
.mrp-page-title {font-size:32px;font-weight:800;line-height:1.15;letter-spacing:-.9px;color:var(--mrp-text);margin-bottom:8px;overflow-wrap:anywhere;}
.mrp-page-subtitle {font-size:14.5px;line-height:1.6;color:var(--mrp-muted);margin-bottom:10px;max-width:760px;}
.mrp-hero {position:relative;overflow:hidden;border-radius:26px;padding:30px 32px;margin-bottom:6px;color:#fff;background:radial-gradient(520px 260px at 92% 0%,rgba(255,255,255,.22),transparent 60%),radial-gradient(420px 260px at 0% 120%,rgba(34,211,238,.28),transparent 60%),linear-gradient(135deg,#6E58F7 0%,#4B2FD8 55%,#2A1B8F 100%);box-shadow:0 24px 50px -18px rgba(75,47,216,.7);animation:mrpUp .4s ease-out;}
.mrp-hero::after {content:"";position:absolute;right:-60px;bottom:-90px;width:260px;height:260px;border-radius:50%;border:44px solid rgba(255,255,255,.07);}
.mrp-hero-eyebrow {font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.78);margin-bottom:8px;}
.mrp-hero-title {font-size:34px;font-weight:800;letter-spacing:-1px;line-height:1.1;}
.mrp-hero-sub {max-width:640px;font-size:14.5px;line-height:1.6;color:rgba(255,255,255,.82);margin-top:10px;}
.mrp-hero-chips {display:flex;flex-wrap:wrap;gap:8px;margin-top:18px;}
.mrp-hero-chip {display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;padding:6px 12px;border-radius:99px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.18);backdrop-filter:blur(6px);}

/* ---------- Tarjetas de estadística ---------- */
.mrp-stat-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:16px;margin:20px 0 18px;}
.mrp-stat-card,.mrp-panel,.mrp-card {background:var(--mrp-surface);border:1px solid var(--mrp-border);border-radius:20px;box-shadow:var(--mrp-shadow);}
.mrp-stat-card {position:relative;overflow:hidden;padding:20px 20px 18px;transition:transform .18s,box-shadow .18s,border-color .18s;animation:mrpUp .4s ease-out both;--tone:var(--mrp-accent);--tone-bg:var(--mrp-soft);}
.mrp-stat-card:nth-child(2) {animation-delay:.04s;}.mrp-stat-card:nth-child(3) {animation-delay:.08s;}.mrp-stat-card:nth-child(4) {animation-delay:.12s;}.mrp-stat-card:nth-child(5) {animation-delay:.16s;}
.mrp-stat-card::before {content:"";position:absolute;left:0;right:0;top:0;height:3px;background:var(--tone);opacity:.85;}
.mrp-stat-card:hover {transform:translateY(-3px);box-shadow:var(--mrp-shadow-lg);border-color:color-mix(in srgb,var(--tone) 40%,var(--mrp-border));}
.mrp-tone-green {--tone:var(--mrp-good);--tone-bg:var(--mrp-good-bg);}.mrp-tone-amber,.mrp-warn {--tone:#E0951A;--tone-bg:var(--mrp-warn-bg);}
.mrp-tone-blue {--tone:var(--mrp-info);--tone-bg:var(--mrp-info-bg);}.mrp-tone-red {--tone:var(--mrp-bad);--tone-bg:var(--mrp-bad-bg);}.mrp-tone-teal {--tone:var(--mrp-teal);--tone-bg:var(--mrp-teal-bg);}
.mrp-stat-top {display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:14px;}
.mrp-stat-label {font-size:11px;text-transform:uppercase;letter-spacing:.07em;font-weight:700;color:var(--mrp-muted);}
.mrp-icon-badge {width:38px;height:38px;flex-shrink:0;background:var(--tone-bg);border-radius:12px;display:grid;place-items:center;font-size:18px;}
.mrp-stat-value {font-size:31px;font-weight:800;letter-spacing:-.8px;color:var(--mrp-text);font-variant-numeric:tabular-nums;line-height:1.15;overflow-wrap:anywhere;}
.mrp-stat-caption {color:var(--mrp-muted);font-size:12.5px;line-height:1.5;margin-top:6px;}
.mrp-spark {display:block;width:100%;height:34px;margin-top:10px;}

/* ---------- Paneles, listas y filas ---------- */
.mrp-panel {padding:22px;}
.mrp-panel-title {color:var(--mrp-text);font-size:18px;font-weight:800;letter-spacing:-.3px;margin:2px 0 14px;}
.mrp-activity-item {display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--mrp-border);}
.mrp-activity-item:last-child {border-bottom:0;}
.mrp-activity-name,.mrp-row-name {color:var(--mrp-text);font-size:14px;font-weight:700;overflow-wrap:anywhere;}
.mrp-activity-sub,.mrp-row-sub {color:var(--mrp-muted);font-size:12.5px;line-height:1.5;overflow-wrap:anywhere;}
.mrp-activity-when {font-size:11px;color:var(--mrp-muted);margin-top:5px;}
.mrp-timeline-item {display:flex;gap:12px;align-items:flex-start;padding:11px 0;position:relative;}
.mrp-timeline-item:not(:last-child)::after {content:"";position:absolute;left:17px;top:46px;bottom:-8px;width:2px;background:var(--mrp-border);}
.mrp-timeline-dot {width:36px;height:36px;min-width:36px;border-radius:12px;display:grid;place-items:center;font-size:16px;background:var(--mrp-soft);}
.mrp-timeline-body {flex:1;min-width:0;}
.mrp-timeline-when {font-size:11px;color:var(--mrp-muted);white-space:nowrap;}

.mrp-avatar {width:40px;height:40px;min-width:40px;display:grid;place-items:center;border-radius:13px;background:var(--mrp-soft);color:var(--mrp-accent);font-size:15px;font-weight:800;}
.mrp-row {display:flex;gap:12px;align-items:center;}
.mrp-pill,.mrp-activity-badge {display:inline-flex;align-items:center;gap:6px;background:var(--mrp-soft);color:var(--mrp-accent);font-size:11.5px;font-weight:700;border-radius:99px;padding:4px 11px;white-space:normal;line-height:1.35;}
.mrp-pill::before {content:"";width:6px;height:6px;border-radius:50%;background:currentColor;opacity:.8;flex-shrink:0;}
.mrp-pill-green {background:var(--mrp-good-bg);color:var(--mrp-good);}.mrp-pill-red {background:var(--mrp-bad-bg);color:var(--mrp-bad);}
.mrp-pill-gray {background:var(--mrp-field);color:var(--mrp-muted);border:1px solid var(--mrp-border);}.mrp-pill-amber {background:var(--mrp-warn-bg);color:var(--mrp-warn);}.mrp-pill-blue {background:var(--mrp-info-bg);color:var(--mrp-info);}
.mrp-links {display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;}
a.mrp-link {display:inline-flex;align-items:center;gap:4px;padding:6px 11px;border-radius:99px;background:var(--mrp-soft);color:var(--mrp-accent)!important;text-decoration:none!important;font-size:12px;font-weight:600;border:1px solid transparent;transition:border-color .15s,transform .15s;}
a.mrp-link:hover {border-color:var(--mrp-accent);transform:translateY(-1px);}
.mrp-tip {background:var(--mrp-soft);border:1px solid color-mix(in srgb,var(--mrp-accent) 22%,transparent);border-radius:14px;padding:12px 14px;font-size:12.5px;line-height:1.55;color:var(--mrp-text);margin-bottom:6px;}
.mrp-meter {height:8px;border-radius:99px;background:var(--mrp-field);border:1px solid var(--mrp-border);overflow:hidden;margin:6px 0 4px;}
.mrp-meter>span {display:block;height:100%;border-radius:99px;background:var(--mrp-grad);}

/* ---------- Validación y formularios ---------- */
.mrp-live {display:flex;flex-wrap:wrap;gap:4px 10px;font-size:11.5px;line-height:1.45;max-width:100%;margin:6px 2px 2px;font-weight:500;}
.mrp-live[data-state="ok"] {color:var(--mrp-good);}.mrp-live[data-state="bad"] {color:var(--mrp-bad);}.mrp-live[data-state="idle"] {color:var(--mrp-muted);}
.mrp-live-count {font-variant-numeric:tabular-nums;white-space:nowrap;color:var(--mrp-muted);}
[data-testid="stTextInput"]:has(.mrp-live) [data-testid="InputInstructions"],[data-testid="stNumberInput"]:has(.mrp-live) [data-testid="InputInstructions"],[data-testid="stTextArea"]:has(.mrp-live) [data-testid="InputInstructions"] {display:none;}
.mrp-form-intro {border-bottom:1px solid var(--mrp-border);padding-bottom:14px;margin-bottom:4px;}.mrp-form-title {font-size:18px;font-weight:800;letter-spacing:-.3px;color:var(--mrp-text);}
.mrp-form-description {font-size:13px;line-height:1.6;color:var(--mrp-muted);margin-top:4px;}
.mrp-form-section {display:flex;flex-direction:column;gap:3px;margin:16px 0 4px;padding-top:12px;border-top:1px dashed var(--mrp-border);color:var(--mrp-text);font-size:13px;}.mrp-form-section strong {font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--mrp-accent);}.mrp-form-section span {font-size:12px;color:var(--mrp-muted);line-height:1.5;}

/* ---------- Estados vacíos ---------- */
.mrp-empty {background:var(--mrp-surface);border:1.5px dashed var(--mrp-border);border-radius:22px;text-align:center;padding:40px 22px;margin:14px 0;}
.mrp-empty-icon {width:64px;height:64px;margin:0 auto 14px;border-radius:20px;background:var(--mrp-soft);display:grid;place-items:center;font-size:30px;}
.mrp-empty-title {font-size:17px;font-weight:800;color:var(--mrp-text);letter-spacing:-.2px;}.mrp-empty-copy {max-width:500px;margin:8px auto 0;color:var(--mrp-muted);font-size:13.5px;line-height:1.6;}
.mrp-result-count {font-size:12px;color:var(--mrp-muted);margin:4px 0 12px;font-weight:500;}

/* ---------- Responsive y accesibilidad ---------- */
@media(max-width:900px) {[data-testid="stMainBlockContainer"] {padding:2rem 1.3rem 3rem;}.mrp-page-title {font-size:27px;}.mrp-hero {padding:24px 22px;border-radius:22px;}.mrp-hero-title {font-size:27px;}}
@media(max-width:640px) {[data-testid="stMainBlockContainer"] {padding:3.5rem 1rem 3rem;}.mrp-stat-grid {grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;}.mrp-stat-card {padding:15px 13px;}.mrp-stat-value {font-size:24px;}.mrp-page-title {font-size:24px;}.mrp-panel {padding:16px;}.mrp-activity-item {flex-wrap:wrap;}[data-testid="stDialog"] [role="dialog"] {width:calc(100vw - 16px)!important;margin:8px;border-radius:18px!important;}[data-testid="stForm"] {padding:15px;}[data-baseweb="tab-list"] {width:100%;}}
@media(prefers-reduced-motion:reduce) {*,*::before,*::after {animation:none!important;transition:none!important;scroll-behavior:auto!important;}}
"""
