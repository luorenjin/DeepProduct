"""
MemoryManager单元测试
"""

import os
import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# 不直接导入依赖，而是使用模拟对象
# from mem0 import Memory
# from mem0.vector_stores.redis import RedisDB, MemoryResult

from utils.memory_manager import MemoryManager


# 创建模拟类以替代实际的导入 - 根据实际mem0的API调整
class MockMemory:
    def __init__(self, content=None, metadata=None):
        # 使用content参数而不是text
        self.id = None  # 这将在外部设置
        self.content = content  # 使用content存储内容
        self.text = content  # 为了兼容性保留text属性
        self.metadata = metadata or {}
        # 对于向量功能，添加空向量
        self.vector = []


class MockMemoryResult:
    def __init__(self, id=None, payload=None, score=None):
        self.id = id
        self.payload = payload or {}
        self.score = score
        # 解析payload中的data字段为text
        self.text = payload.get("data", "") if payload else ""
        self.metadata = {}
        # 添加完整的Memory接口所需属性
        self.vector = []


@pytest.fixture
def mock_redis_db():
    """创建一个模拟的RedisDB实例"""
    mock_db = AsyncMock()
    mock_db.add = AsyncMock(return_value=True)
    mock_db.get = AsyncMock()
    mock_db.update = AsyncMock()
    mock_db.delete = AsyncMock()
    mock_db.list = AsyncMock()
    mock_db.search = AsyncMock()
    return mock_db


@pytest.fixture
def memory_manager(mock_redis_db):
    """创建一个MemoryManager实例，使用模拟的RedisDB"""
    with patch('utils.memory_manager.RedisDB', return_value=mock_redis_db), \
         patch('utils.memory_manager.Memory') as mock_memory_class:
        # 配置Memory模拟以使用我们的MockMemory
        mock_instance = MockMemory()
        mock_memory_class.return_value = mock_instance
        
        # 当Memory被创建时，保存参数以便后续断言
        def side_effect(*args, **kwargs):
            mock_instance.content = kwargs.get('content', '')
            mock_instance.metadata = kwargs.get('metadata', {})
            # 手动设置ID (这在实际Memory类中由构造函数设置)
            if 'id' in kwargs:
                mock_instance.id = kwargs['id']
            return mock_instance
            
        mock_memory_class.side_effect = side_effect
        
        manager = MemoryManager(agent_id="test_agent", namespace="test_namespace")
        manager.vector_store = mock_redis_db
        return manager


