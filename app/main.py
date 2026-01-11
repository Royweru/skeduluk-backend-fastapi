# app/main.py
from fastapi.staticfiles import StaticFiles
import uvicorn
from fastapi import FastAPI
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, posts, social, users, payments, templates
from .config import settings

app = FastAPI(title=settings.APP_NAME)

# Creates the uploads directory if it doesn't exist
Path("uploads").mkdir(exist_ok=True)

# Mount static files - this creates the /uploads endpoint
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Configure CORS - CRITICAL FIX
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://skeduluk-social.vercel.app", 
        "https://*.vercel.app", 
        "https://www.skeduluk.club"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Add this line
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(social.router)
app.include_router(payments.router)
app.include_router(templates.router)
@app.get("/")
async def root():
    return {"message": "Welcome to Skeduluk API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    print("Starting application...")
    print("Listening on http://localhost:8000")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)