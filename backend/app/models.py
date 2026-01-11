# backend/app/models.py
"""
SQLAlchemy ORM 数据库模型代码
包含了所有依赖导入 + UUID 工具函数 + 两个核心数据表模型：ChatSession 和 ChatMessage
一个聊天会话（ChatSession）能包含多条聊天消息（ChatMessage），多条消息一定属于某一个会话
"""

# 1. 导入所有依赖库
from sqlalchemy import Column, Integer, String, ForeignKey, Text, func
from sqlalchemy.types import DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import uuid

# 2. UUID生成工具函数
def generate_uuid():
    # 生成uuid4类型的UUID，转为字符串返回
    return str(uuid.uuid4())

# 3. 声明ORM基类
Base = declarative_base()

# ===================== 核心表1：聊天会话表 =====================
class ChatSession(Base):
    """定义chat_session表结构，存储用户的「聊天会话」数据"""
    __tablename__ = 'chat_sessions'

    id = Column(String(36), primary_key=True, index=True,default=generate_uuid)
    title = Column(String(255), nullable=False, default="New Chat Session")
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    # 定义与ChatMessage的关系：一个会话对应多条消息
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

# ===================== 核心表2：聊天消息表 =====================
class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id = Column(String(36), primary_key=True, index=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey('chat_sessions.id',ondelete="CASCADE"), nullable=False,index=True)       
    role = Column(String(50), nullable=False)  # 'user','assistant','system','tool'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    tool_calls=Column(Text, nullable=True)  # Text
    tool_results=Column(Text, nullable=True)  # Text

    session = relationship("ChatSession", back_populates="messages")