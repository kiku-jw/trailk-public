import './karaoke.js';
import {choiceLabel} from './text-adapter.js';
// Presentation only: no provider calls, automatic choice, speech or transmission.
const $=id=>document.getElementById(id);let latest=null,chosen=null,lastEnglish=null,leadReading=false,displayed=null;
function syncChoice(){const value=$('english').value;if(value===lastEnglish)return;lastEnglish=value;const selected=!!value.trim();$('english').hidden=!selected;$('reply-lead').hidden=selected;renderMeaning();}
function renderMeaning(){const value=$('english').value;const pair=value?chosen:displayed;$('reply-choice-kind').textContent=pair?(value?'Вы выбрали: ':'Вариант: ')+choiceLabel(pair.kind):'Позицию выбираете вы';$('answer-meaning').textContent=pair?(value&&value!==pair.en?'Русский смысл исходного варианта: ':'')+pair.ru:'Смысл появится вместе с подсказкой.';}
window.calmSelectedReply=pair=>{chosen=pair;syncChoice();renderMeaning();window.dispatchEvent(new Event('selected-reply'));};
window.calmFocusBatch=(batch,buttons)=>{latest={batch,buttons};if(batch.options.some(pair=>pair.kind))$('alternatives').open=true;if($('english').value.trim()||(!leadReading&&document.activeElement!==$('reply-lead'))){displayed=batch.options[0];$('reply-lead').textContent=displayed.en;$('reply-lead').disabled=false;}if($('english').value.trim()||(!leadReading&&document.activeElement!==$('reply-lead')))$('reply-lead').onclick=()=>buttons[0]?.click();const active=document.activeElement;const reading=$('focus-options').contains(active);if(reading){$('alternatives').querySelector('summary').textContent='Другие варианты · появились новые';return;}$('alternatives').querySelector('summary').textContent='Другие варианты';const shelf=$('focus-options');shelf.replaceChildren();batch.options.forEach((pair,index)=>{const button=document.createElement('button');const label=document.createElement('small');label.className='choice-label';label.textContent=choiceLabel(pair.kind);const text=document.createElement('span');text.textContent=pair.en;button.append(label,text);button.setAttribute('aria-pressed','false');button.onclick=()=>{buttons[index]?.click();for(const other of shelf.children)other.setAttribute('aria-pressed',String(other===button));};shelf.append(button);});renderMeaning();};
$('reply-lead').addEventListener('pointerenter',()=>leadReading=true);$('reply-lead').addEventListener('pointerleave',()=>{leadReading=false;if(latest&&!$('english').value.trim()&&!latest.batch.stale)window.calmFocusBatch(latest.batch,latest.buttons);});
$('show-meaning').onclick=()=>{const open=$('show-meaning').getAttribute('aria-expanded')!=='true';$('show-meaning').setAttribute('aria-expanded',String(open));$('answer-meaning').hidden=!open;};
$('english').addEventListener('input',()=>{lastEnglish=null;syncChoice();});
const prefs=window.calmPreferences||{};const theme=['light','dark','system'].includes(prefs.theme)?prefs.theme:'dark';$('theme').value=theme;
function applyTheme(){const t=$('theme').value;if(t==='system')delete document.documentElement.dataset.theme;else document.documentElement.dataset.theme=t;}
$('theme').addEventListener('change',applyTheme);applyTheme();
window.calmFocusCaption=(text,count)=>{const caption=text||'Здесь появится перевод.';if($('focus-caption').textContent!==caption)$('focus-caption').textContent=caption;$('history-count').textContent=count?String(count):'';};
setInterval(syncChoice,150);syncChoice();

function centerViewport(){const box=document.querySelector('.camera-focus').getBoundingClientRect();const old=parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--viewport-center-offset'))||0;document.documentElement.style.setProperty('--viewport-center-offset',(old+innerWidth/2-box.left-box.width/2)+'px');}
window.addEventListener('resize',centerViewport);centerViewport();

for(const id of ['reply-lead','show-meaning'])$(id).addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&!e.repeat){e.preventDefault();$(id).click();}});

window.calmMark=(stage,detail={})=>{if(!window.calmMeasureLatency)return;const list=window.calmLatencyMarks||(window.calmLatencyMarks=[]);if(list.length<1000)list.push({stage,at_ms:performance.now(),...detail});};

window.calmFocusStale=()=>{latest=null;if(!$('english').value.trim()){if(!leadReading&&document.activeElement!==$('reply-lead'))$('reply-lead').textContent='Жду законченной реплики…';$('reply-lead').disabled=true;$('answer-meaning').textContent='Предыдущая подсказка устарела.';}for(const button of $('focus-options').children)button.disabled=true;};

$('reply-lead').addEventListener('blur',()=>{if(latest&&!$('english').value.trim()&&!latest.batch.stale)window.calmFocusBatch(latest.batch,latest.buttons);});
