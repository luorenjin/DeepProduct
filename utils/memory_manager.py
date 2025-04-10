"""
记忆管理工具 - 使用mem0提供长期记忆存储
"""
import os
import json
import yaml
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pathlib import Path

from mem0 import Memory

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    基于mem0的记忆管理器，为Agent提供长期记忆存储功能
    
    提供记忆的存储、检索、更新和遗忘等操作，支持记忆优先级管理和元数据记录
    """
    
    # 常见嵌入模型的维度映射表
    EMBEDDING_MODEL_DIMS_MAP = {
        # HuggingFace模型
        "BAAI/bge-small-zh-v1.5": 512,
        "BAAI/bge-base-zh-v1.5": 768,
        "BAAI/bge-large-zh-v1.5": 1024,
        "BAAI/bge-small-en-v1.5": 512,
        "BAAI/bge-base-en-v1.5": 768,
        "BAAI/bge-large-en-v1.5": 1024,
        # OpenAI模型
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
        # 其他常见模型
        "all-MiniLM-L6-v2": 384,
        "all-mpnet-base-v2": 768,
        "gte-large": 1024,
    }
    
    def __init__(self, agent_id: str = None, namespace: str = "memories"):
        """
        初始化记忆管理器
        
        Args:
            agent_id: Agent的唯一标识符，用于隔离不同Agent的记忆空间
            namespace: 记忆空间命名空间，默认为"memories"
        """

        # 获取配置信息并打印源信息
        memory_mode = self._get_config_value("MEMORY_MODE", default="memory")
        logger.info(f"内存模式配置值: {memory_mode}, 来源: {'环境变量' if os.environ.get('MEMORY_MODE') else '默认值'}")
        
        llm_provider = self._get_config_value("MEMORY_LLM_PROVIDER", default="qwen")
        logger.info(f"LLM提供商配置值: {llm_provider}, 来源: {'环境变量' if os.environ.get('MEMORY_LLM_PROVIDER') else '默认值'}")
        
        # 加载提供商配置
        provider_config = self._load_provider_config(llm_provider)
        if not provider_config:
            logger.warning(f"提供商 {llm_provider} 配置未找到，使用空配置")
            provider_config = {}
            
        # 从多个来源获取模型配置
        llm_model = self._get_config_value("MEMORY_LLM_MODEL", 
                                         provider_config.get("default_model", "qwen-turbo"))
        logger.info(f"使用的模型: {llm_model}, 提供商: {llm_provider}, 配置: {provider_config}")

        # 确保API密钥存在
        api_key = provider_config.get("api_key")
        if not api_key:
            # 尝试直接从环境变量获取
            api_key_env_var = provider_config.get("api_key", f"{llm_provider.upper()}_API_KEY")
            api_key = os.environ.get(api_key_env_var)
            if not api_key:
                logger.warning(f"未找到API密钥，请确保设置了{api_key_env_var}环境变量或在提供商配置中提供")
        
        # mem0支持的LLM提供商映射关系
        mem0_supported_providers = {
            "openrouter": "openai",    # openrouter 接口与 openai 兼容，映射为 openai
            "deepseek": "deepseek",    # 原生支持
            "doubao": "deepseek",      # doubao 接口与 openai 兼容，映射为 deepseek
            "openai": "openai",        # 原生支持
            "anthropic": "anthropic",  # 原生支持
            "gemini": "gemini",        # 原生支持
            "ollama": "ollama",        # 原生支持
            "qwen": "deepseek"         # qwen 接口与 openai 兼容，映射为 deepseek
        }
        
        # 确定 mem0 可用的提供商
        mem0_provider = mem0_supported_providers.get(llm_provider, "openai")
        logger.info(f"Using {mem0_provider} provider for mem0 (mapped from {llm_provider})")
        
        # 获取嵌入模型名称
        embedding_provider = os.environ.get("EMBEDDING_MODEL_PROVIDER", "huggingface")
        embedding_model = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
        
        # 根据嵌入模型名称获取正确的维度，如果在映射表中没找到，则使用环境变量 or默认值
        if embedding_model in self.EMBEDDING_MODEL_DIMS_MAP:
            embedding_dims = self.EMBEDDING_MODEL_DIMS_MAP[embedding_model]
            logger.info(f"Using predefined dimensions for {embedding_model}: {embedding_dims}")
        else:
            # 如果不在预定义列表中，使用环境变量 or默认值384
            embedding_dims = int(os.environ.get("EMBEDDING_MODEL_DIMS", 512))
            logger.warning(
                f"Model '{embedding_model}' not found in dimension map. "
                f"Using configured dimension: {embedding_dims}. "
                f"If retrieval errors occur, verify this matches the actual model output."
            )
        
        logger.info(f"Using embedding model: {embedding_model} with dimensions: {embedding_dims}")

        # 根据提供商类型构建基础配置
        config = {
            "llm": {
                "provider": mem0_provider,
                "config": {
                    "model": llm_model,
                    "temperature": provider_config["default_params"]["temperature"],
                    # 使用标准化的参数名称，不用动态生成参数名
                    "api_key": provider_config["api_key"],
                    f"{mem0_provider}_base_url": provider_config["api_base"],
                }
            },
            "embedder": {
                "provider": embedding_provider, 
                "config": {
                    "model": embedding_model,
                    "embedding_dims": embedding_dims
                }
            },
            "version": "v1.1"
        }

        # 为不同提供商配置正确的参数
        if memory_mode == "memory":
            logger.info("Using in-memory storage for testing")
            
            # 为内存模式提供基本配置
            config["vector_store"] = {
                "config": {
                    "collection_name": namespace,
                    "embedding_model_dims": embedding_dims,
                }
            }

            logger.info(f"In-memory storage initialized config: {config} ")
        elif memory_mode == "redis":
            logger.info("Using Redis for memory storage")
            # 从环境变量获取Redis配置
            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = int(os.environ.get("REDIS_PORT", 6379))
            redis_password = os.environ.get("REDIS_PASSWORD", None)
            redis_db = int(os.environ.get("REDIS_DB", 0))
            
            # 构建包含认证信息的Redis URL
            if (redis_password):
                redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
            else:
                redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"
                
            # 为Redis模式提供基本配置
            config["vector_store"] = {
                "provider": "redis",
                "config": {
                    "collection_name": namespace,
                    "embedding_model_dims": embedding_dims,
                    "redis_url": redis_url
                }
            }
            logger.info(f"Redis storage initialized config: {config} ")
        try:
            # 初始化mem0客户端
            self.client = Memory.from_config(config)
            
            self.agent_id = agent_id
            self._namespace = namespace
            logger.info(f"MemoryManager initialized for agent: {agent_id} in namespace: {namespace}")
        except Exception as e:
            logger.error(f"Failed to initialize MemoryManager: {str(e)}")
            raise
    
    def _get_config_value(self, key: str, default: Any = None, 
                         provider_config: Dict[str, Any] = None) -> Any:
        """
        按优先级从不同来源获取配置值
        
        优先级顺序：
        1. 环境变量
        2. 提供商配置（如果提供）
        3. 默认值
        
        Args:
            key: 配置键名
            default: 默认值
            provider_config: 提供商配置（可选）
            
        Returns:
            Any: 配置值
        """
        
        # 首先尝试从环境变量获取
        value = os.environ.get(key)
        if value is not None:
            return value
        
        # 其次尝试从提供商配置获取（如果提供）
        if provider_config and key.lower() in provider_config:
            return provider_config[key.lower()]
        # 最后返回默认值
        return default
    
    def _load_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """
        从配置文件中加载提供商配置
        
        Args:
            provider_name: 提供商名称
            
        Returns:
            Dict[str, Any]: 提供商配置
        """
        try:
            # 构建配置文件路径
            potential_paths = [
                # 相对路径 (相对于当前文件)
                Path(__file__).parent.parent / "config" / "model_providers.yaml",
                # 相对路径 (相对于工作目录)
                Path("config") / "model_providers.yaml",
                # 绝对路径 (基于环境变量)
                Path(os.environ.get("CONFIG_DIR", "")) / "model_providers.yaml",
            ]
            
            # 记录配置搜索过程
            logger.debug(f"正在搜索配置文件，搜索路径: {[str(p) for p in potential_paths]}")
            
            config_path = None
            for path in potential_paths:
                if path.exists():
                    config_path = path
                    break
                    
            if not config_path:
                logger.warning(f"未找到配置文件。尝试查找路径: {[str(p) for p in potential_paths]}")
                return {}
                
            logger.info(f"使用配置文件: {config_path}")
                
            # 读取YAML配置
            with open(config_path, "r", encoding="utf-8") as f:
                all_configs = yaml.safe_load(f)
                
            # 获取指定提供商的配置
            provider_config = all_configs.get("providers", {}).get(provider_name, {})
            
            # 处理环境变量替换
            for key, value in provider_config.items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    provider_config[key] = os.environ.get(env_var, "")
                    
            return provider_config
        except Exception as e:
            logger.error(f"加载提供商配置失败: {str(e)}")
            return {}
    
    async def save_memory(self, key: str, content: Any, priority: str = "normal", 
                         tags: List[str] = None,user_id: str = None, agent_id: str = None, run_id: str = None) -> bool:
        """
        将内容保存到长期记忆中
        
        Args:
            key: 记忆的唯一标识符
            content: 要存储的内容
            priority: 记忆优先级，可选值："high"、"normal"、"low"
            tags: 记忆的相关性标签列表
            user_id: 用户的唯一标识符，用于多用户系统
            agent_id: 指定的Agent ID，覆盖初始化时设置的agent_id
            run_id: 运行的唯一标识符，用于跟踪特定执行流程
            
        Returns:
            bool: 保存是否成功
        """
        # 验证优先级
        valid_priorities = ["high", "normal", "low"]
        if priority not in valid_priorities:
            logger.warning(f"Invalid priority: {priority}, using 'normal' instead")
            priority = "normal"
        
        # 确定使用的agent_id (方法参数优先)
        effective_agent_id = agent_id or self.agent_id
        
        # 准备元数据
        metadata = {
            "key": key,  # 存储原始键以便检索
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "access_count": 0
        }
        
        if tags:
            metadata["tags"] = tags
            
        try:
            # 将内容转换为mem0期望的消息格式
            if isinstance(content, list):
                # 检查是否为空列表或列表元素是否已经符合消息格式
                if not content:
                    messages = [{"role": "user", "content": ""}]
                elif isinstance(content[0], dict) and "role" in content[0] and "content" in content[0]:
                    messages = content
                else:
                    # 列表元素不符合消息格式，将整个列表作为内容
                    messages = [{"role": "user", "content": json.dumps(content)}]
            elif isinstance(content, dict):
                # 直接以JSON格式存储字典内容，而不是str()转换
                messages = [{"role": "user", "content": json.dumps(content)}]
            else:
                # 其他类型转为字符串
                messages = [{"role": "user", "content": str(content)}]
            
            # 调用mem0的add方法
            result = self.client.add(
                messages=messages,
                user_id=user_id,
                agent_id=effective_agent_id,
                run_id=run_id,
                metadata=metadata,
                infer=True
            )
            
            # 检查result是否为None
            if result is None:
                logger.warning(f"Memory add operation returned None for key: {key}")
                return False
                
            logger.debug(f"Memory saved with key: {key}, priority: {priority}, tags: {tags}, result: {result}")
            return True
        except Exception as e:
            logger.error(f"Failed to save memory with key {key}: {str(e)}")
            return False
            
    async def retrieve_memory(self, key: str, user_id: str = None, agent_id: str = None, run_id: str = None) -> Optional[Any]:
        """
        从长期记忆中检索内容
        
        Args:
            key: 记忆的唯一标识符
            user_id: 用户的唯一标识符，用于多用户系统
            agent_id: 指定的Agent ID，覆盖初始化时设置的agent_id
            run_id: 运行的唯一标识符，用于跟踪特定执行流程
            
        Returns:
            Optional[Any]: 检索到的内容，如果不存在则返回None
        """
        # 确定使用的agent_id (方法参数优先)
        effective_agent_id = agent_id or self.agent_id
        
        try:
            # 搜索具有特定key的记忆，修改查询方式通过metadata.key查询
            search_results = self.client.search(
                query="",  # 空查询用于精确匹配
                user_id=user_id,
                agent_id=effective_agent_id,
                run_id=run_id,
                limit=1000
            )
            
            # 检查是否有结果
            if not search_results or "results" not in search_results or not search_results["results"]:
                return None
                
            # 在应用层面过滤包含正确key的记忆
            matching_memory = None
            for memory in search_results["results"]:
                metadata = memory.get("metadata", {})
                if metadata.get("key") == key:
                    matching_memory = memory
                    break
                    
            if not matching_memory:
                return None
                
            # 返回内容
            content = memory.get("memory")
            
            # 尝试解析JSON(如果是JSON格式)
            try:
                return json.loads(content)
            except (json.JSONDecodeError, TypeError):
                return content
        except Exception as e:
            logger.error(f"Failed to retrieve memory with key {key}: {str(e)}")
            return None
            
    async def update_memory(self, key: str, content: Any, user_id: str = None, agent_id: str = None, run_id: str = None) -> bool:
        """
        更新长期记忆中的内容
        
        Args:
            key: 记忆的唯一标识符
            content: 要更新的内容
            update_metadata: 是否更新访问元数据
            user_id: 用户的唯一标识符，用于多用户系统
            agent_id: 指定的Agent ID，覆盖初始化时设置的agent_id
            run_id: 运行的唯一标识符，用于跟踪特定执行流程
            
        Returns:
            bool: 更新是否成功
        """
        # 确定使用的agent_id (方法参数优先)
        effective_agent_id = agent_id or self.agent_id
        
        try:
            # 首先查找具有此key的记忆
            search_results = self.client.search(
                query="",  # 空查询用于精确匹配
                user_id=user_id,
                agent_id=effective_agent_id,
                run_id=run_id,
                limit=1000
            )
            
            # 检查是否找到记忆
            if not search_results or "results" not in search_results or not search_results["results"]:
                logger.warning(f"Memory with key {key} does not exist, cannot update")
                return False
                
            # 在应用层面过滤包含正确key的记忆
            matching_memory = None
            for memory in search_results["results"]:
                metadata = memory.get("metadata", {})
                if metadata.get("key") == key:
                    matching_memory = memory
                    break
                    
            if not matching_memory:
                return None
                
            memory_id = matching_memory.get("id")
            
            # 序列化内容(如果需要)
            if not isinstance(content, (str, int, float, bool)):
                content = json.dumps(content,ensure_ascii=False)
                
            # 更新记忆,导致metadata被清空
            self.client.delete(memory_id)
            result = self.client.add(
                messages=[{"role": "user", "content": content}],
                user_id=user_id,
                agent_id=effective_agent_id,
                run_id=run_id,
                metadata=matching_memory.get("metadata", {}),  # 保留原有元数据
                infer=False
            )
            if result is None:
                logger.warning(f"Memory update operation returned None for key: {key}")
                return False
            logger.debug(f"Memory updated with key: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to update memory with key {key}: {str(e)}")
            return False
            
    async def forget_memory(self, key: str, 
                          user_id: str = None, agent_id: str = None, run_id: str = None) -> bool:
        """
        从长期记忆中删除内容
        
        Args:
            key: 记忆的唯一标识符
            user_id: 用户的唯一标识符，用于多用户系统
            agent_id: 指定的Agent ID，覆盖初始化时设置的agent_id
            run_id: 运行的唯一标识符，用于跟踪特定执行流程
            
        Returns:
            bool: 删除是否成功
        """
        # 确定使用的agent_id (方法参数优先)
        effective_agent_id = agent_id or self.agent_id
        
        try:
            # 查找具有此key的记忆
            search_results = self.client.search(
                query="",  # 空查询用于精确匹配
                user_id=user_id,
                agent_id=effective_agent_id,
                run_id=run_id,
                limit=1000
            )
            
            # 检查是否找到记忆
            if not search_results or "results" not in search_results or not search_results["results"]:
                logger.warning(f"Memory with key {key} does not exist, cannot delete")
                return False
                
            # 在应用层面过滤包含正确key的记忆
            matching_memory = None
            for memory in search_results["results"]:
                metadata = memory.get("metadata", {})
                if metadata.get("key") == key:
                    matching_memory = memory
                    break
                    
            if not matching_memory:
                return None
                
            memory_id = matching_memory.get("id")
            
            # 删除记忆
            self.client.delete(memory_id)
            
            logger.debug(f"Memory deleted with key: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory with key {key}: {str(e)}")
            return False
            
    async def list_memories(self, tag: str = None, priority: str = None,
                          user_id: str = None, agent_id: str = None, run_id: str = None) -> List[Dict[str, Any]]:
        """
        列出具有特定标签 or优先级的所有记忆
        
        Args:
            tag: 可选的标签过滤器
            priority: 可选的优先级过滤器("high", "normal", "low")
            user_id: 用户的唯一标识符，用于多用户系统
            agent_id: 指定的Agent ID，覆盖初始化时设置的agent_id
            run_id: 运行的唯一标识符，用于跟踪特定执行流程
            
        Returns:
            List[Dict[str, Any]]: 记忆列表
        """
        # 确定使用的agent_id (方法参数优先)
        effective_agent_id = agent_id or self.agent_id
        
        try:
            
            # 获取所有记忆 - 移除filters参数，只传递标准参数
            memories_response = self.client.get_all(
                user_id=user_id,
                agent_id=effective_agent_id,
                run_id=run_id
            )
            
            if not memories_response or "results" not in memories_response:
                return []
                
            memories = memories_response["results"]
            
            # 在内存中过滤tag和priority (因为mem0 API不支持这些过滤)
            if tag or priority:
                filtered_memories = []
                for memory in memories:
                    metadata = memory.get("metadata", {})
                    
                    # 检查标签匹配
                    if tag and "tags" in metadata:
                        if tag not in metadata["tags"]:
                            continue
                            
                    # 检查优先级匹配
                    if priority and "priority" in metadata:
                        if metadata["priority"] != priority:
                            continue
                            
                    filtered_memories.append(memory)
                
                memories = filtered_memories
            
            results = []
            for memory in memories:
                # 处理元数据
                metadata = memory.get("metadata", {})
                
                # 获取键值(如果在元数据中存储)
                display_key = metadata.get("key", memory.get("id", "unknown"))
                
                # 获取内容
                content = memory.get("memory")
                
                # 尝试解析内容为JSON
                try:
                    value = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    value = content
                    
                results.append({
                    "key": display_key,
                    "value": value,
                    "metadata": metadata
                })
                
            return results
        except Exception as e:
            logger.error(f"Failed to list memories: {str(e)}")
            return []
            
    async def search_memories(self, query: str,
                            user_id: str = None, agent_id: str = None, run_id: str = None) -> List[Dict[str, Any]]:
        """
        搜索记忆内容
        
        Args:
            query: 搜索查询字符串
            user_id: 用户的唯一标识符，用于多用户系统
            agent_id: 指定的Agent ID，覆盖初始化时设置的agent_id
            run_id: 运行的唯一标识符，用于跟踪特定执行流程
            
        Returns:
            List[Dict[str, Any]]: 匹配的记忆列表
        """
        # 确定使用的agent_id (方法参数优先)
        effective_agent_id = agent_id or self.agent_id
        
        try:
            # 使用向量搜索
            search_response = self.client.search(
                query=query,
                user_id=user_id,
                agent_id=effective_agent_id,
                run_id=run_id,
                limit=1000
            )
            
            if not search_response or "results" not in search_response:
                return []
                
            memories = search_response["results"]
            
            results = []
            for memory in memories:
                metadata = memory.get("metadata", {})
                
                # 获取键值(如果在元数据中存储)
                display_key = metadata.get("key", memory.get("id", "unknown"))
                
                # 获取内容
                content = memory.get("memory")
                
                # 尝试解析内容为JSON
                try:
                    value = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    value = content
                    
                results.append({
                    "key": display_key,
                    "value": value,
                    "metadata": metadata,
                    "score": memory.get("score")
                })
                    
            return results
        except Exception as e:
            logger.error(f"Failed to search memories: {str(e)}")
            return []
            
    async def clear_all_memories(self, confirm: bool = False,
                               user_id: str = None, agent_id: str = None, run_id: str = None) -> bool:
        """
        清除所有记忆(危险操作)
        
        Args:
            confirm: 确认操作，必须设为True才能执行
            user_id: 用户的唯一标识符，用于多用户系统
            agent_id: 指定的Agent ID，覆盖初始化时设置的agent_id
            run_id: 运行的唯一标识符，用于跟踪特定执行流程
            
        Returns:
            bool: 操作是否成功
        """
        if not confirm:
            logger.warning("Memory clear operation not confirmed")
            return False
            
        # 确定使用的agent_id (方法参数优先)
        effective_agent_id = agent_id or self.agent_id
        
        try:
            # 删除所有记忆
            self.client.delete_all(
                user_id=user_id,
                agent_id=effective_agent_id,
                run_id=run_id
            )
            
            logger.info(f"All memories cleared for agent: {effective_agent_id}, user: {user_id}, run: {run_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear memories: {str(e)}")
            return False
        