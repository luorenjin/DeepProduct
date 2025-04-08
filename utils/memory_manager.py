"""
记忆管理工具 - 使用mem0提供长期记忆存储
"""

import os
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from mem0.vector_stores.redis import RedisDB
from mem0 import Memory

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    基于mem0的记忆管理器，为Agent提供长期记忆存储功能
    
    提供记忆的存储、检索、更新和遗忘等操作，支持记忆优先级管理和元数据记录
    """
    
    def __init__(self, agent_id: str = None, namespace: str = "deepproduct"):
        """
        初始化记忆管理器
        
        Args:
            agent_id: Agent的唯一标识符，用于隔离不同Agent的记忆空间
            namespace: 记忆空间命名空间，默认为"deepproduct"
        """
        # 从环境变量获取Redis配置
        redis_host = os.environ.get("REDIS_HOST", "localhost")
        redis_port = int(os.environ.get("REDIS_PORT", 6379))
        redis_password = os.environ.get("REDIS_PASSWORD", None)
        redis_db = int(os.environ.get("REDIS_DB", 0))
        
        # 构建包含认证信息的Redis URL
        if redis_password:
            redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
        else:
            redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"
            
        try:
            # 初始化mem0 Redis向量存储
            self.vector_store = RedisDB(
                redis_url=redis_url,
                collection_name=namespace,
                embedding_model_dims=1536  # 默认使用OpenAI的嵌入维度
            )
            
            self.agent_id = agent_id
            self._namespace = namespace
            logger.info(f"MemoryManager initialized for agent: {agent_id} in namespace: {namespace}")
        except Exception as e:
            logger.error(f"Failed to initialize MemoryManager: {str(e)}")
            raise
    
    async def save_memory(self, key: str, content: Any, priority: str = "normal", 
                        tags: List[str] = None, ttl: int = None) -> bool:
        """
        将内容保存到长期记忆中
        
        Args:
            key: 记忆的唯一标识符
            content: 要存储的内容
            priority: 记忆优先级，可选值："high"、"normal"、"low"
            tags: 记忆的相关性标签列表
            ttl: 记忆的生存时间(秒)，如果不指定则永久保存
            
        Returns:
            bool: 保存是否成功
        """
        if not self.agent_id:
            full_key = key
        else:
            full_key = f"{self.agent_id}:{key}"
        
        # 验证优先级
        valid_priorities = ["high", "normal", "low"]
        if priority not in valid_priorities:
            logger.warning(f"Invalid priority: {priority}, using 'normal' instead")
            priority = "normal"
        
        # 准备元数据
        metadata = {
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "access_count": 0
        }
        
        if tags:
            metadata["tags"] = tags
            
        try:
            # 序列化内容(如果需要)
            if not isinstance(content, (str, int, float, bool)):
                content = json.dumps(content)
                
            # 创建Memory对象 - 使用正确的参数名content而不是text
            memory = Memory(
                content=str(content),  # 使用content参数名称
                metadata=metadata
            )
            # 手动设置ID
            memory.id = full_key
                
            # 保存到向量存储
            await self.vector_store.add(memory, ttl=ttl)
            logger.debug(f"Memory saved with key: {key}, priority: {priority}")
            return True
        except Exception as e:
            logger.error(f"Failed to save memory with key {key}: {str(e)}")
            return False
            
    async def retrieve_memory(self, key: str, update_metadata: bool = True) -> Optional[Any]:
        """
        从长期记忆中检索内容
        
        Args:
            key: 记忆的唯一标识符
            update_metadata: 是否更新访问元数据
            
        Returns:
            Optional[Any]: 检索到的内容，如果不存在则返回None
        """
        if not self.agent_id:
            full_key = key
        else:
            full_key = f"{self.agent_id}:{key}"
            
        try:
            # 从向量存储检索
            memory = await self.vector_store.get(full_key)
            
            if not memory:
                return None
                
            # 更新访问元数据
            if update_metadata:
                metadata = memory.metadata
                metadata["last_accessed"] = datetime.now().isoformat()
                metadata["access_count"] = metadata.get("access_count", 0) + 1
                
                memory.metadata = metadata
                await self.vector_store.update(memory)
                
            # 尝试将内容解析为JSON（如果是有效的JSON格式）
            # Memory类内容可能存储在content属性而不是text属性中
            content = memory.content if hasattr(memory, "content") else memory.text
            try:
                return json.loads(content)
            except:
                return content
        except Exception as e:
            logger.error(f"Failed to retrieve memory with key {key}: {str(e)}")
            return None
            
    async def update_memory(self, key: str, content: Any, 
                          update_metadata: bool = True) -> bool:
        """
        更新长期记忆中的内容
        
        Args:
            key: 记忆的唯一标识符
            content: 要更新的内容
            update_metadata: 是否更新访问元数据
            
        Returns:
            bool: 更新是否成功
        """
        if not self.agent_id:
            full_key = key
        else:
            full_key = f"{self.agent_id}:{key}"
            
        try:
            # 检查记忆是否存在
            existing_memory = await self.vector_store.get(full_key)
            
            if not existing_memory:
                logger.warning(f"Memory with key {key} does not exist, cannot update")
                return False
                
            # 序列化内容(如果需要)
            if not isinstance(content, (str, int, float, bool)):
                content = json.dumps(content)
                
            # 更新元数据
            metadata = existing_memory.metadata
            if update_metadata:
                metadata["last_accessed"] = datetime.now().isoformat()
                metadata["access_count"] = metadata.get("access_count", 0) + 1
                metadata["updated_at"] = datetime.now().isoformat()
            
            # 创建更新后的Memory对象 - 使用正确的参数名content而不是text
            updated_memory = Memory(
                content=str(content),  # 使用content参数名称
                metadata=metadata
            )
            # 手动设置ID
            updated_memory.id = full_key
                
            # 更新内容
            await self.vector_store.update(updated_memory)
            
            logger.debug(f"Memory updated with key: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to update memory with key {key}: {str(e)}")
            return False
            
    async def forget_memory(self, key: str) -> bool:
        """
        从长期记忆中删除内容
        
        Args:
            key: 记忆的唯一标识符
            
        Returns:
            bool: 删除是否成功
        """
        if not self.agent_id:
            full_key = key
        else:
            full_key = f"{self.agent_id}:{key}"
            
        try:
            # 从向量存储删除
            await self.vector_store.delete(full_key)
            logger.debug(f"Memory deleted with key: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory with key {key}: {str(e)}")
            return False
            
    async def list_memories(self, tag: str = None, 
                          priority: str = None) -> List[Dict[str, Any]]:
        """
        列出具有特定标签或优先级的所有记忆
        
        Args:
            tag: 可选的标签过滤器
            priority: 可选的优先级过滤器("high", "normal", "low")
            
        Returns:
            List[Dict[str, Any]]: 记忆列表
        """
        try:
            prefix = f"{self.agent_id}:" if self.agent_id else ""
            # 获取所有记忆 - 注意：RedisDB.list返回的是普通列表而不是嵌套列表
            memories = await self.vector_store.list(filters={})
            
            results = []
            for memory in memories:
                metadata = memory.metadata
                
                # 过滤标签
                if tag and tag not in metadata.get("tags", []):
                    continue
                    
                # 过滤优先级
                if priority and metadata.get("priority") != priority:
                    continue
                    
                # 移除前缀
                display_key = memory.id
                if self.agent_id and display_key.startswith(f"{self.agent_id}:"):
                    display_key = display_key[len(f"{self.agent_id}:"):]
                    
                # 尝试解析内容为JSON
                try:
                    value = json.loads(memory.text)
                except:
                    value = memory.text
                    
                results.append({
                    "key": display_key,
                    "value": value,
                    "metadata": metadata
                })
                
            return results
        except Exception as e:
            logger.error(f"Failed to list memories: {str(e)}")
            return []
            
    async def search_memories(self, query: str) -> List[Dict[str, Any]]:
        """
        搜索记忆内容
        
        Args:
            query: 搜索查询字符串
            
        Returns:
            List[Dict[str, Any]]: 匹配的记忆列表
        """
        try:
            prefix = f"{self.agent_id}:" if self.agent_id else ""
            # 使用向量搜索
            memories = await self.vector_store.search(
                query=query,
                limit=10,
                namespace=self._namespace,
                prefix=prefix
            )
            
            results = []
            for memory in memories:
                # 尝试解析内容为JSON
                try:
                    value = json.loads(memory.text)
                except:
                    value = memory.text
                
                # 移除前缀
                display_key = memory.id
                if self.agent_id and display_key.startswith(f"{self.agent_id}:"):
                    display_key = display_key[len(f"{self.agent_id}:"):]
                    
                results.append({
                    "key": display_key,
                    "value": value,
                    "metadata": memory.metadata,
                    "score": memory.score if hasattr(memory, "score") else None
                })
                    
            return results
        except Exception as e:
            logger.error(f"Failed to search memories: {str(e)}")
            return []
            
    async def clear_all_memories(self, confirm: bool = False) -> bool:
        """
        清除所有记忆(危险操作)
        
        Args:
            confirm: 确认操作，必须设为True才能执行
            
        Returns:
            bool: 操作是否成功
        """
        if not confirm:
            logger.warning("Memory clear operation not confirmed")
            return False
            
        try:
            prefix = f"{self.agent_id}:" if self.agent_id else ""
            
            # 获取所有记忆 - RedisDB.list返回普通列表
            memories = await self.vector_store.list(filters={})
            
            # 过滤出符合前缀的记忆
            prefix_memories = [mem for mem in memories if mem.id.startswith(prefix)]
            
            # 记录删除的数量
            deleted_count = 0
            
            # 逐一删除记忆
            for memory in prefix_memories:
                await self.vector_store.delete(memory.id)
                deleted_count += 1
                
            logger.info(f"Cleared {deleted_count} memories for agent: {self.agent_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear memories: {str(e)}")
            return False
