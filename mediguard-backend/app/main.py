from fastapi import FastAPI, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
# Import your database dependency
from app.api.dependencies import get_db

# Import your modular routers
from app.api.routes import auth, patients, consultations, medications,ai, users

# Initialize the FastAPI application
app = FastAPI(
    title="MediGuard AI-CDSS API",
    description="Backend API for Clinical Decision Support System",
    version="1.0.0"
)

# ==========================================
# CORS CONFIGURATION (Crucial for Vue 3)
# ==========================================
# Since your Vue 3 frontend will likely run on a different port (e.g., localhost:3000)
# or domain, you must explicitly allow it to communicate with this FastAPI backend.
origins = [
    "http://localhost:3000",
    "http://localhost:5173", # Default Vite port (often used with Vue 3)
    "http://127.0.0.1:5173",
    # Add your production frontend domain here later
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows GET, POST, PUT, DELETE, etc.
    allow_headers=["*"], # Allows all headers (like Authorization for JWT)
)

# ==========================================
# GLOBAL EXCEPTION HANDLERS
# ==========================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Transforms Pydantic's default array of errors into your normalized field-based dictionary.
    Output: {"errorPayload": {"errors": {"password": "Password cannot be blank."}}}
    """
    errors = {}
    for error in exc.errors():
        # Grab the actual field name that failed (e.g., 'password', 'email')
        field = str(error["loc"][-1]) if len(error["loc"]) > 0 else "unknown"
        # Standardize the Pydantic error message
        errors[field] = error["msg"]
        
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"errorPayload": {"errors": errors}}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Transforms standard HTTP exceptions into the normalized format.
    If exc.detail is a dictionary, it maps to specific frontend fields.
    Otherwise, it defaults to the 'general' field.
    """
    # Check if the developer passed a dict (e.g., {"password": "Bad credentials"})
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
# This is where we attach our modules to the main app.
# The 'prefix' means all routes in auth.py will start with /api/auth
app.include_router(auth.router, prefix="/api")
app.include_router(patients.router, prefix="/api")
app.include_router(consultations.router, prefix="/api")
app.include_router(medications.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(users.router, prefix="/api")

# ==========================================
# SYSTEM ENDPOINTS
# ==========================================

@app.get("/")
def read_root():
    """Root endpoint to verify the API is reachable."""
    return {"status": "online", "system": "MediGuard API Gateway"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint to verify database connectivity."""
    try:
        db.execute("SELECT 1")
        return {"database_status": "connected"}
    except Exception as e:
        return {"database_status": "disconnected", "error": str(e)}