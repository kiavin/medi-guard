from fastapi import FastAPI, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text  # <-- ADDED THIS FOR THE HEALTH CHECK
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Import your database dependency
from app.api.dependencies import get_db

# Import your modular routers (Removed 'ai' from the import list)
from app.api.routes import auth, patients, consultations, medications, users, laboratory, dashboard

# Initialize the FastAPI application
app = FastAPI(
    title="MediGuard AI-CDSS API",
    description="Backend API for Clinical Decision Support System",
    version="1.0.0"
)

# ==========================================
# CORS CONFIGURATION (Crucial for Vue 3)
# ==========================================
origins = [
    "http://localhost:3000",
    "http://localhost:5173", 
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

# ==========================================
# GLOBAL EXCEPTION HANDLERS
# ==========================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {}
    for error in exc.errors():
        field = str(error["loc"][-1]) if len(error["loc"]) > 0 else "unknown"
        errors[field] = error["msg"]
        
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"errorPayload": {"errors": errors}}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict):
        errors = exc.detail
    else:
        errors = {"general": str(exc.detail)}
        
    return JSONResponse(
        status_code=exc.status_code,
        content={"errorPayload": {"errors": errors}}
    )

# ==========================================
# MOUNT ROUTERS
# ==========================================
app.include_router(auth.router, prefix="/api")
app.include_router(patients.router, prefix="/api")
app.include_router(consultations.router, prefix="/api")
app.include_router(medications.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(laboratory.router, prefix="/api")
app.include_router(dashboard.router,  prefix="/api")
# NOTE: ai.router removed to prevent overlapping routes!

# ==========================================
# SYSTEM ENDPOINTS
# ==========================================

@app.get("/")
def read_root():
    return {"status": "online", "system": "MediGuard API Gateway"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        # Wrap raw SQL in text() to prevent SQLAlchemy 2.0 crashes
        db.execute(text("SELECT 1")) 
        return {"database_status": "connected"}
    except Exception as e:
        return {"database_status": "disconnected", "error": str(e)}