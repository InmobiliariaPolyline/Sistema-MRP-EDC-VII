"""Ayudas extra de formularios y diseño que solo se pueden hacer en el navegador.

Complementa a `live_validation.py` (que valida cada campo al teclear):

- **Progreso de obligatorios**: arriba de cada diálogo/formulario, una barra y
  la lista de lo que falta, que se actualiza al escribir.
- **Aviso de duplicados**: si el nombre ya existe (proveedor, material, obra,
  cuadrilla, usuario) avisa antes de guardar. En formularios de edición no
  avisa por el nombre del propio registro.
- **Contraseña**: medidor de fortaleza y comprobación de coincidencia.
- **Enfoque automático** en el primer campo vacío al abrir un diálogo.
- **Gráficos**: ajusta la altura de los gráficos Plotly al tamaño de la
  pantalla (HD, FHD, UHD), porque Plotly usa píxeles y el resto de la
  interfaz usa rem.

El script se instala una vez como <script> de la página principal; en cada
recarga solo se actualizan los datos (`__mrpExisting`)."""
from __future__ import annotations

import json

import streamlit as st

from db import repository as repo

VERSION = 1


def existing_names() -> dict[str, list[str]]:
    """Nombres ya registrados, por etiqueta de campo, para detectar duplicados."""
    def names(frame, column):
        return [str(v) for v in frame[column].dropna().tolist()] if not frame.empty else []

    try:
        return {
            "Nombre del proveedor": names(repo.list_suppliers(), "name"),
            "Nombre de la obra": names(repo.list_project_sites(), "name"),
            "Nombre de la cuadrilla": names(repo.list_work_groups(), "name"),
            "Nombre": names(repo.list_materials(), "name"),
            "Usuario": names(repo.list_users(), "username"),
        }
    except Exception:  # sin base de datos: simplemente no hay aviso de duplicados
        return {}


def inject(include_existing: bool = True) -> None:
    existing = existing_names() if include_existing else {}
    data = json.dumps(existing, ensure_ascii=False).replace("<", "\\u003c")
    script = json.dumps(_SCRIPT).replace("<", "\\u003c")
    loader = (
        "const P=window.parent;"
        f"P.__mrpExisting={data};"
        f"if(P.__mrpAssistVersion=={VERSION}){{if(P.__mrpAssistScan)P.__mrpAssistScan();}}"
        f"else{{const s=P.document.createElement('script');s.textContent={script};P.document.head.appendChild(s);}}"
    )
    st.iframe(f"<script>{loader}</script>", height=1, tab_index=-1)


