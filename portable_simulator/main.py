import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — must be set before any other matplotlib import

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path
import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database and default users
    db.init_db()
    from auth_utils import hash_password
    if not db.get_user_by_username("reda"):
        db.create_user("reda", hash_password("taqinoreda"), role="admin")
    if not db.get_user_by_username("meryem"):
        db.create_user("meryem", hash_password("mertaq"), role="user")
    yield


app = FastAPI(title="TAQINOR Solar Quote Simulator", lifespan=lifespan)

# Mount static files
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
from routers import auth_router, catalog_router, devis_router, roi_router, autofill_router

app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(catalog_router.router, prefix="/api/catalog", tags=["catalog"])
app.include_router(devis_router.router, prefix="/api/devis", tags=["devis"])
app.include_router(roi_router.router, prefix="/api/roi", tags=["roi"])
app.include_router(autofill_router.router, prefix="/api/autofill", tags=["autofill"])


# Serve frontend
@app.get("/")
async def serve_index():
    index_file = Path("static/index.html")
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "TAQINOR Solar Quote Simulator API", "docs": "/docs"}


@app.get("/login")
async def serve_login():
    login_file = Path("static/login.html")
    if login_file.exists():
        return FileResponse(str(login_file))
    return {"message": "Login page not found"}


# Catch-all for SPA routing — must be last
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Skip API paths
    if full_path.startswith("api/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")
    static_file = Path("static") / full_path
    if static_file.exists() and static_file.is_file():
        return FileResponse(str(static_file))
    index_file = Path("static/index.html")
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Not found"}
