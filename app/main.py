import asyncio
import logging
from contextlib import asynccontextmanager,suppress
from fastapi import FastAPI,Request,HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.config import ROOT
from app.db import Base,engine,SessionLocal
from app.seed.seed import seed
from app.services.rules_engine import evaluate_historical
from app.services.forecast_service import ForecastService
from app.services.simulator import Simulator
from app.routers import plant,kpi,downtime,quality,incidents,forecast,scenarios,impact,ws

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
log=logging.getLogger('allur')

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    app.state.hub=ws.Hub();app.state.forecast=ForecastService()
    app.state.simulator=Simulator(SessionLocal,app.state.forecast,app.state.hub)
    with SessionLocal() as db:
        seed(db);evaluate_historical(db);db.commit()
        app.state.forecast.train(db);app.state.simulator.start(db)
        app.state.forecast.refresh(db,app.state.simulator.state);db.commit()
    task=asyncio.create_task(app.state.simulator.run())
    log.info('Allur twin ready. Case data preserved; synthetic history clearly marked.')
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):await task

app=FastAPI(title='ALLUR · Цифровой двойник завода',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origin_regex=r'https?://(localhost|127\.0\.0\.1)(:\d+)?',allow_methods=['GET','POST'],allow_headers=['Content-Type'])

@app.exception_handler(HTTPException)
async def http_error(request:Request,exc:HTTPException):return JSONResponse(status_code=exc.status_code,content={'error':{'code':exc.status_code,'message':str(exc.detail)}})

@app.exception_handler(RequestValidationError)
async def validation_error(request:Request,exc:RequestValidationError):
    return JSONResponse(status_code=422,content={'error':{'code':422,'message':'Проверьте параметры запроса','details':[{'field':'.'.join(str(x) for x in e['loc']),'message':e['msg']} for e in exc.errors()]}})

@app.exception_handler(Exception)
async def unexpected_error(request:Request,exc:Exception):
    log.exception('Request failed: %s',request.url.path,exc_info=exc)
    return JSONResponse(status_code=500,content={'error':{'code':500,'message':'Внутренняя ошибка. Повторите запрос; подробности в журнале сервера.'}})

for module in [plant,kpi,downtime,quality,incidents,forecast,scenarios,impact,ws]:app.include_router(module.router)

@app.get('/api/health',tags=['Система'])
def health():
    with SessionLocal() as db:db.execute(text('SELECT 1'))
    return {'status':'ok','database':'connected','version':'1.0.0','mode':'demo'}

@app.get('/',include_in_schema=False)
def index():return FileResponse(ROOT/'frontend'/'index.html')

@app.get('/sw.js',include_in_schema=False)
def service_worker():return FileResponse(ROOT/'frontend'/'sw.js',media_type='application/javascript',headers={'Service-Worker-Allowed':'/','Cache-Control':'no-cache'})

app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')
