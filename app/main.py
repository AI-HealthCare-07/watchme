from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Watchme", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"ok": True}
