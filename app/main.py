from fastapi import FastAPI

app = FastAPI(title="Watchme")


@app.get("/healthz")
def healthz():
    return {"ok": True}
