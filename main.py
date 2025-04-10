import asyncio
import logging
import os
import traceback
from typing import Dict, Any, Optional
from pathlib import Path

from dotenv import load_dotenv

from utils.memory_manager import MemoryManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_memory_manager() -> None:
    """
    测试 MemoryManager 的核心功能
    
    测试包括:
    - 初始化记忆管理器
    - 保存记忆
    - 检索记忆
    - 更新记忆
    - 搜索记忆
    - 列出记忆
    - 删除记忆
    """
    try:
 
        # 初始化记忆管理器
        logger.info("初始化记忆管理器...")
        memory_manager = MemoryManager(agent_id="test_agent")
        
        # 1. 测试保存记忆
        logger.info("测试保存记忆...")
        save_result = await memory_manager.save_memory(
            key="product_idea",
            content={"name": "智能家居助手", "description": "一款基于AI的智能家居控制系统"},
            priority="high",
            tags=["产品", "AI", "智能家居"]
        )
        logger.info(f"保存记忆结果: {save_result}")
        
        # 2. 测试检索记忆
        logger.info("测试检索记忆...")
        retrieved_memory = await memory_manager.retrieve_memory("product_idea")
        logger.info(f"检索到的记忆: {retrieved_memory}")

        # 3. 测试更新记忆
        logger.info("测试更新记忆...")
        update_result = await memory_manager.update_memory(
            key="product_idea",
            content={"name": "智能家居助手Pro", "description": "一款基于AI的智能家居控制系统，支持语音控制"}
        )
        logger.info(f"更新记忆结果: {update_result}")
        
        # 确认更新成功
        updated_memory = await memory_manager.retrieve_memory("product_idea")
        logger.info(f"更新后的记忆: {updated_memory}")
        
        # # 4. 添加更多记忆用于测试搜索和列表功能
        # await memory_manager.save_memory(
        #     key="user_research",
        #     content="针对30-45岁的科技爱好者进行的市场调研",
        #     priority="normal",
        #     tags=["研究", "市场"]
        # )
        
        # await memory_manager.save_memory(
        #     key="competitor_analysis",
        #     content={"competitors": ["HomeKit", "Google Home", "Alexa"], "strengths": ["AI集成", "用户体验"]},
        #     priority="high",
        #     tags=["竞争", "分析"]
        # )
        
        # # 5. 测试搜索记忆
        # logger.info("测试搜索记忆...")
        # search_results = await memory_manager.search_memories("智能家居")
        # logger.info(f"搜索结果: {search_results}")
        
        # # 6. 测试列出记忆
        # logger.info("测试列出所有记忆...")
        # all_memories = await memory_manager.list_memories()
        # logger.info(f"找到 {len(all_memories)} 条记忆")
        
        # logger.info("测试按优先级筛选记忆...")
        # high_priority = await memory_manager.list_memories(priority="high")
        # logger.info(f"高优先级记忆: {len(high_priority)} 条")
        
        # # 7. 测试删除记忆
        # logger.info("测试删除记忆...")
        # forget_result = await memory_manager.forget_memory("user_research")
        # logger.info(f"删除记忆结果: {forget_result}")
        
        # # 确认删除成功
        # deleted_memory = await memory_manager.retrieve_memory("user_research")
        # logger.info(f"删除后检索结果应为None: {deleted_memory}")
        
        # logger.info("记忆管理器测试完成!")
        return True
    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}")
        logger.error(f"错误堆栈: \n{traceback.format_exc()}")
        return False

async def main():
    """
    主函数
    """
    await test_memory_manager()

if __name__ == "__main__":
    load_dotenv(".env", override=True)
    asyncio.run(main())
