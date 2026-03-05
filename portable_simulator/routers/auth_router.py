from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
import db
import auth_utils

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------- Pydantic schemas ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class RoleUpdateRequest(BaseModel):
    role: str


# ---------- Dependencies ----------
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = auth_utils.decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = db.get_user_by_id(int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


# ---------- Endpoints ----------
@router.post("/login")
async def login(body: LoginRequest):
    user = db.get_user_by_username(body.username)
    if not user or not auth_utils.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = auth_utils.create_access_token({"sub": str(user["id"]), "username": user["username"], "role": user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "username": user["username"], "role": user["role"]},
    }


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, admin: dict = Depends(require_admin)):
    try:
        hashed = auth_utils.hash_password(body.password)
        user = db.create_user(body.username, hashed, body.role)
        return {"id": user["id"], "username": user["username"], "role": user["role"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {"id": current_user["id"], "username": current_user["username"], "role": current_user["role"]}


@router.get("/users")
async def list_users(admin: dict = Depends(require_admin)):
    return db.get_all_users()


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    if admin["id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    deleted = db.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")


@router.put("/users/{user_id}/role")
async def update_role(user_id: int, body: RoleUpdateRequest, admin: dict = Depends(require_admin)):
    updated = db.update_user_role(user_id, body.role)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return updated
