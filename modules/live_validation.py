"""Validación en vivo de formularios.

Streamlit solo manda el valor de un campo al servidor al salir de él (o con
Enter), así que no puede avisar mientras se teclea. Por eso se inyecta un
script en la página que escucha lo que se escribe y, por cada campo con regla
(se identifica por su etiqueta), muestra debajo:

- cuántos caracteres lleva / el máximo, y cuántos faltan para el mínimo,
- qué caracteres no se permiten (si se usó alguno) y por qué el formato es malo,
- borde rojo si está mal, verde si está bien, y un ejemplo mientras está vacío.

Es solo ayuda visual: las reglas definitivas se siguen aplicando al guardar."""
from __future__ import annotations

import json

import streamlit.components.v1 as components

_PERSON = r"[\p{L} .'\-]"
_TEXT = r"""[\p{L}\p{N} .,;:'"&()/#%+\-_=°²³¼½¾]"""

# etiqueta del campo -> regla. Claves: required, min, max (largo), allowed (clase
# de caracteres permitida, regex JS con flag u), allowed_desc, pattern + pattern_msg
# (formato del valor completo), digits [min, max] (cantidad de dígitos),
# num {min, max, gt0} (campos numéricos), hint (ejemplo).
RULES: dict[str, dict] = {
    # proveedores
    "Nombre del proveedor": {"required": True, "min": 2, "max": 80, "allowed": _TEXT, "allowed_desc": "letras, números y . , & ( ) / -", "hint": "Ej. Ferretería Norte"},
    "Persona de contacto (opcional)": {"max": 60, "allowed": _PERSON, "allowed_desc": "solo letras, espacios, punto, apóstrofo y guion", "hint": "Ej. Ana Ruiz"},
    "Teléfono": {"max": 20, "allowed": r"[0-9+()\-\s]", "allowed_desc": "dígitos, +, espacios, guion y paréntesis", "digits": [7, 15], "hint": "Con código de país, ej. 51987654321"},
    "Correo (opcional)": {"max": 80, "pattern": r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$", "pattern_msg": "Formato de correo: nombre@dominio.com", "hint": "Ej. ventas@empresa.com"},
    "Notas (opcional)": {"max": 200, "hint": "Ej. Entrega antes del viernes"},
    # materiales
    "Categoría": {"required": True, "min": 2, "max": 60, "allowed": _TEXT, "allowed_desc": "letras, números y . , & ( ) / -", "hint": "Ej. Concreto"},
    "Nombre": {"required": True, "min": 2, "max": 100, "allowed": _TEXT, "allowed_desc": "letras, números y . , & ( ) / -", "hint": "Ej. Concreto f'c=210"},
    "Métrica de cómputo": {"max": 60, "allowed": _TEXT, "allowed_desc": "letras, números y . , ( ) / -", "hint": "Ej. Volumen (m³)"},
    "Densidad (kg/m³, opcional)": {"num": {"min": 0, "max": 25000}, "hint": "Ej. 2400 (concreto)"},
    # trabajadores
    "Nombre completo": {"required": True, "min": 3, "max": 80, "allowed": _PERSON, "allowed_desc": "solo letras, espacios, punto, apóstrofo y guion", "hint": "Ej. Juan Pérez"},
    "Documento (opcional)": {"max": 15, "allowed": r"[A-Za-z0-9\-]", "allowed_desc": "letras, números y guion", "hint": "Ej. 45879632"},
    "Puesto (opcional)": {"max": 60, "allowed": _TEXT, "allowed_desc": "letras y números", "hint": "Ej. Capataz"},
    "Nombre de la cuadrilla": {"required": True, "min": 2, "max": 50, "allowed": _TEXT, "allowed_desc": "letras y números", "hint": "Ej. Electricistas"},
    "Nombre de la obra": {"required": True, "min": 2, "max": 80, "allowed": _TEXT, "allowed_desc": "letras, números y . , & ( ) / -", "hint": "Ej. Torre Central"},
    "Dirección": {"max": 150, "allowed": _TEXT, "allowed_desc": "letras, números y . , # -", "hint": "Calle y número, distrito, ciudad"},
    "Usuario": {"required": True, "min": 3, "max": 30, "allowed": r"[A-Za-z0-9._\-]", "allowed_desc": "letras sin tilde, números, punto, guion y _", "hint": "Ej. jperez"},
    # números
    "Cantidad": {"num": {"gt0": True, "max": 1000000}, "hint": "Mayor que 0"},
    "Precio unit.": {"num": {"min": 0, "max": 10000000}, "hint": "0 = sin precio"},
    "Precio unit. estimado": {"num": {"min": 0, "max": 10000000}},
}


def inject() -> None:
    """Instala (una sola vez por pestaña) el validador y le pasa las reglas.

    El componente vive en un iframe que Streamlit destruye y recrea en cada
    recarga, y los observadores creados dentro de él mueren con él; por eso
    el iframe solo carga el script como <script> en la página principal, donde
    sobrevive, y en las siguientes recargas únicamente actualiza las reglas."""
    loader = (
        "const P = window.parent;"
        f"P.__mrpRules = {json.dumps(RULES, ensure_ascii=False)};"
        "if (P.__mrpLiveInstalled) { if (P.__mrpScan) P.__mrpScan(); }"
        f"else {{ const s = P.document.createElement('script'); s.textContent = {json.dumps(_SCRIPT)}; P.document.head.appendChild(s); }}"
    )
    components.html(f"<script>{loader}</script>", height=0)


_SCRIPT = r"""
(function () {
  const P = window, D = document;
  P.__mrpLiveInstalled = true;

  const COLORS = { ok: '#1F9254', bad: '#D64545', idle: '#9095A6' };

  function ruleFor(el) {
    const label = el.getAttribute('aria-label');
    if (!label || el.closest('[data-baseweb="select"]')) return null;
    const r = P.__mrpRules[label];
    if (r) return r;
    if (el.type === 'number' || el.getAttribute('inputmode') === 'decimal') {
      const min = el.getAttribute('min'), max = el.getAttribute('max');
      if (min !== null || max !== null) return { num: { min: min !== null ? parseFloat(min) : undefined, max: max !== null ? parseFloat(max) : undefined } };
    }
    return null;
  }

  function evaluate(value, r, touched) {
    // numérico
    if (r.num) {
      const n = parseFloat(String(value).replace(',', '.'));
      const lim = r.num;
      const range = lim.gt0 ? 'mayor que 0' : (lim.min !== undefined && lim.max !== undefined ? `entre ${lim.min} y ${lim.max}` : lim.min !== undefined ? `mínimo ${lim.min}` : `máximo ${lim.max}`);
      if (value === '' || isNaN(n)) return { s: 'idle', m: `Número ${range}` + (r.hint ? ` · ${r.hint}` : '') };
      if (lim.gt0 && n <= 0) return { s: 'bad', m: '✗ Debe ser mayor que 0' };
      if (lim.min !== undefined && n < lim.min) return { s: 'bad', m: `✗ Muy bajo: el mínimo es ${lim.min}` };
      if (lim.max !== undefined && n > lim.max) return { s: 'bad', m: `✗ Muy alto: el máximo es ${lim.max}` };
      return { s: 'ok', m: `✓ Valor válido (${range})` };
    }
    const len = value.trim().length, errs = [];
    const counter = r.max ? `${value.length}/${r.max}` : `${value.length}`;
    if (value === '') {
      if (r.required && touched) return { s: 'bad', m: '✗ Campo obligatorio', c: counter };
      return { s: 'idle', m: (r.required ? 'Obligatorio' : 'Opcional') + (r.hint ? ` · ${r.hint}` : ''), c: counter };
    }
    if (r.allowed) {
      let re; try { re = new RegExp('^' + r.allowed + '$', 'u'); } catch (err) { re = /^[\s\S]$/; }
      const bad = [...new Set([...value].filter(ch => !re.test(ch)))];
      if (bad.length) errs.push(`Caracteres no permitidos: ${bad.map(b => b === ' ' ? '(espacio)' : b).join(' ')} · solo ${r.allowed_desc}`);
    }
    if (r.min && len < r.min) errs.push(`Faltan ${r.min - len} carácter(es) para el mínimo de ${r.min}`);
    if (r.max && value.length > r.max) errs.push(`Te pasaste por ${value.length - r.max} (máximo ${r.max})`);
    if (r.digits) {
      const d = value.replace(/\D/g, '').length;
      if (d < r.digits[0]) errs.push(`Faltan ${r.digits[0] - d} dígito(s) (mínimo ${r.digits[0]})`);
      else if (d > r.digits[1]) errs.push(`Sobran ${d - r.digits[1]} dígito(s) (máximo ${r.digits[1]})`);
    }
    if (r.pattern && !new RegExp(r.pattern).test(value)) errs.push(r.pattern_msg || 'Formato no válido');
    if (errs.length) return { s: 'bad', m: '✗ ' + errs[0], c: counter };
    return { s: 'ok', m: '✓ Correcto', c: counter };
  }

  function paint(el, touched) {
    const r = ruleFor(el);
    if (!r) return;
    const box = el.closest('[data-baseweb="input"]') || el.closest('[data-baseweb="textarea"]') || el.parentElement;
    const host = el.closest('[data-testid="stTextInput"],[data-testid="stNumberInput"],[data-testid="stTextArea"]');
    if (!host) return;
    let note = host.querySelector(':scope > .mrp-live');
    if (!note) { note = D.createElement('div'); note.className = 'mrp-live'; host.appendChild(note); }
    const res = evaluate(el.value, r, touched);
    const color = COLORS[res.s];
    note.style.color = color;
    const html = `<span>${res.m.replace(/</g, '&lt;')}</span>` + (res.c ? `<span class="mrp-live-count">· ${res.c}</span>` : '');
    if (note.__html !== html) { note.innerHTML = html; note.__html = html; }
    if (box) {
      if (res.s === 'idle') { box.style.removeProperty('border-color'); box.style.removeProperty('box-shadow'); }
      else {
        box.style.setProperty('border-color', color, 'important');
        box.style.setProperty('box-shadow', `0 0 0 2px ${res.s === 'bad' ? 'rgba(214,69,69,.18)' : 'rgba(31,146,84,.16)'}`, 'important');
      }
    }
  }

  D.addEventListener('input', e => { if (e.target.matches && e.target.matches('input,textarea')) { e.target.__touched = true; paint(e.target, true); } }, true);
  D.addEventListener('focusout', e => { if (e.target.matches && e.target.matches('input,textarea')) { e.target.__touched = true; paint(e.target, true); } }, true);

  P.__mrpPaint = paint;
  let timer = null;
  P.__mrpScan = function () {
    D.querySelectorAll('input[aria-label],textarea[aria-label]').forEach(el => { if (ruleFor(el)) paint(el, !!el.__touched); });
  };
  new MutationObserver(() => { clearTimeout(timer); timer = setTimeout(P.__mrpScan, 150); }).observe(D.body, { childList: true, subtree: true });
  P.__mrpScan();
})();
"""
