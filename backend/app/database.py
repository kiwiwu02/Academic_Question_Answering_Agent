# backend/app/database.py
# 1. 导入核心依赖：引擎创建+会话工厂+模型基类
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

# 2. 创建数据库引擎
engine = create_engine(
    'sqlite:///./academic_agent.db', 
    connect_args={"check_same_thread": False}   # 关闭 SQLite 的线程检查，允许多线程共享同一个数据库连接，适配 FastAPI 的并发场景，不加必报错！
    )
# 3. 创建数据库会话工厂
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
    )

# 4. 封装：获取数据库会话的依赖函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 5. 封装：创建所有数据库表的函数
def create_tables():
    """
    创建所有数据库表
    可以多次调用此函数，只有在表不存在时才会创建表
    """
    Base.metadata.create_all(bind=engine)