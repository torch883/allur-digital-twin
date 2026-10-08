import assert from 'node:assert/strict';
import {test} from 'node:test';
import {offlineResponse,offlineTick,offlineReset,offlineState} from '../../frontend/js/offline-data.js';

test('offline snapshot serves all pages and preserves case data',()=>{
  offlineReset();
  for(const path of ['/api/plant','/api/dashboard','/api/kpi','/api/downtime','/api/quality','/api/incidents','/api/recommendations','/api/forecast/downtime','/api/forecast/plan','/api/forecast/bottleneck','/api/stages/painting','/api/equipment/Камера-02'])assert.ok(offlineResponse(path));
  assert.equal(offlineResponse('/api/kpi').final_output,240);
  assert.equal(offlineResponse('/api/dashboard').monthly_plan.models_total,4800);
});
test('offline conveyor cascade and timeline',()=>{
  offlineReset();offlineResponse('/api/simulation',{method:'POST',body:{enabled:true,speed:20}});
  offlineResponse('/api/scenarios/conveyor_failure',{method:'POST'});
  for(let i=0;i<20;i++)offlineTick();
  const state=offlineState();assert.equal(state.stages.assembly.load_pct,0);assert.ok(state.stages.painting.load_pct<1);assert.ok(state.buffers.every(b=>b.qty>=0&&b.qty<=b.capacity));
  const timeline=offlineResponse('/api/timeline');assert.equal(timeline.available.length,20);assert.equal(timeline.available[0],'2026-10-03T12:20:00');
  offlineResponse('/api/scenarios/reset',{method:'POST'});assert.equal(offlineState().scenario,null);
});
test('offline supply depletion, filters, incident actions, zero payback',()=>{
  offlineResponse('/api/scenarios/supply_disruption',{method:'POST'});for(let i=0;i<20;i++)offlineTick();assert.equal(offlineState().stages.assembly.load_pct,0);
  const items=offlineResponse('/api/incidents?severity=critical&stage=welding').items;assert.ok(items.length);
  const ack=offlineResponse('/api/incidents/'+items[0].id+'/ack',{method:'POST'});assert.equal(ack.status,'ack');
  const impact=offlineResponse('/api/impact',{method:'POST',body:{downtime_reduction_pct:0,defect_reduction_pct:0}});assert.equal(impact.annual_savings,0);assert.equal(impact.payback_months,null);
});
