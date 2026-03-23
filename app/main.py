"""Main application entry point"""
import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import socketio

from app.api import user as user_router
import socketio
from app.api import species as species_router
from app.api import collection as collection_router
from app.api import identification as identify_router
from app.api import feedback as feedback_router
from app.socketio_server import sio
from app.dependencies.auth import require_admin

# Create FastAPI app
app = FastAPI(
    title="Antify API",
    description="Backend API for Antify - Ant Species Identification App",
    docs_url="/docs",
    redoc_url="/redoc",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Antify API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# API prefix
BASE_URL = "/api"

# Public routers
app.include_router(user_router.router,        prefix=BASE_URL, tags=["User Management"])
app.include_router(species_router.router,     prefix=BASE_URL, tags=["Species"])
app.include_router(collection_router.router,  prefix=BASE_URL, tags=["Collections"])
app.include_router(identify_router.router,    prefix=BASE_URL, tags=["AI Identification"])
app.include_router(feedback_router.router,    prefix=BASE_URL, tags=["Feedback"])

# Admin-only routers (require_admin is enforced at the router level)
# so individual route functions need no dependency in their signatures.
app.include_router(
    user_router.admin_router,
    prefix=BASE_URL,
    tags=["User Management"],
    dependencies=[Depends(require_admin)],
)
app.include_router(
    species_router.admin_router,
    prefix=BASE_URL,
    tags=["Species"],
    dependencies=[Depends(require_admin)],
)
app.include_router(
    feedback_router.admin_router,
    prefix=BASE_URL,
    tags=["Feedback"],
    dependencies=[Depends(require_admin)],
)

# Create Socket.IO ASGI app and mount it
app = socketio.ASGIApp(sio, other_asgi_app=app)

# For running with uvicorn directly
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
