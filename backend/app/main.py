from fastapi import FastAPI

from app.api.routes_ask import router as ask_router
from app.api.routes_auth import router as auth_router

app = FastAPI(title="Sentinel")

app.include_router(auth_router)
app.include_router(ask_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
