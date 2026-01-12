import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import user as user_router

app = FastAPI(
    title="Antify API",
    description="Backend API for Antify application",
    docs_url="/",
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
    return {"message": "Welcome to Antify API"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

BASE_URL = "/api"
app.include_router(user_router.router, prefix=BASE_URL, tags=["User Management"])
