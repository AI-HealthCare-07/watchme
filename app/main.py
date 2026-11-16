from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Watchme", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(router)


@app.get("/healthz")
def healthz():
    return {"ok": True}
