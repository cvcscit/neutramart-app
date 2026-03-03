from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.upload import router as upload_router
from app.routes.analyze import router as analyze_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/api")
app.include_router(analyze_router, prefix="/api")
