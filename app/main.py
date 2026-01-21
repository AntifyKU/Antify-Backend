import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from app.api import user as user_router
from app.api import species as species_router
from app.api import collection as collection_router
from app.api import identify as identify_router
from app.api import news as news_router
from app.api import feedback as feedback_router
from app.socketio_server import sio

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

# Include all routers
app.include_router(user_router.router, prefix=BASE_URL, tags=["User Management"])
app.include_router(species_router.router, prefix=BASE_URL, tags=["Species"])
app.include_router(collection_router.router, prefix=BASE_URL, tags=["Collections"])
app.include_router(identify_router.router, prefix=BASE_URL, tags=["AI Identification"])
app.include_router(news_router.router, prefix=BASE_URL, tags=["News"])
app.include_router(feedback_router.router, prefix=BASE_URL, tags=["Feedback"])

# Create Socket.IO ASGI app and mount it
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


# For running with uvicorn directly
if __name__ == "__main__":
    uvicorn.run(
        "app.main:socket_app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
