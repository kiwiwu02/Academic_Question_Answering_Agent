# backend/app/services.py
from typing import Dict, List, Optional, Any,AsyncIterator
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage,ToolMessage
from langchain_community.agent_toolkits.load_tools import load_tools
import logging
import json
from .config import settings


logger = logging.getLogger(__name__)

class AcademicResearchAgentService:
    """学术研究助手Agent 服务"""

    def __init__(self):
        self.agent = None
        self._initialize_agent()

    def _initialize_agent(self):
        """初始化学术研究助手Agent"""
        try:
            # 1.初始化聊天模型
            chat_model = init_chat_model(
                model=settings.BAI_LIAN_MODEL,
                model_provider="openai",
                api_key=settings.BAI_LIAN_API_KEY,
                base_url=settings.BAI_LIAN_BASE_URL,
                temperature=settings.agent_temperature,
                max_tokens=settings.agent_max_tokens,
            )
            # 2.加载学术工具
            tools = load_tools(
                ["arxiv"],
                llm=chat_model
                )
            # 3.创建Agent
            system_prompt = """你是一个专业的研究助手，专门帮助用户查找、理解和总结学术论文。
            你可以使用以下工具：
            1. arxiv - 在arXiv上搜索和获取学术论文
            
            请按照以下步骤帮助用户：
            1. 理解用户的研究需求
            2. 使用合适的工具搜索相关论文
            3. 提供论文的关键信息：标题、作者、摘要、关键贡献
            4. 如果用户要求，可以提供论文的详细总结
            5. 保持回答专业、准确、有用
            
            **重要提示**：
            - 优先搜索最近2-3年的论文
            - 使用具体的搜索词，避免过于宽泛的查询
            - 最多搜索2-3次，避免过多API调用
            
            记住：始终用中文回答，除非用户特别要求使用其他语言。
            """
            self.agent = create_agent(
                model=chat_model,
                tools=tools,
                system_prompt=system_prompt
                )
                        
            logger.info("Agent初始化成功")
            
        except Exception as e:
            logger.error(f"Agent初始化失败: {e}")
            raise

    async def process_message(self, message: str, history: List[Dict] = None) -> Dict[str, Any]:
        """处理用户消息（非流式）"""
        try:
            if not self.agent:
                self._initialize_agent()
            
            # 准备消息历史
            langchain_messages = []
            if history:
                for msg in history:
                    if msg["role"] == "user":
                        langchain_messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        langchain_messages.append(AIMessage(content=msg["content"]))
                    elif msg["role"] == "tool" and msg.get("content"):
                        langchain_messages.append(ToolMessage(
                            content=msg["content"],
                            tool_call_id=msg.get("tool_call_id", "")
                        ))
            
            # 添加当前消息
            langchain_messages.append(HumanMessage(content=message))
            
            # 调用Agent（非流式）
            input_data = {"messages": langchain_messages}
            result = self.agent.invoke(input_data)
            
            # 提取最后一条消息内容
            messages = result.get("messages", [])
            last_message = messages[-1] if messages else None
            content = last_message.content if hasattr(last_message, 'content') else ""
            
            # 提取工具调用信息
            tool_calls = []
            tool_results = {}
            
            for msg in messages:
                if isinstance(msg, AIMessage):
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            tool_info = {
                                "name": tool_call.get('name', ''),
                                "args": tool_call.get('args', {}),
                                "id": tool_call.get('id', '')
                            }
                            tool_calls.append(tool_info)
                
                elif isinstance(msg, ToolMessage):
                    tool_results[msg.tool_call_id] = msg.content
            
            # 将tool_calls和tool_results转换为字符串存储
            tool_calls_str = json.dumps(tool_calls) if tool_calls else None
            tool_results_str = json.dumps(tool_results) if tool_results else None
            
            return {
                "content": content,
                "tool_calls": tool_calls_str,
                "tool_results": tool_results_str
            }
                
        except Exception as e:
            logger.error(f"处理消息失败: {e}", exc_info=True)
            return {"content": f"处理消息时出错: {str(e)}", "tool_calls": None, "tool_results": None}
    
    async def process_stream(self, message: str, history: List[Dict] = None):
        """真正的流式处理用户消息"""
        try:
            if not self.agent:
                self._initialize_agent()
            
            # 准备消息历史
            langchain_messages = []
            if history:
                for msg in history:
                    if msg["role"] == "user":
                        langchain_messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        langchain_messages.append(AIMessage(content=msg["content"]))
                    elif msg["role"] == "tool" and msg.get("content"):
                        langchain_messages.append(ToolMessage(
                            content=msg["content"],
                            tool_call_id=msg.get("tool_call_id", "")
                        ))
            
            # 添加当前消息
            langchain_messages.append(HumanMessage(content=message))
            
            logger.info(f"开始真正的流式处理，消息: {message[:100]}...")
            
            # 转换消息格式
            input_messages = []
            for msg in langchain_messages:
                if isinstance(msg, HumanMessage):
                    input_messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    input_messages.append({"role": "assistant", "content": msg.content})
                elif isinstance(msg, ToolMessage):
                    input_messages.append({"role": "tool", "content": msg.content, "tool_call_id": msg.tool_call_id})
            
            logger.info(f"输入消息数量: {len(input_messages)}")
            
            # 使用 agent.stream() 实现真正的流式
            # 参考您提供的代码：for chunk in agent.stream(... , stream_mode="messages")
            full_content = ""
            accumulated_tool_calls = []
            
            try:
                # 这里的关键：使用 stream_mode="messages"
                for chunk in self.agent.stream(
                    {"messages": input_messages},
                    stream_mode="messages"  # token by token
                ):
                    # chunk 是一个元组 (message_chunk, metadata)
                    if chunk and len(chunk) > 0:
                        message_chunk = chunk[0]
                        
                        # 记录chunk类型用于调试
                        chunk_type = type(message_chunk).__name__
                        
                        # 检查是否是 AIMessageChunk
                        if hasattr(message_chunk, 'content'):
                            chunk_content = message_chunk.content or ""
                            if chunk_content:
                                full_content += chunk_content
                                logger.debug(f"流式chunk内容: {chunk_content}")
                                
                                # 发送内容块
                                yield {
                                    "content": chunk_content,
                                    "is_final": False,
                                    "tool_calls": None
                                }
                        
                        # 提取工具调用信息（如果有）
                        if hasattr(message_chunk, 'tool_calls') and message_chunk.tool_calls:
                            for tool_call in message_chunk.tool_calls:
                                tool_info = {
                                    "name": tool_call.get('name', ''),
                                    "args": tool_call.get('args', {}),
                                    "id": tool_call.get('id', '')
                                }
                                accumulated_tool_calls.append(tool_info)
                                logger.info(f"流式工具调用: {tool_info}")
            
            except StopIteration:
                # 流式自然结束
                logger.info("流式处理自然结束")
                pass
            
            except Exception as e:
                logger.error(f"流式处理过程中出错: {e}", exc_info=True)
                raise
            
            # 发送最终消息
            logger.info(f"流式处理完成，总内容长度: {len(full_content)}")
            yield {
                "content": "",
                "is_final": True,
                "tool_calls": accumulated_tool_calls if accumulated_tool_calls else None
            }
            
        except Exception as e:
            logger.error(f"流式处理失败: {e}", exc_info=True)
            yield {
                "content": f"错误: {str(e)}",
                "is_final": True,
                "tool_calls": None
            }

# 创建全局Agent实例
agent_service = AcademicResearchAgentService()