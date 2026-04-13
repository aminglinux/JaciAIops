from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from jose import jwt
import bcrypt
import json

from app.core.database import get_db, User
from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    is_admin: bool = False

class UserResponse(BaseModel):
    userId: int
    username: str
    email: str
    avatar: Optional[str] = None
    roles: List[str]
    permissions: List[str]
    scope: List[str]
    isAdmin: bool
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[dict] = None

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def verify_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except Exception:
        return None

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=401, detail="账户已被禁用")
    return user

def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user

def user_to_response(user: User) -> UserResponse:
    roles = json.loads(user.roles) if user.roles else ["user"]
    permissions = json.loads(user.permissions) if user.permissions else []
    scope = json.loads(user.scope) if user.scope else []
    
    default_permissions = []
    if user.is_admin:
        default_permissions = [
            "logs:view", "logs:edit", "logs:delete",
            "diagnose:view", "diagnose:execute",
            "knowledge:view", "knowledge:edit",
            "qa:view",
            "users:manage"
        ]
    else:
        default_permissions = [
            "logs:view", "diagnose:view", "knowledge:view", "qa:view"
        ]
    
    all_permissions = list(set(default_permissions + permissions))
    
    return UserResponse(
        userId=user.id,
        username=user.username,
        email=user.email,
        roles=roles,
        permissions=all_permissions,
        scope=scope,
        isAdmin=user.is_admin
    )

@router.post("/register", response_model=dict)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        is_admin=user_data.is_admin,
        roles=json.dumps(["admin"] if user_data.is_admin else ["user"]),
        permissions=json.dumps([]),
        scope=json.dumps([])
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return {
        "code": 200,
        "message": "注册成功",
        "data": user_to_response(user).model_dump()
    }

@router.post("/login", response_model=dict)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="密码错误")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="账户已被禁用")
    
    access_token = create_access_token(data={"sub": user.username})
    
    return {
        "code": 200,
        "message": "登录成功",
        "data": {
            "token": access_token,
            "user": user_to_response(user).model_dump()
        }
    }

@router.get("/me", response_model=dict)
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "code": 200,
        "message": "success",
        "data": user_to_response(current_user).model_dump()
    }

@router.post("/logout", response_model=dict)
def logout():
    return {
        "code": 200,
        "message": "退出成功",
        "data": None
    }

@router.get("/users", response_model=dict)
def list_users(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return {
        "code": 200,
        "message": "success",
        "data": [user_to_response(u).model_dump() for u in users]
    }

@router.delete("/users/{user_id}", response_model=dict)
def delete_user(user_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="不能删除管理员账户")
    db.delete(user)
    db.commit()
    return {
        "code": 200,
        "message": "删除成功",
        "data": None
    }

def create_default_users():
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            admin = User(
                username="admin",
                email="admin@aiops.com",
                hashed_password=hash_password("admin123"),
                is_admin=True,
                roles=json.dumps(["admin"]),
                permissions=json.dumps([]),
                scope=json.dumps(["System-A", "System-B", "System-C"])
            )
            db.add(admin)
            print("默认管理员创建成功: admin / admin123")
        
        if not db.query(User).filter(User.username == "user").first():
            user = User(
                username="user",
                email="user@aiops.com",
                hashed_password=hash_password("user123"),
                is_admin=False,
                roles=json.dumps(["user"]),
                permissions=json.dumps([]),
                scope=json.dumps(["System-A"])
            )
            db.add(user)
            print("默认用户创建成功: user / user123")
        
        db.commit()
    finally:
        db.close()
