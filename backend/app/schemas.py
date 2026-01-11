# /backend/app/schemas.py
from pydantic import BaseModel,ConfigDict
from typing import Any, Dict, Optional,List
from datetime import datetime

# 消息基类
class MessageBase(BaseModel):
    # 配置允许从 ORM 模型创建 Pydantic 模型
    model_config = ConfigDict(from_attributes=True)
    role: str   # 'user','assistant','system','tool'
    content: str
    session_id: str
    tool_calls: Optional[str] = None
    tool_results: Optional[str] = None

# 消息创建请求
class MessageCreate(MessageBase):
    pass

# 消息响应模型
class MessageResponse(MessageBase):
    id: str
    created_at: datetime

# 会话基类
class SessionBase(BaseModel):
    # 配置允许从 ORM 模型创建 Pydantic 模型
    model_config = ConfigDict(from_attributes=True)
    title: Optional[str] = "New Chat Session"

# 会话创建请求
class SessionCreate(SessionBase):
    pass

# 会话响应模型
class SessionResponse(SessionBase):
    id: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []


# 会话更新请求
class SessionUpdate(BaseModel):
    title: Optional[str] = None

#聊天请求
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    stream: Optional[bool] = False

#聊天响应
class ChatResponse(BaseModel):
    session_id: str
    message: MessageResponse
    is_complete: bool = True

#流式聊天响应
class ChatStreamChunk(BaseModel):
    content: str
    is_final: bool = False
    tool_calls: Optional[List[Dict[str,Any]]] = None