from utils.timeutil import utcnow
from models.init_db import User
from typing import Optional, List
# 根据id查询
def get_user_by_id(db, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()
# 根据用户名查询
def get_user_by_name(db, name: str) -> Optional[User]:
    return db.query(User).filter(User.name == name).first()

# 根据手机号查询
def get_user_by_phone(db, phone: str) -> Optional[User]:
    return db.query(User).filter(User.phone == phone).first()

# 查询所有用户
def get_all_users(db) -> List[User]:
    return db.query(User).all()

# 创建用户
def create_user(db, name: str, password: str, age: int, phone: str = None) -> User:
    user = User(name=name,password=password,age=age,phone=phone)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# 修改用户密码：同时让这个用户此前签发的所有 token 一起失效（auth_version + 1）
def update_user_password(db, user: User, new_password: str) -> User:
    user.password = new_password
    user.auth_version = (getattr(user, "auth_version", 0) or 0) + 1
    user.password_changed_at = utcnow()
    db.commit()
    db.refresh(user)
    return user

# 删除用户
def delete_user(db, user: User) -> bool:
    db.delete(user)
    db.commit()
    return True

# 更新用户选中的智能体
def update_selected_agent(db, user: User, agent_id:Optional[int]) -> User:
    user.selected_agent_id = agent_id
    db.flush()
    return user