class TestMemoryManager:
    """MemoryManager测试类"""

    @pytest.mark.asyncio
    async def test_init(self):
        """测试MemoryManager初始化"""
        with patch('utils.memory_manager.RedisDB') as mock_redis_class:
            # 设置环境变量
            os.environ["REDIS_HOST"] = "testhost"
            os.environ["REDIS_PORT"] = "6380"
            os.environ["REDIS_PASSWORD"] = "testpass"

            # 创建实例
            manager = MemoryManager(agent_id="test_agent", namespace="test_namespace")

            # 验证RedisDB初始化参数
            mock_redis_class.assert_called_once()
            args = mock_redis_class.call_args
            assert "redis://:testpass@testhost:6380" in args[1]["redis_url"]
            assert args[1]["collection_name"] == "test_namespace"
            assert args[1]["embedding_model_dims"] == 1536

            # 验证属性
            assert manager.agent_id == "test_agent"
            assert manager._namespace == "test_namespace"

    @pytest.mark.asyncio
    async def test_save_memory_success(self, memory_manager):
        """测试成功保存记忆"""
        # 模拟成功保存
        memory_manager.vector_store.add = AsyncMock(return_value=True)

        # 执行保存
        result = await memory_manager.save_memory(
            key="test_key",
            content={"test": "data"},
            priority="high",
            tags=["test", "memory"]
        )

        # 验证结果和调用
        assert result is True
        memory_manager.vector_store.add.assert_called_once()
        
        # 验证Memory创建时使用的参数
        call_args = memory_manager.vector_store.add.call_args
        memory_obj = call_args[0][0]
        assert memory_obj.text == '{"test": "data"}'
        assert memory_obj.metadata["priority"] == "high"
        assert memory_obj.metadata["tags"] == ["test", "memory"]

    @pytest.mark.asyncio
    async def test_save_memory_invalid_priority(self, memory_manager):
        """测试保存记忆时使用无效的优先级"""
        memory_manager.vector_store.add = AsyncMock(return_value=True)

        result = await memory_manager.save_memory(
            key="test_key",
            content="test data",
            priority="invalid"  # 无效的优先级
        )

        assert result is True
        
        # 验证使用了默认优先级
        call_args = memory_manager.vector_store.add.call_args
        memory_obj = call_args[0][0]
        assert memory_obj.metadata["priority"] == "normal"

    @pytest.mark.asyncio
    async def test_save_memory_failure(self, memory_manager):
        """测试保存记忆失败的情况"""
        # 模拟异常
        memory_manager.vector_store.add = AsyncMock(side_effect=Exception("Test error"))

        result = await memory_manager.save_memory(
            key="test_key",
            content="test data"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_retrieve_memory_success(self, memory_manager):
        """测试成功检索记忆"""
        # 创建一个模拟的内存结果
        mock_memory = MockMemory(
            content='{"test": "data"}',
            metadata={"priority": "high", "tags": ["test"]}
        )
        mock_memory.id = "test_agent:test_key"
        
        memory_manager.vector_store.get = AsyncMock(return_value=mock_memory)
        memory_manager.vector_store.update = AsyncMock()

        # 执行检索
        result = await memory_manager.retrieve_memory("test_key")

        # 验证结果 - 注意现在应该返回解析后的JSON对象
        assert result == {"test": "data"}
        memory_manager.vector_store.get.assert_called_once_with("test_agent:test_key")

    @pytest.mark.asyncio
    async def test_retrieve_memory_not_found(self, memory_manager):
        """测试检索不存在的记忆"""
        memory_manager.vector_store.get = AsyncMock(return_value=None)

        result = await memory_manager.retrieve_memory("non_existing_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_memory_success(self, memory_manager):
        """测试成功更新记忆"""
        # 模拟现有记忆
        mock_memory = MockMemory(
            content="old data",
            metadata={
                "priority": "normal", 
                "created_at": datetime.now().isoformat(),
                "access_count": 0
            }
        )
        mock_memory.id = "test_agent:test_key"
        
        memory_manager.vector_store.get = AsyncMock(return_value=mock_memory)
        memory_manager.vector_store.update = AsyncMock()

        # 执行更新
        result = await memory_manager.update_memory("test_key", "new data")

        # 验证结果
        assert result is True
        memory_manager.vector_store.update.assert_called_once()
        
        # 验证更新的内容
        call_args = memory_manager.vector_store.update.call_args
        updated_memory = call_args[0][0]
        assert updated_memory.text == "new data"
        assert "updated_at" in updated_memory.metadata

    @pytest.mark.asyncio
    async def test_forget_memory(self, memory_manager):
        """测试删除记忆"""
        memory_manager.vector_store.delete = AsyncMock()

        result = await memory_manager.forget_memory("test_key")

        assert result is True
        memory_manager.vector_store.delete.assert_called_once_with("test_agent:test_key")

    @pytest.mark.asyncio
    async def test_list_memories(self, memory_manager):
        """测试列出记忆"""
        # 创建模拟返回结果
        mock_memory = MockMemory(
            content='{"test": "data"}',
            metadata={"priority": "high", "tags": ["test"]}
        )
        mock_memory.id = "test_agent:test_key"

        # 修正返回值格式 - RedisDB.list返回的是单层列表
        memory_manager.vector_store.list = AsyncMock(return_value=[mock_memory])

        # 执行列出
        results = await memory_manager.list_memories()

        # 验证结果
        assert len(results) == 1
        assert results[0]["key"] == "test_key"
        assert results[0]["value"] == {"test": "data"}
        assert results[0]["metadata"]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_search_memories(self, memory_manager):
        """测试搜索记忆"""
        # 创建模拟搜索结果
        mock_memory = MockMemory(
            content='{"search": "result"}',
            metadata={"priority": "high"}
        )
        mock_memory.id = "test_agent:search_key"
        mock_memory.score = 0.95  # 添加得分属性

        memory_manager.vector_store.search = AsyncMock(return_value=[mock_memory])

        # 执行搜索
        results = await memory_manager.search_memories("search query")

        # 验证结果
        assert len(results) == 1
        assert results[0]["key"] == "search_key"
        assert results[0]["value"] == {"search": "result"}
        assert results[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_clear_all_memories_without_confirm(self, memory_manager):
        """测试没有确认的清除所有记忆"""
        result = await memory_manager.clear_all_memories(confirm=False)
        
        assert result is False
        # 此处不能直接检查.assert_not_called()，因为列表是动态属性
        assert not memory_manager.vector_store.list.called

    @pytest.mark.asyncio
    async def test_clear_all_memories_with_confirm(self, memory_manager):
        """测试确认后清除所有记忆"""
        # 创建模拟记忆列表
        mock_memory1 = MockMemory()
        mock_memory1.id = "test_agent:key1"
        mock_memory2 = MockMemory()
        mock_memory2.id = "test_agent:key2"
        mock_memory3 = MockMemory()
        mock_memory3.id = "other_agent:key3"
        
        # 修正返回值格式
        memory_manager.vector_store.list = AsyncMock(return_value=[mock_memory1, mock_memory2, mock_memory3])
        memory_manager.vector_store.delete = AsyncMock()

        # 执行清除
        result = await memory_manager.clear_all_memories(confirm=True)
        
        # 验证结果
        assert result is True
        # 验证只删除了前缀匹配的两个记忆
        assert memory_manager.vector_store.delete.call_count == 2


if __name__ == "__main__":
    pytest.main(["-xvs", "test_memory_manager.py"])
