import {esc,fmt,empty} from './ui.js';
// Подписи — HTML (13 px при любой ширине), линии — SVG без масштабирования толщины.
// series: {key,label,color?,tone?:'fact'|'model'|'reference'}; opts.model — ключ флага синтетики в строке.
const TONE={fact:'var(--text)',model:'var(--blue)',reference:'var(--muted)'};
const niceStep=raw=>{const p=10**Math.floor(Math.log10(raw)),m=raw/p;return (m<=1?1:m<=2?2:m<=2.5?2.5:m<=5?5:10)*p;};
const xLabel=r=>r.date?`${r.date.slice(8,10)}.${r.date.slice(5,7)}`:String(r.label??'');
export function lineChart(rows,series,{threshold=null,height=190,labels=true,model=null,unit=''}={}){
  if(!rows?.length)return empty();
  const values=rows.flatMap(r=>series.map(s=>+r[s.key]||0));if(threshold!==null)values.push(threshold);
  const top=Math.max(1e-9,...values)*1.08,step=niceStep(top/3),max=step*Math.ceil(top/step),ticks=[];for(let k=0;k*step<=max+step/2;k++)ticks.push(k*step);
  const n=rows.length,X=i=>n<2?50:3+i*94/(n-1),Y=v=>100-v/max*100,digits=step<1?1:0,isModel=r=>!!(model&&r[model]),hasModel=rows.some(isModel);
  const color=s=>s.color||TONE[s.tone||'fact'],lineColor=(s,r)=>isModel(r)&&s.tone!=='reference'?TONE.model:color(s),multi=series.length>1;
  let svg=`<svg viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">`;
  for(const v of ticks)svg+=`<line class="chart-grid" x1="0" x2="1000" y1="${Y(v)}" y2="${Y(v)}"/>`;
  if(threshold!==null)svg+=`<line class="chart-threshold" x1="0" x2="1000" y1="${Y(threshold)}" y2="${Y(threshold)}"/>`;
  let dots='';
  for(const s of series){
    // Отрезки синтетики — синим (модель), кейс — цветом серии; граничная точка входит в оба отрезка.
    let run=[],stroke=null;const flush=()=>{if(run.length>1)svg+=`<polyline class="chart-line${s.tone==='reference'?' reference':''}" style="stroke:${stroke}" points="${run.join(' ')}"/>`;};
    rows.forEach((r,i)=>{const c=lineColor(s,r),pt=`${X(i)*10},${Y(+r[s.key]||0)}`;if(stroke!==null&&c!==stroke){flush();run=[run.at(-1)];}stroke=c;run.push(pt);});flush();
    rows.forEach((r,i)=>{const v=+r[s.key]||0,over=threshold!==null&&v>threshold&&s.tone!=='reference'&&!isModel(r);if(n<=14||over||i===n-1)dots+=`<i class="chart-dot${over?' over':''}" style="left:${X(i)}%;top:${Y(v)}%;--c:${over?'var(--bad)':lineColor(s,r)}"></i>`;});
  }
  svg+='</svg>';
  // Подписи у концов линий (≤4 серий), разведённые по высоте, чтобы не наезжали.
  let ends='';if(multi&&series.length<=4){const pos=series.map(s=>({s,y:Y(+rows[n-1][s.key]||0)/100*height})).sort((a,b)=>a.y-b.y);for(let i=1;i<pos.length;i++)pos[i].y=Math.max(pos[i].y,pos[i-1].y+18);ends=`<div class="chart-ends" aria-hidden="true">${pos.map(p=>`<span style="top:${p.y}px"><i style="background:${color(p.s)}"></i>${esc(p.s.label)}</span>`).join('')}</div>`;}
  const tips=rows.map(r=>({t:xLabel(r)+(isModel(r)?' · модель':''),v:series.map(s=>[s.label,fmt(r[s.key],1)+unit])}));
  let legend='';
  if(multi||hasModel||threshold!==null||series.some(s=>s.tone==='model')){legend='<div class="chart-legend">'+series.map(s=>`<span><i class="${s.tone==='reference'?'dashed':''}" style="${s.tone==='reference'?'':`background:${color(s)}`}"></i>${esc(s.label)}${hasModel&&s.tone!=='reference'?' · кейс':''}</span>`).join('');if(hasModel)legend+=`<span><i style="background:${TONE.model}"></i>Модель · синтетическая история</span>`;if(threshold!==null)legend+=`<span><i class="dashed"></i>Допуск ${fmt(threshold,threshold%1?1:0)}${unit||'%'}</span>`;legend+='</div>';}
  const name=series.map(s=>s.label).join(', ');
  let html=`<figure class="chart${ends?' has-ends':''}" style="--chart-h:${height}px">${legend}<div class="chart-frame"><div class="chart-y" aria-hidden="true">${ticks.map(v=>`<span style="top:${Y(v)}%">${fmt(v,digits)}</span>`).join('')}</div><div class="chart-plot" tabindex="0" role="img" aria-label="График: ${esc(name)}. Стрелки — по точкам, значения — в таблице ниже." data-tips="${esc(JSON.stringify(tips))}" data-xs="${esc(JSON.stringify(rows.map((_,i)=>X(i))))}">${svg}${dots}<span class="chart-cross" hidden></span><div class="chart-tip" hidden></div>${ends}</div>`;
  if(labels){const every=n>6?Math.ceil(n/5):1;html+=`<div class="chart-x" aria-hidden="true">${rows.map((r,i)=>(i%every||n-1-i<every/2)&&i!==n-1?'':`<span style="left:${X(i)}%">${esc(xLabel(r))}</span>`).join('')}</div>`;}
  html+=`</div><details class="chart-table"><summary>Таблица</summary><div class="table-scroll"><table><thead><tr><th></th>${series.map(s=>`<th>${esc(s.label)}</th>`).join('')}${hasModel?'<th>Источник</th>':''}</tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(xLabel(r))}</td>${series.map(s=>`<td>${fmt(r[s.key],1)}${unit}</td>`).join('')}${hasModel?`<td>${isModel(r)?'Модель':'Кейс'}</td>`:''}</tr>`).join('')}</tbody></table></div></details></figure>`;
  return html;
}
// Подсказка и перекрестие: мышь — ближайшая точка по X, клавиатура — стрелки на графике в фокусе.
function showTip(plot,i){const tips=JSON.parse(plot.dataset.tips),xs=JSON.parse(plot.dataset.xs);i=Math.max(0,Math.min(tips.length-1,i));plot.dataset.i=i;const tip=plot.querySelector('.chart-tip'),cross=plot.querySelector('.chart-cross');cross.hidden=tip.hidden=false;cross.style.left=xs[i]+'%';tip.replaceChildren();const h=document.createElement('strong');h.textContent=tips[i].t;tip.append(h);for(const [label,value] of tips[i].v){const row=document.createElement('div'),a=document.createElement('span'),b=document.createElement('b');a.textContent=label;b.textContent=value;row.append(a,b);tip.append(row);}const right=xs[i]>60;tip.style.left=right?'':`calc(${xs[i]}% + 12px)`;tip.style.right=right?`calc(${100-xs[i]}% + 12px)`:'';}
function hideTip(plot){plot.querySelector('.chart-tip').hidden=plot.querySelector('.chart-cross').hidden=true;delete plot.dataset.i;}
if(typeof document!=='undefined'){
  document.addEventListener('pointermove',e=>{const plot=e.target.closest?.('.chart-plot');document.querySelectorAll('.chart-plot[data-i]').forEach(p=>{if(p!==plot&&p!==document.activeElement)hideTip(p);});if(!plot)return;const xs=JSON.parse(plot.dataset.xs),box=plot.getBoundingClientRect(),pct=(e.clientX-box.left)/box.width*100;let best=0;xs.forEach((x,i)=>{if(Math.abs(x-pct)<Math.abs(xs[best]-pct))best=i;});showTip(plot,best);});
  document.addEventListener('focusin',e=>{if(e.target.matches?.('.chart-plot'))showTip(e.target,JSON.parse(e.target.dataset.xs).length-1);});
  document.addEventListener('focusout',e=>{if(e.target.matches?.('.chart-plot'))hideTip(e.target);});
  // capture: стрелки на графике не листают тур и участки
  document.addEventListener('keydown',e=>{const plot=e.target.closest?.('.chart-plot');if(!plot||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();e.stopPropagation();const last=JSON.parse(plot.dataset.xs).length-1,i=plot.dataset.i===undefined?last+(e.key==='ArrowRight'?-1:1):+plot.dataset.i;showTip(plot,e.key==='Home'?0:e.key==='End'?last:i+(e.key==='ArrowRight'?1:-1));},true);
}
export function bars(rows,key='minutes',label='reason',max=null){const m=max||Math.max(1,...rows.map(x=>x[key]));return rows.map(r=>`<div class="bar-row"><div><span>${esc(r[label])}</span><small>${fmt(r[key],1)}</small></div><div class="progress"><span style="width:${Math.max(0,Math.min(100,r[key]/m*100))}%"></span></div></div>`).join('')||empty();}
