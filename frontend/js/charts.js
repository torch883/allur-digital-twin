import {esc,fmt,empty} from './ui.js';
export function lineChart(rows,series,{threshold=null,height=190,labels=true}={}){
  if(!rows?.length)return empty();
  const w=600,h=height,p={l:40,r:20,t:18,b:28},all=rows.flatMap(r=>series.map(s=>+r[s.key]||0));if(threshold!==null)all.push(threshold);
  const max=Math.max(1,...all)*1.15,x=i=>p.l+i*(w-p.l-p.r)/Math.max(1,rows.length-1),y=v=>h-p.b-v/max*(h-p.t-p.b);
  let out=`<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="График ${esc(series.map(s=>s.label).join(', '))}">`;
  for(let i=0;i<=3;i++){const v=max*i/3;out+=`<line class="chart-grid" x1="${p.l}" y1="${y(v)}" x2="${w-p.r}" y2="${y(v)}"/><text x="${p.l-9}" y="${y(v)+3}" text-anchor="end">${fmt(v,max<10?1:0)}</text>`;}
  if(threshold!==null)out+=`<line x1="${p.l}" x2="${w-p.r}" y1="${y(threshold)}" y2="${y(threshold)}" stroke="#f1bb55" stroke-dasharray="5 4"/><text x="${w-p.r}" y="${y(threshold)-5}" text-anchor="end">Допуск ${threshold}%</text>`;
  for(const s of series){out+=`<polyline fill="none" stroke="${s.color||'#ff3b30'}" stroke-width="2.5" points="${rows.map((r,i)=>`${x(i)},${y(+r[s.key]||0)}`).join(' ')}"/>`;rows.forEach((r,i)=>{out+=`<circle cx="${x(i)}" cy="${y(+r[s.key]||0)}" r="${rows.length<8?4:2}" fill="${s.color||'#ff3b30'}"><title>${esc(r.date||r.label)} · ${esc(s.label)}: ${fmt(r[s.key],1)}</title></circle>`;});}
  if(labels)rows.forEach((r,i)=>{if(rows.length>6&&i%Math.ceil(rows.length/5)&&i!==rows.length-1)return;out+=`<text x="${x(i)}" y="${h-6}" text-anchor="middle">${esc((r.date||r.label||'').slice(-5))}</text>`;});
  return out+'</svg>';
}
export function bars(rows,key='minutes',label='reason',max=null){const m=max||Math.max(1,...rows.map(x=>x[key]));return rows.map(r=>`<div class="bar-row"><div><span>${esc(r[label])}</span><small>${fmt(r[key],1)}</small></div><div class="progress"><span style="width:${Math.max(0,Math.min(100,r[key]/m*100))}%"></span></div></div>`).join('')||empty();}
