"""Ayuda inmediata al escribir, usando las mismas reglas que al guardar."""
import json
import streamlit as st
from modules.forms import RULES

def inject() -> None:
    rules = json.dumps(RULES, ensure_ascii=False).replace("<", "\\u003c")
    script = json.dumps(_SCRIPT).replace("<", "\\u003c")
    loader = ("const P=window.parent;" + f"P.__mrpRules={rules};" +
        "if(P.__mrpLiveVersion===2){P.__mrpScan();}else{" +
        f"const s=P.document.createElement('script');s.textContent={script};P.document.head.appendChild(s);}}")
    st.iframe(f"<script>{loader}</script>", height=1, tab_index=-1)

_SCRIPT = r"""
(function(){
  const P=window,D=document;P.__mrpLiveVersion=2;let noteId=0;
  function ruleFor(el){
    const label=el.getAttribute('aria-label');
    if(!label||el.closest('[data-baseweb="select"]')||el.type==='password'||el.disabled)return null;
    let r=P.__mrpRules[label];
    if(label==='Usuario'){
      const form=el.closest('[data-testid="stForm"]');
      const access=form?[...form.querySelectorAll('[data-testid="stCheckbox"]')].find(w=>w.textContent.includes('Dar acceso al sistema')):null;
      if(access&&!access.querySelector('input')?.checked)r={hint:'Opcional · se utilizará solo si marcas «Dar acceso al sistema»'};
    }
    if(label==='Usuario'&&el.closest('[data-testid="stForm"]')?.getAttribute('data-testid')==='stForm'&&el.closest('[data-testid="stHorizontalBlock"]')?.querySelector('.mrp-lp-brand')){
      const bootstrap=[...D.querySelectorAll('button')].some(b=>b.textContent.includes('Crear administrador'));
      if(!bootstrap)r={required:true,hint:'Usa el usuario que te asignó el administrador'};
    }
    if(!r)for(const prefix of ['Cantidad prevista','Recibido ahora'])if(label.startsWith(prefix))r=P.__mrpRules[prefix];
    if(el.type==='number'||el.getAttribute('inputmode')==='decimal'){
      const limits=Object.assign({},r?r.num:{});
      for(const attr of ['min','max']){const raw=el.getAttribute(attr);if(raw!==null&&raw!==''&&Number.isFinite(Number(raw)))limits[attr]=Number(raw);}
      return {num:limits,hint:r?r.hint:'',optional_number:r?r.optional_number:false};
    }
    return r;
  }
  function evaluate(value,r,touched){
    if(r.num){
      const lim=r.num,raw=String(value).trim(),n=Number(raw.replace(',','.'));
      const range=lim.gt0?'mayor que 0':lim.min!==undefined&&lim.max!==undefined?`entre ${lim.min} y ${lim.max}`:lim.min!==undefined?`mínimo ${lim.min}`:lim.max!==undefined?`máximo ${lim.max}`:'finito';
      if(!raw)return r.optional_number?{s:'idle',m:r.hint||'Opcional'}:{s:touched?'bad':'idle',m:touched?'Escribe una cantidad':`Número ${range}`};
      if(!Number.isFinite(n))return {s:'bad',m:'Escribe un número válido'};
      if(lim.gt0&&n<=0)return {s:'bad',m:'La cantidad debe ser mayor que 0'};
      if(lim.min!==undefined&&n<lim.min)return {s:'bad',m:`El mínimo permitido es ${lim.min}`};
      if(lim.max!==undefined&&n>lim.max)return {s:'bad',m:`El máximo permitido es ${lim.max}`};
      return {s:touched?'ok':'idle',m:touched?'Valor válido':(r.hint||`Número ${range}`)};
    }
    const text=value.trim(),len=[...text].length,count=[...value].length;
    const c=r.max?`${count}/${r.max} · quedan ${Math.max(0,r.max-count)}`:'';
    if(!text)return {s:r.required&&touched?'bad':'idle',m:r.required&&touched?'Completa este campo obligatorio':`${r.required?'Obligatorio':'Opcional'}${r.hint?' · '+r.hint:''}`,c};
    if(r.allowed){
      let re;try{re=new RegExp('^'+r.allowed+'$','u');}catch(err){return {s:'idle',m:r.hint||'Revisa este dato al guardar',c};}
      const bad=[...new Set([...text].filter(ch=>!re.test(ch)))];if(bad.length)return {s:'bad',m:`Caracteres no permitidos: ${bad.join(' ')}`,c};
    }
    if(r.min&&len<r.min)return {s:'bad',m:`Faltan ${r.min-len} caracteres; mínimo ${r.min}`,c};
    if(r.max&&len>r.max)return {s:'bad',m:`Superas el máximo de ${r.max} caracteres`,c};
    if(r.digits){const n=text.replace(/[^0-9]/g,'').length;if(n<r.digits[0]||n>r.digits[1])return {s:'bad',m:`Usa ${r.digits[0]}–${r.digits[1]} dígitos con código de país; tienes ${n}`,c};}
    if(r.pattern&&!new RegExp(r.pattern).test(text))return {s:'bad',m:r.pattern_msg,c};
    return {s:touched?'ok':'idle',m:touched?'Correcto':(r.hint||'Revisa el dato antes de guardar'),c};
  }
  function paint(el){
    const r=ruleFor(el);if(!r)return;
    const host=el.closest('[data-testid="stTextInput"],[data-testid="stNumberInput"],[data-testid="stTextArea"]');if(!host)return;
    let note=host.querySelector(':scope > .mrp-live');if(!note){note=D.createElement('div');note.className='mrp-live';note.id='mrp-live-'+(++noteId);host.appendChild(note);}
    const res=evaluate(el.value,r,!!el.__mrpTouched);if(note.dataset.state!==res.s)note.dataset.state=res.s;
    const msg=(res.s==='ok'?'✓ ':res.s==='bad'?'✕ ':'')+res.m;
    if(note.__message!==msg||note.__counter!==res.c){
      note.replaceChildren();const span=D.createElement('span');span.textContent=msg;note.appendChild(span);
      if(res.c){const count=D.createElement('span');count.className='mrp-live-count';count.textContent=res.c;note.appendChild(count);}note.__message=msg;note.__counter=res.c;
    }
    const described=(el.getAttribute('aria-describedby')||'').split(' ').filter(x=>x&&!x.startsWith('mrp-live-'));described.push(note.id);el.setAttribute('aria-describedby',described.join(' '));
    if(res.s==='bad')el.setAttribute('aria-invalid','true');else el.removeAttribute('aria-invalid');
    const box=el.closest('[data-baseweb="input"]')||el.closest('[data-baseweb="textarea"]');
    if(box){if(res.s==='idle'){box.style.removeProperty('border-color');box.style.removeProperty('box-shadow');}else{const color=`var(--mrp-${res.s==='ok'?'good':'bad'})`;box.style.setProperty('border-color',color,'important');box.style.setProperty('box-shadow',`0 0 0 1px ${color}`,'important');}}
  }
  function onEdit(e){if(e.target.matches&&e.target.matches('input,textarea')){e.target.__mrpTouched=true;paint(e.target);}}
  D.addEventListener('input',onEdit,true);D.addEventListener('focusout',onEdit,true);
  D.addEventListener('change',e=>{if(e.target.type==='checkbox')P.__mrpScan();},true);
  P.__mrpScan=()=>D.querySelectorAll('input[aria-label],textarea[aria-label]').forEach(paint);
  let timer;new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(P.__mrpScan,100);}).observe(D.body,{childList:true,subtree:true});P.__mrpScan();
})();
"""
