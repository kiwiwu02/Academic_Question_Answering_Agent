# backend/app/crud.py
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import ChatSession, ChatMessage
from app.schemas import SessionCreate, SessionUpdate, MessageCreate

# ===================== 会话相关 CRUD 操作 =====================
def create_session(db: Session, session_create: SessionCreate) -> ChatSession:
    """创建一个新的聊天会话"""
    # set default title if not provided
    title = session_create.title if session_create.title else "New Chat Session"
    db_session = ChatSession(title=title)

    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def get_session(db: Session, session_id: str) -> Optional[ChatSession]:
    """根据ID获取聊天会话"""
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()

def get_sessions(db: Session) -> List[ChatSession]:
    """获取所有聊天会话"""
    return db.query(ChatSession).order_by(ChatSession.created_at.desc()).all()


def update_session(db: Session, session_id: str, session_update: SessionUpdate) -> Optional[ChatSession]:
    """更新聊天会话的标题"""
    db_session = get_session(db, session_id)
    if db_session:
        # 过滤掉 None 值，只更新提供的字段
        update_dict = {k: v for k, v in session_update.dict().items() if v is not None}
        if update_dict:
            for key, value in update_dict.items():
                if hasattr(db_session, key):
                    setattr(db_session, key, value)
            db.commit()
            db.refresh(db_session)
    return db_session   

def delete_session(db: Session, session_id: str) -> bool:
    """删除聊天会话及其关联的消息"""
    db_session = get_session(db, session_id)
    if db_session:
        db.delete(db_session)
        db.commit()
        return True
    return False

# ===================== 消息相关 CRUD 操作 =====================
def create_message(db: Session, message_create: MessageCreate) -> ChatMessage:
    """创建一条新的聊天消息"""
    # 确保会话存在
    db_session = get_session(db, message_create.session_id)
    if not db_session:
        raise ValueError("会话不存在")
    
    db_message = ChatMessage(
        session_id=message_create.session_id,
        role=message_create.role,
        content=message_create.content,
        tool_calls=getattr(message_create, "tool_calls", None),
        tool_results=getattr(message_create, "tool_results", None),
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


def get_messages_by_session(db: Session, session_id: str) -> List[ChatMessage]:
    """根据会话ID获取所有关联的聊天消息"""
    return db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()

def get_message(db: Session, message_id: str) -> Optional[ChatMessage]:
    """根据ID获取单条聊天消息"""
    return db.query(ChatMessage).filter(ChatMessage.id == message_id).first()

def delete_messages_by_session(db: Session, session_id: str) -> int:
    """删除某个会话下的所有聊天消息，返回删除的消息数量"""
    deleted_count = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.commit()
    return deleted_count