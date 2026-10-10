"""Paleta y estados comunes. El modo oscuro usa colores propios."""

LIGHT = """
--mrp-bg:#F5F6FB;--mrp-surface:#FFFFFF;--mrp-raised:#FFFFFF;--mrp-field:#F8F9FD;
--mrp-text:#20263B;--mrp-muted:#616B82;--mrp-border:#DFE4EF;--mrp-accent:#6754D7;
--mrp-soft:#F0EDFD;--mrp-hover:#F7F5FF;--mrp-shadow:0 4px 18px rgba(32,38,59,.045);
--mrp-good:#187B48;--mrp-good-bg:#EAF8F0;--mrp-bad:#BF343D;--mrp-bad-bg:#FDEEEF;
--mrp-warn:#956011;--mrp-warn-bg:#FFF4DD;--mrp-info:#275CAA;--mrp-info-bg:#EAF2FE;
color-scheme:light;
"""
DARK = """
--mrp-bg:#111827;--mrp-surface:#1B2538;--mrp-raised:#243148;--mrp-field:#152034;
--mrp-text:#F1F4FC;--mrp-muted:#B7C3DA;--mrp-border:#3D4B64;--mrp-accent:#B2A4FF;
--mrp-soft:#302C50;--mrp-hover:#29344D;--mrp-shadow:0 6px 20px rgba(0,0,0,.13);
--mrp-good:#8BE1B0;--mrp-good-bg:#173E33;--mrp-bad:#FFADB5;--mrp-bad-bg:#492935;
--mrp-warn:#F4D084;--mrp-warn-bg:#443721;--mrp-info:#AACDFF;--mrp-info-bg:#233B5B;
color-scheme:dark;
"""
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,.stApp,input,textarea,button {font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"] {background:var(--mrp-bg);color:var(--mrp-text);}
[data-testid="stHeader"] {background:var(--mrp-bg);}
[data-testid="stMainBlockContainer"] {max-width:1520px;padding:2.4rem 2.3rem 4rem;}
[data-testid="stSidebar"] {background:var(--mrp-surface);border-right:1px solid var(--mrp-border);}
[data-testid="stSidebarContent"] {padding-top:.6rem;}
.st-key-mrp_sidebar_navigation [data-testid="stVerticalBlock"] {gap:6px;}
.st-key-mrp_sidebar_navigation button[kind] {justify-content:flex-start;padding:11px 14px;box-shadow:none!important;}
.st-key-mrp_sidebar_navigation button[kind="primary"] {background:var(--mrp-soft)!important;color:var(--mrp-accent)!important;border:1px solid var(--mrp-accent)!important;filter:none;}
.st-key-mrp_sidebar_navigation button[kind="primary"] p {color:var(--mrp-accent)!important;}
.st-key-mrp_sidebar_navigation button[kind="secondary"] {background:var(--mrp-surface)!important;}
[data-testid="stVerticalBlock"] {border-color:var(--mrp-border)!important;border-radius:16px;gap:.8rem;}
[data-testid="stLayoutWrapper"]>[data-testid="stVerticalBlock"]:has(.mrp-row) {background:var(--mrp-surface);transition:background .15s,border-color .15s,box-shadow .15s;}
[data-testid="stLayoutWrapper"]>[data-testid="stVerticalBlock"]:has(.mrp-row):hover {background:var(--mrp-hover);border-color:var(--mrp-accent)!important;box-shadow:var(--mrp-shadow);}
button[kind] {border-radius:10px!important;min-height:42px;font-weight:600!important;transition:background .15s,box-shadow .15s;}
button[kind="primary"],button[kind="primaryFormSubmit"] {background:linear-gradient(135deg,#705BDD,#5840C4)!important;color:#FFF!important;border:1px solid transparent!important;}
button[kind="primary"]:hover,button[kind="primaryFormSubmit"]:hover {box-shadow:0 4px 14px rgba(103,84,215,.28);filter:brightness(1.08);}
button[kind="secondary"],button[kind="secondaryFormSubmit"],button[kind="tertiary"] {color:var(--mrp-text)!important;background:var(--mrp-surface)!important;border-color:var(--mrp-border)!important;}
button[kind="secondary"]:hover,button[kind="secondaryFormSubmit"]:hover {background:var(--mrp-soft)!important;border-color:var(--mrp-accent)!important;}
button[kind]:disabled {opacity:.5;cursor:not-allowed;box-shadow:none;filter:none;}
button:focus-visible,a:focus-visible,[role="tab"]:focus-visible {outline:3px solid var(--mrp-accent)!important;outline-offset:3px;}
[data-testid="stWidgetLabel"] p,[data-testid="stMarkdownContainer"] p,[data-testid="stMarkdownContainer"] li,[data-testid="stMarkdownContainer"] h1,[data-testid="stMarkdownContainer"] h2,[data-testid="stMarkdownContainer"] h3 {color:var(--mrp-text);}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p {color:var(--mrp-muted)!important;}
[data-testid="stWidgetLabel"] p {font-size:13px;font-weight:600;line-height:1.45;}
button[kind="primary"] p,button[kind="primaryFormSubmit"] p {color:#FFFFFF!important;}
[data-testid="stMetricValue"],[data-testid="stMetricLabel"],[data-testid="stMetricLabel"] p {color:var(--mrp-text)!important;}
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div {background:var(--mrp-field)!important;border:1px solid var(--mrp-border);border-radius:10px!important;transition:border-color .15s,box-shadow .15s;}
[data-baseweb="base-input"],[data-baseweb="input"] input,[data-baseweb="textarea"] textarea {background:transparent!important;color:var(--mrp-text)!important;caret-color:var(--mrp-accent);}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within,[data-baseweb="select"]>div:focus-within {border-color:var(--mrp-accent)!important;box-shadow:0 0 0 3px var(--mrp-soft);}
input::placeholder,textarea::placeholder {color:var(--mrp-muted)!important;opacity:.85;}
[data-baseweb="select"] span,[data-baseweb="select"] div,[data-baseweb="select"] input {color:var(--mrp-text);}
[data-baseweb="select"] svg,[data-testid="stNumberInput"] button svg,[data-testid="stHeader"] svg {fill:var(--mrp-muted);color:var(--mrp-muted);}
[data-baseweb="popover"]>div,[data-baseweb="menu"],[role="listbox"],[data-testid="stPopoverBody"],[data-testid="stTooltipContent"] {background:var(--mrp-raised)!important;color:var(--mrp-text)!important;border-color:var(--mrp-border)!important;}
[role="option"],[data-baseweb="menu"] li {color:var(--mrp-text)!important;background:var(--mrp-raised)!important;}
[role="option"]:hover,[data-baseweb="menu"] li:hover {background:var(--mrp-hover)!important;}
[data-baseweb="tag"] {background:var(--mrp-soft)!important;color:var(--mrp-accent)!important;}
[data-testid="stForm"] {border-color:var(--mrp-border);background:var(--mrp-surface);border-radius:16px;padding:20px;}
[data-testid="stDialog"] [role="dialog"] {background:var(--mrp-surface);color:var(--mrp-text);border:1px solid var(--mrp-border);border-radius:20px!important;box-shadow:0 24px 90px rgba(0,0,0,.25);}
[data-testid="stDialog"] [role="dialog"] {max-height:calc(100dvh - 32px);overflow-y:auto;scrollbar-gutter:stable;}
[data-testid="stDialog"] [role="dialog"]>div:first-child {background:var(--mrp-surface);}
[data-testid="stExpander"] {background:var(--mrp-surface);border:1px solid var(--mrp-border)!important;border-radius:14px!important;}
[data-testid="stExpander"] summary,[data-testid="stExpander"] summary p {color:var(--mrp-text);}
[data-baseweb="tab-list"] {gap:8px;border-bottom:1px solid var(--mrp-border);}
[data-baseweb="tab"] {color:var(--mrp-muted);padding:12px 14px;border-radius:8px 8px 0 0;}
[data-baseweb="tab"][aria-selected="true"] {color:var(--mrp-accent);background:var(--mrp-soft);font-weight:700;}
[data-testid="stAlertContainer"] {border-radius:12px!important;border:1px solid var(--mrp-border)!important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {background:var(--mrp-info-bg)!important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {background:var(--mrp-good-bg)!important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {background:var(--mrp-warn-bg)!important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {background:var(--mrp-bad-bg)!important;}
[data-testid="stAlertContainer"] p {color:var(--mrp-text)!important;}
hr {border-color:var(--mrp-border)!important;}
::-webkit-scrollbar {width:8px;height:8px;}::-webkit-scrollbar-thumb {background:var(--mrp-border);border-radius:20px;}
.mrp-eyebrow {font-size:11px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--mrp-accent);margin-bottom:6px;}
.mrp-page-title {font-size:30px;font-weight:800;line-height:1.2;letter-spacing:-.6px;color:var(--mrp-text);margin-bottom:8px;overflow-wrap:anywhere;}
.mrp-page-subtitle {font-size:14px;line-height:1.6;color:var(--mrp-muted);margin-bottom:8px;max-width:780px;}
.mrp-stat-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:18px 0 16px;}
.mrp-stat-card,.mrp-panel,.mrp-card {background:var(--mrp-surface);border:1px solid var(--mrp-border);border-radius:16px;box-shadow:var(--mrp-shadow);}
.mrp-stat-card {padding:18px;}.mrp-stat-top {display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px;}
.mrp-stat-label {font-size:11px;text-transform:uppercase;letter-spacing:.04em;font-weight:700;color:var(--mrp-muted);}
.mrp-icon-badge {width:36px;height:36px;flex-shrink:0;background:var(--mrp-soft);border-radius:10px;display:grid;place-items:center;font-size:17px;}
.mrp-warn .mrp-icon-badge {background:var(--mrp-warn-bg);}
.mrp-stat-value {font-size:29px;font-weight:800;color:var(--mrp-text);font-variant-numeric:tabular-nums;line-height:1.2;overflow-wrap:anywhere;}
.mrp-stat-caption {color:var(--mrp-muted);font-size:12px;line-height:1.5;margin-top:6px;}
.mrp-panel {padding:20px;}.mrp-panel-title {color:var(--mrp-text);font-size:18px;font-weight:700;margin:4px 0 14px;}
.mrp-activity-item {display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--mrp-border);}
.mrp-activity-item:last-child {border-bottom:0;}
.mrp-activity-name,.mrp-row-name {color:var(--mrp-text);font-size:14px;font-weight:700;overflow-wrap:anywhere;}
.mrp-activity-sub,.mrp-row-sub {color:var(--mrp-muted);font-size:12px;line-height:1.5;overflow-wrap:anywhere;}
.mrp-activity-badge,.mrp-pill {display:inline-block;background:var(--mrp-soft);color:var(--mrp-accent);font-size:11px;font-weight:700;border-radius:7px;padding:4px 9px;white-space:normal;line-height:1.4;}
.mrp-activity-when {font-size:11px;color:var(--mrp-muted);margin-top:5px;}
.mrp-sidebar-section {font-size:10px;color:var(--mrp-muted);font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin:8px 0;}
.mrp-brand {display:flex;align-items:center;gap:10px;margin-bottom:8px;}.mrp-brand-badge {width:40px;height:40px;display:grid;place-items:center;background:#6754D7;border-radius:12px;font-size:20px;}
.mrp-brand-name {font-size:16px;font-weight:800;color:var(--mrp-text);}.mrp-brand-sub {font-size:12px;color:var(--mrp-muted);}
.mrp-avatar {width:38px;height:38px;min-width:38px;display:grid;place-items:center;border-radius:11px;background:var(--mrp-soft);color:var(--mrp-accent);font-size:15px;font-weight:800;}
.mrp-row {display:flex;gap:12px;align-items:center;}
.mrp-pill-green {background:var(--mrp-good-bg);color:var(--mrp-good);}.mrp-pill-red {background:var(--mrp-bad-bg);color:var(--mrp-bad);}
.mrp-pill-gray {background:var(--mrp-field);color:var(--mrp-muted);}.mrp-pill-amber {background:var(--mrp-warn-bg);color:var(--mrp-warn);}.mrp-pill-blue {background:var(--mrp-info-bg);color:var(--mrp-info);}
.mrp-links {display:flex;flex-wrap:wrap;gap:6px;margin-top:4px;}
a.mrp-link {padding:6px 10px;border-radius:8px;background:var(--mrp-soft);color:var(--mrp-accent)!important;text-decoration:none!important;font-size:12px;font-weight:600;}
a.mrp-link:hover {text-decoration:underline!important;}
.mrp-tip {background:var(--mrp-soft);border-left:3px solid var(--mrp-accent);border-radius:8px;padding:12px 14px;font-size:12px;line-height:1.55;color:var(--mrp-text);margin-bottom:6px;}
.mrp-live {display:flex;flex-wrap:wrap;gap:4px 10px;font-size:11px;line-height:1.45;max-width:100%;margin:6px 0 2px;}
.mrp-live[data-state="ok"] {color:var(--mrp-good);}.mrp-live[data-state="bad"] {color:var(--mrp-bad);}.mrp-live[data-state="idle"] {color:var(--mrp-muted);}
.mrp-live-count {font-variant-numeric:tabular-nums;white-space:nowrap;color:var(--mrp-muted);}
[data-testid="stTextInput"]:has(.mrp-live) [data-testid="InputInstructions"],[data-testid="stNumberInput"]:has(.mrp-live) [data-testid="InputInstructions"],[data-testid="stTextArea"]:has(.mrp-live) [data-testid="InputInstructions"] {display:none;}
.mrp-form-intro {border-bottom:1px solid var(--mrp-border);padding-bottom:14px;margin-bottom:4px;}.mrp-form-title {font-size:17px;font-weight:700;color:var(--mrp-text);}
.mrp-form-description {font-size:13px;line-height:1.6;color:var(--mrp-muted);margin-top:4px;}
.mrp-form-section {display:flex;flex-direction:column;gap:3px;margin:12px 0 2px;color:var(--mrp-text);font-size:13px;}.mrp-form-section span {font-size:12px;color:var(--mrp-muted);line-height:1.5;}
.mrp-empty {background:var(--mrp-surface);border:1px dashed var(--mrp-border);border-radius:16px;text-align:center;padding:32px 20px;margin:12px 0;}
.mrp-empty-icon {font-size:28px;margin-bottom:10px;}.mrp-empty-title {font-size:16px;font-weight:700;color:var(--mrp-text);}.mrp-empty-copy {max-width:500px;margin:8px auto 0;color:var(--mrp-muted);font-size:13px;line-height:1.6;}
.mrp-result-count {font-size:12px;color:var(--mrp-muted);margin:4px 0 12px;}
@media(max-width:900px) {[data-testid="stMainBlockContainer"] {padding:2rem 1.3rem 3rem;}.mrp-page-title{font-size:26px;}}
@media(max-width:640px) {[data-testid="stMainBlockContainer"] {padding:3.5rem 1rem 3rem;}.mrp-stat-grid {grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;}.mrp-stat-card {padding:14px 12px;}.mrp-stat-value {font-size:23px;}.mrp-page-title {font-size:24px;}.mrp-panel {padding:15px;}.mrp-activity-item {flex-wrap:wrap;}[data-testid="stDialog"] [role="dialog"] {width:calc(100vw - 16px)!important;margin:8px;border-radius:14px!important;}[data-testid="stForm"] {padding:14px;}}
@media(prefers-reduced-motion:reduce) {*,*::before,*::after {animation:none!important;transition:none!important;scroll-behavior:auto!important;}}
"""
