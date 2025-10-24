# app/main.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, posts, social, users, payments
from .config import settings

app = FastAPI(title=settings.APP_NAME)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://skeduluk-social.vercel.app"
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"], 
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(social.router)
app.include_router(payments.router)

@app.get("/")
async def root():
    return {"message": "Welcome to Skeduluk API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# --- CHANGE 4: Add block to run with `python -m app.main` ---
if __name__ == "__main__":
    print("Starting application...")
    print("Listening on http://localhost:8000")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)