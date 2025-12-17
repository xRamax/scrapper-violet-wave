import logging
import asyncio
import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles 
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager
from pydantic import BaseModel 
from typing import Optional

# Imports de tus módulos
from app.routes import webhook
from app.scheduler.tasks import daily_outreach_job
from app.db import database, models
from app.routers import auth
from app.core import security

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Scheduler
scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler.add_job(daily_outreach_job, 'cron', hour=10, minute=0, id="daily_outreach")
    scheduler.start()
    logger.info("Scheduler started.")
    
    # Initialize DB models
    models.Base.metadata.create_all(bind=database.engine)
    
    yield
    # Shutdown
    scheduler.shutdown()
    logger.info("Scheduler shut down.")

# --- SEGURIDAD: Desactivamos los docs automáticos públicos ---
app = FastAPI(
    title="Violet Wave Dashboard", 
    lifespan=lifespan,
    docs_url=None,    # <--- Desactivado (Puerta cerrada)
    redoc_url=None,   # <--- Desactivado
    openapi_url=None  # <--- Desactivado
)

# --- MONTAR CARPETA STATIC ---
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- INCLUDE ROUTERS ---
app.include_router(webhook.router)
app.include_router(auth.router)

# --- MODELOS DE DATOS ---
class ScrapeRequest(BaseModel):
    apify_token: Optional[str] = None # <--- Campo del Token Apify
    city: str
    country: str
    niche: str          
    spreadsheet_id: str 
    limit: int = 10

# ==========================================
# 🛡️ SEGURIDAD PARA /DOCS (SWAGGER) - BLINDAJE
# ==========================================
security_docs = HTTPBasic()

def get_current_username_docs(credentials: HTTPBasicCredentials = Depends(security_docs)):
    """
    Verifica usuario y contraseña para entrar a la documentación.
    """
    # Credenciales Maestras para ver los DOCS (pueden ser las mismas de admin)
    correct_username = secrets.compare_digest(credentials.username, "admin@violetwave.com")
    correct_password = secrets.compare_digest(credentials.password, "RBPV2025vw!") # Tu nueva pass segura
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acceso Denegado",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Rutas manuales para docs protegidos
@app.get("/docs", include_in_schema=False)
async def get_swagger_documentation(username: str = Depends(get_current_username_docs)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Violet Wave API Docs")

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(username: str = Depends(get_current_username_docs)):
    return get_openapi(title="Violet Wave API", version="1.0.0", routes=app.routes)

# ==========================================
# 🚀 RUTAS PRINCIPALES DEL DASHBOARD
# ==========================================

@app.get("/")
def read_login():
    return FileResponse('static/login.html')

@app.get("/dashboard")
def read_dashboard():
    return FileResponse('static/dashboard.html')

# --- ENDPOINT PARA BUSCAR LEADS (PROTEGIDO JWT) ---
@app.post("/api/buscar-leads")
async def buscar_leads_google_maps(
    request: ScrapeRequest, 
    current_user: models.User = Depends(security.get_current_user)
):
    """
    DASHBOARD TOOL: Busca leads en Google Maps y llena el Excel indicado.
    Requiere autenticación JWT + Token Apify opcional.
    """
    from app.services.scraper_service import ScraperService
    
    logger.info(f"🔎 Buscando '{request.niche}' (User: {current_user.email})")
    
    scraper = ScraperService()
    
    # Pasamos el token del usuario (si lo puso) al servicio
    result = scraper.scrape_and_save(
        city=request.city, 
        country=request.country, 
        niche=request.niche,
        spreadsheet_id=request.spreadsheet_id,
        limit=request.limit,
        apify_token=request.apify_token
    )
    
    return result

# --- ENDPOINT DE PRUEBA MANUAL ---
@app.post("/test-manual")
async def test_manual_trigger(current_user: models.User = Depends(security.get_current_user)):
    logger.info(f">>> 🔴 INICIANDO PRUEBA MANUAL (User: {current_user.email}) <<<")
    try:
        if asyncio.iscoroutinefunction(daily_outreach_job):
            await daily_outreach_job()
        else:
            daily_outreach_job()
        return {"status": "success", "message": "Tarea ejecutada."}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)