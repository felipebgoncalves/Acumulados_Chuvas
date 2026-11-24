"""API HTTP para a interface React."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api_service import DashboardCache
from app.config.settings import BASE_DIR

app = FastAPI(title="Acumulados de Chuva — Espírito Santo")
cache = DashboardCache()
app.mount("/assets", StaticFiles(directory=BASE_DIR / "img"), name="assets")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard():
    return cache.get()


@app.post("/api/refresh")
def refresh():
    return cache.get(force=True)
