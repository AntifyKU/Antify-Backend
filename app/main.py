from app.api.routes import router
from fastapi import FastAPI

app = FastAPI(
    title="Antify Backend",
    version="0.1.0"
)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to Antify Backend API",
        "status": "running"
    }

app.include_router(router)