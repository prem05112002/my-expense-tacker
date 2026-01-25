from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router

app = FastAPI(title="Expense Tracker API")

# --- CORS CONFIGURATION ---
# Allow the frontend to talk to the backend
origins = [
    "http://localhost:5173", # Vite (Default)
    "http://localhost:3000", # Create-React-App
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach the routes we created
app.include_router(router)

@app.get("/")
def read_root():
    return {"status": "✅ API is running"}