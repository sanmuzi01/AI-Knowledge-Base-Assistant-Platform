from fastapi import APIRouter,Depends
from pydantic import BaseModel,Field
from service import auth_service
from models.init_db import get_db
from sqlalchemy.orm import Session
from service.dependencies import get_current_user
from models.init_db import User
from service.admin_service import current_user_payload
router = APIRouter(prefix="/user", tags=["用户功能"])

class LoginUser(BaseModel):
    name: str = Field(min_length=3, max_length=20)
    password:str= Field(min_length=6)
class RegisterUser(BaseModel):
    name: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=6)
    age: int = Field(ge=0, le=150)
#登录
@router.post("/login",summary="用户登录")
def login(user:LoginUser,db: Session = Depends(get_db)):
    result = auth_service.login(db, user.name, user.password)
    return result
#注册
@router.post("/register",summary="用户注册")
def register(user:RegisterUser, db: Session = Depends(get_db)):
    result = auth_service.register(db, user.name, user.password, user.age)
    return result
@router.get("/me", summary="查询当前登录用户信息")
def get_me(current_user: User = Depends(get_current_user)):
    return current_user_payload(current_user)
