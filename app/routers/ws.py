import asyncio
from fastapi import APIRouter,WebSocket,WebSocketDisconnect

class Hub:
    def __init__(self):self.clients=set()
    async def broadcast(self,type,payload):
        for ws in list(self.clients):
            try:await asyncio.wait_for(ws.send_json({'type':type,'payload':payload}),timeout=1)
            except Exception:self.clients.discard(ws)

router=APIRouter()

@router.websocket('/ws/live')
async def live(ws:WebSocket):
    await ws.accept();hub=ws.app.state.hub;hub.clients.add(ws)
    try:
        await ws.send_json({'type':'kpi_update','payload':ws.app.state.simulator.state})
        while True:
            try:await asyncio.wait_for(ws.receive_text(),timeout=15)
            except asyncio.TimeoutError:await ws.send_json({'type':'heartbeat','payload':{'at':ws.app.state.simulator.state['at']}})
    except (WebSocketDisconnect,RuntimeError):pass
    finally:hub.clients.discard(ws)