_SCRIPT = r"""
(function(){
  const P=window,D=document;P.__mrpAssistVersion=%VERSION%;
  const norm=s=>String(s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/\s+/g,' ').trim();
  const isLogin=el=>!!el.closest('[data-testid="stHorizontalBlock"]:has(.mrp-lp-brand)');
  const hostOf=el=>el.closest('[data-testid="stTextInput"],[data-testid="stNumberInput"],[data-testid="stTextArea"]');
  const clean=l=>String(l).replace(/\s*\(.*?\)\s*/g,' ').trim();

  /* ---- progreso de campos obligatorios ---- */
  function progress(c){
    const rules=P.__mrpRules||{},fields=[];
    c.querySelectorAll('input[aria-label],textarea[aria-label]').forEach(el=>{
      const label=el.getAttribute('aria-label'),r=rules[label];
      if(!r||!r.required||label==='Usuario'||isLogin(el)||el.disabled)return;
      const host=hostOf(el),bad=host&&host.querySelector('.mrp-live[data-state="bad"]');
      const filled=el.value.trim().length>=(r.min||1)&&!bad;
      fields.push({label:clean(label),filled});
    });
    let panel=c.querySelector(':scope .mrp-formprogress');
    if(!fields.length){if(panel)panel.remove();return;}
    const done=fields.filter(f=>f.filled).length,total=fields.length,missing=fields.filter(f=>!f.filled).map(f=>f.label);
    const sig=done+'/'+total+'|'+missing.join(',');
    if(!panel){
      panel=D.createElement('div');panel.className='mrp-formprogress';
      const block=c.querySelector('[data-testid="stVerticalBlock"]')||c;block.insertBefore(panel,block.firstChild);
    }
    if(panel.__sig===sig)return;panel.__sig=sig;
    panel.dataset.done=done===total?'1':'0';
    panel.innerHTML='<div class="mrp-formprogress-row"><b>'+(done===total?'Todo listo para guardar':'Campos obligatorios')+'</b><small>'+done+' de '+total+'</small></div>'
      +'<div class="mrp-meter"><span style="width:'+Math.round(done/total*100)+'%"></span></div>'
      +(missing.length?'<div class="mrp-formprogress-missing">Falta: '+missing.join(', ')+'</div>':'');
  }

  /* ---- duplicados ---- */
  function duplicate(el){
    const label=el.getAttribute('aria-label'),list=(P.__mrpExisting||{})[label];
    if(!list||isLogin(el))return;
    const host=hostOf(el);if(!host)return;
    if(el.__mrpInit===undefined)el.__mrpInit=el.value;
    const value=norm(el.value);let note=host.querySelector(':scope > .mrp-dup');
    const hit=value&&value!==norm(el.__mrpInit)?list.find(n=>norm(n)===value):null;
    if(!hit){if(note)note.remove();return;}
    if(!note){note=D.createElement('div');note.className='mrp-dup';host.appendChild(note);}
    const msg='Ya existe «'+hit+'». '+(label==='Nombre'?'Si es otra categoría puedes continuar.':'Revisa antes de guardar para no duplicarlo.');
    if(note.textContent!==msg)note.textContent=msg;
  }

  /* ---- contraseñas ---- */
  function password(el){
    const label=el.getAttribute('aria-label');
    if(el.type!=='password'||(label!=='Contraseña'&&label!=='Repetir contraseña'))return;
    const form=el.closest('[data-testid="stForm"]')||el.closest('[role="dialog"]')||D;
    const repeat=[...form.querySelectorAll('input[type=password]')].find(i=>i.getAttribute('aria-label')==='Repetir contraseña');
    const host=el.closest('[data-testid="stTextInput"]');if(!host)return;
    if(label==='Contraseña'&&(!repeat&&isLogin(el)))return;
    if(label==='Contraseña'){
      let box=host.querySelector(':scope > .mrp-pwd');if(!box){box=D.createElement('div');box.className='mrp-pwd';box.innerHTML='<div class="mrp-pwd-bar"><span></span></div><em></em>';host.appendChild(box);}
      const v=el.value;let score=0;if(v.length>=8)score++;if(v.length>=12)score++;if(/[a-z]/.test(v)&&/[A-Z]/.test(v))score++;if(/\d/.test(v))score++;if(/[^A-Za-z0-9]/.test(v))score++;
      const valid=v.length>=8&&/[A-Za-z]/.test(v)&&/\d/.test(v);const level=!v?0:(!valid||score<=2)?1:score<=3?2:3;box.dataset.level=level;
      box.querySelector('span').style.width=[0,28,62,100][level]+'%';
      const text=['Escribe una contraseña de al menos 8 caracteres, con letras y números','Débil: usa al menos 8 caracteres con letras y números, y añade mayúsculas o símbolos','Media: puedes reforzarla con símbolos o más largo','Fuerte'][level];
      const em=box.querySelector('em');if(em.textContent!==text)em.textContent=text;
    }else{
      const first=[...form.querySelectorAll('input[type=password]')].find(i=>i.getAttribute('aria-label')==='Contraseña');
      let m=host.querySelector(':scope > .mrp-pwd-match');if(!m){m=D.createElement('div');m.className='mrp-pwd-match';host.appendChild(m);}
      if(!el.value){m.textContent='';m.dataset.state='';return;}
      const ok=first&&first.value===el.value;m.dataset.state=ok?'ok':'bad';m.textContent=ok?'✓ Las contraseñas coinciden':'✕ Todavía no coinciden';
    }
  }

  /* ---- gráficos Plotly: altura proporcional a la pantalla ---- */
  function charts(){
    const scale=Math.max(1,parseFloat(getComputedStyle(D.documentElement).fontSize)/16);
    let changed=false;
    D.querySelectorAll('.js-plotly-plot').forEach(el=>{
      const wrap=el.closest('[data-testid="stPlotlyChart"]')||el.parentElement;
      if(el.__mrpBase===undefined){el.__mrpBase=parseFloat(el.style.height)||el.offsetHeight||300;}
      const target=Math.round(el.__mrpBase*scale);
      if(Math.abs((parseFloat(el.style.height)||0)-target)>2){el.style.height=target+'px';if(wrap)wrap.style.minHeight=target+'px';changed=true;}
    });
    if(changed)setTimeout(()=>P.dispatchEvent(new Event('resize')),60);
  }

  /* ---- enfoque en diálogos nuevos ---- */
  function focusDialog(){
    const dlg=D.querySelector('[role="dialog"]');
    if(dlg&&!dlg.__mrpFocused){dlg.__mrpFocused=true;setTimeout(()=>{const i=dlg.querySelector('input[type=text]:not([disabled]),textarea:not([disabled])');if(i&&!i.value&&!D.activeElement.matches('input,textarea'))i.focus();},180);}
  }

  function scan(){
    D.querySelectorAll('input[aria-label],textarea[aria-label]').forEach(el=>{duplicate(el);password(el);});
    D.querySelectorAll('[role="dialog"],[data-testid="stForm"]').forEach(c=>{if(!(c.matches('[data-testid="stForm"]')&&c.closest('[role="dialog"]')))progress(c);});
    focusDialog();charts();
  }
  P.__mrpAssistScan=scan;
  D.addEventListener('input',()=>setTimeout(scan,30),true);D.addEventListener('focusout',()=>setTimeout(scan,30),true);
  P.addEventListener('resize',()=>{clearTimeout(P.__mrpChartT);P.__mrpChartT=setTimeout(charts,200);});
  let timer;new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(scan,120);}).observe(D.body,{childList:true,subtree:true});scan();
})();
""".replace("%VERSION%", str(VERSION))
