"""Read-only export of a running server to an embedded, offline JS snapshot."""
import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000'
def get(path):
    with urllib.request.urlopen(base+path,timeout=30) as response:return json.load(response)

plant=get('/api/plant')
paths=['/api/plant','/api/dashboard','/api/kpi','/api/downtime','/api/quality','/api/incidents','/api/recommendations','/api/forecast/downtime','/api/forecast/plan','/api/forecast/bottleneck','/api/simulation','/api/timeline']
paths.extend('/api/stages/'+s['code'] for s in plant['stages'])
paths.extend('/api/equipment/'+urllib.parse.quote(e['code']) for s in plant['stages'] for e in s['equipment'])
snapshot={urllib.parse.unquote(path):get(path) for path in paths}
out=Path(__file__).resolve().parent.parent/'frontend/js/offline-snapshot.js'
out.write_text('export const INITIAL = '+json.dumps(snapshot,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print(f'Exported {len(snapshot)} routes to {out}')
