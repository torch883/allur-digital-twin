export const $=(s,root=document)=>root.querySelector(s);
export const $$=(s,root=document)=>[...root.querySelectorAll(s)];
export const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const fmt=(n,d=0)=>n===null||n===undefined?'—':Number(n).toLocaleString('ru-RU',{maximumFractionDigits:d,minimumFractionDigits:d});
export const money=n=>fmt(n,0)+' ₸';
export const names={parts:'Склад комплектующих',welding:'Сварка',painting:'Окраска',assembly:'Сборка',quality:'Контроль качества',finished:'Готовая продукция'};
export const states={running:'Работает',normal:'Норма',warning:'Предупреждение',critical:'Критично',down:'Остановка',maintenance:'Плановое ТО',idle:'Ожидание',open:'Открыт',ack:'В работе',resolved:'Закрыт',info:'Информация'};
export const badge=(status,label)=>`<span class="badge ${esc(status)}">${esc(label||states[status]||status)}</span>`;
export const demo='<span class="badge demo">Демо-данные</span>';
export const aiNotice='<div class="notice info"><span>⌁</span><div>Демонстрационная модель на синтетической истории. В промышленной версии — обучение на потоковых данных MES/SCADA.</div></div>';
export const heading=(eyebrow,title,subtitle,right='')=>`<div class="page-heading"><div><p class="eyebrow"><em>ALLUR</em> / ${eyebrow}</p><h1>${title}</h1><p class="subtitle">${subtitle}</p></div>${right}</div>`;
export const kpi=(label,value,unit,note,symbol='',color='')=>`<div class="kpi-card"><div class="kpi-label">${label}<span class="kpi-symbol">${symbol}</span></div><div class="kpi-value ${color}">${value}<small>${unit}</small></div><div class="kpi-note">${note}</div></div>`;
export const panel=(title,body,extra='',className='')=>`<section class="panel ${className}"><div class="panel-header"><h2>${title}</h2>${extra}</div>${body}</section>`;
export const empty=text=>`<div class="empty">${esc(text||'За выбранный период данных нет')}</div>`;
export const loading=()=>'<div class="loading"><div class="spinner"></div>Загрузка данных…</div>';
export const error=e=>`<div class="error">${esc(e.message||e)}<br><button class="button small" data-retry>Повторить</button></div>`;
export function toast(text,stage){const el=document.createElement('div');el.className='toast';el.innerHTML=esc(text)+(stage?`<button class="button link" data-open-stage="${esc(stage)}">Показать на схеме →</button>`:'');$('#toasts').append(el);while($('#toasts').children.length>3)$('#toasts').firstChild.remove();setTimeout(()=>el.remove(),6500);}
export function openPanel(html){$('#detail-panel').innerHTML=html;$('#detail-panel').classList.remove('hidden');$('#panel-backdrop').classList.remove('hidden');$('#detail-panel').focus();}
export function closePanel(){$('#detail-panel').classList.add('hidden');$('#panel-backdrop').classList.add('hidden');document.dispatchEvent(new CustomEvent('panelclosed'));}
export const panelTop=title=>`<div class="detail-top"><h2>${esc(title)}</h2><button class="close" data-close-panel aria-label="Закрыть панель">×</button></div>`;
export const dateLabel=s=>new Date(s).toLocaleString('ru-RU',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
