// Auditor de espaciado: pégalo en la consola del navegador con la app abierta y ejecuta window.__audit().
// Devuelve pares de elementos que se solapan (SOLAPE) o quedan a menos de 5 px (PEGADO).
// Ignora el contenido de expansores cerrados. Útil tras tocar modules/styles/*.css.
window.__audit = function (root) {
  root = root || document;
  const SEL = [
    '.mrp-eyebrow', '.mrp-page-title', '.mrp-page-subtitle', '.mrp-panel-title', '.mrp-chart-sub', '.mrp-form-title', '.mrp-form-description',
    '.mrp-form-section', '.mrp-sidebar-section', '.mrp-result-count', '.mrp-live', '.mrp-dup', '.mrp-tip', '.mrp-hero', '.mrp-stat-card',
    '.mrp-row-name', '.mrp-row-sub', '.mrp-activity-name', '.mrp-activity-sub', '.mrp-pill', 'a.mrp-link', '.mrp-empty',
    '[data-testid="stWidgetLabel"]', '[data-testid="stCaptionContainer"]', 'button[kind]', '[data-baseweb="input"]', '[data-baseweb="select"] > div',
    '[data-baseweb="textarea"]', '[data-baseweb="tab-list"]', '[data-testid="stDataFrame"]', '[data-testid="stExpander"]', '[data-testid="stAlertContainer"]',
    '.mrp-formprogress', '.mrp-usercard', '.mrp-brand', 'h1', 'h2', 'h3',
  ].join(',');
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 2 && r.height > 2 && cs.visibility !== 'hidden' && cs.display !== 'none' && cs.opacity !== '0'; };
  const nodes = [...root.querySelectorAll(SEL)].filter(vis);
  // quitar anidados del mismo tipo para no duplicar (button dentro de button, etc.)
  const issues = [];
  const name = (e) => (e.className && typeof e.className === 'string' ? e.className.split(' ')[0] : e.tagName.toLowerCase()) + ':' + (e.innerText || e.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 24);
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j];
      if (a.contains(b) || b.contains(a)) continue;
      const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
      const ox = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
      if (ox <= 2) continue; // no comparten columna
      const gap = ra.top < rb.top ? rb.top - ra.bottom : ra.top - rb.bottom;
      const first = ra.top < rb.top ? a : b, second = first === a ? b : a;
      if (gap < -1) {
        // solape real: ¿también solapan en vertical por más de 2px?
        const oy = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
        if (oy > 2) issues.push(['SOLAPE', Math.round(-gap), name(first), name(second)]);
      } else if (gap < 5 && gap >= -1) {
        // vecinos casi pegados (excepciones: relaciones intencionales pegadas)
        const pair = first.className + ' ' + second.className;
        const okPairs = /mrp-live|mrp-dup|WidgetLabel|stWidgetLabel/;
        if (!okPairs.test(String(first.className) + String(second.className)) && !first.matches('[data-testid="stWidgetLabel"]'))
          issues.push(['PEGADO', Math.round(gap), name(first), name(second)]);
      }
    }
  }
  // texto cortado por su contenedor (scroll > client)
  document.querySelectorAll('.mrp-sidebar-section,.mrp-eyebrow,.mrp-pill,.mrp-page-title').forEach((e) => {
    if (vis(e) && e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflow !== 'visible') issues.push(['CORTADO', 0, name(e), '']);
  });
  const seen = new Set();
  return issues.filter((x) => { const k = x.join('|'); if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 60);
};
'audit ready';
