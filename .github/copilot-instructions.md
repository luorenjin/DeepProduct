# GitHub Copilot 指导文件

## 项目介绍

DeepProduct是一个AI驱动的产品设计系统，通过智能Agent协作网络实现从创意到专业产品原型和PRD文档的全流程自动化。系统由多个专业AI Agent组成，包括产品设计师、UI/UX专家、市场分析师等角色，在协调Agent的管理下协同工作。

## 代码风格与规范

### Python代码规范
- 严格遵循PEP8规范
- 使用4空格缩进，不使用制表符
- 类名使用PascalCase（如`ProductDesigner`）
- 函数/方法名使用snake_case（如`analyze_requirements`）
- 常量使用UPPER_SNAKE_CASE（如`MAX_AGENTS`）
- 文件名使用snake_case
- 每个公共方法都要有类型注解和docstring
- 单文件不超过500行，方法不超过50行，类不超过200行

### 项目结构规范
- 按功能模块组织代码，遵循`agents/`、`core/`等目录结构
- 模型定义放在`models/`目录
- 配置文件放在`config/`目录
- 工作流定义放在`workflows/`目录
- 提示词模板放在`prompts/`目录

### 依赖管理
- 使用Poetry或Pipenv进行环境管理
- 所有依赖都需要在requirements.txt中列明

## Agent开发指南

### Agent基础架构
```python
class BaseAgent:
    """所有Agent的基类，定义通用接口和行为"""
    
    def __init__(self, agent_config: Dict[str, Any]):
        """
        初始化Agent
        
        Args:
            agent_config: 包含Agent配置的字典
        """
        self.agent_id = agent_config.get('agent_id')
        self.name = agent_config.get('name')
        self.capabilities = agent_config.get('capabilities', [])
        self.model_config = agent_config.get('model_config', {})
        
    async def process(self, task: Task) -> Result:
        """
        处理分配给Agent的任务
        
        Args:
            task: 任务对象
            
        Returns:
            Result: 任务处理结果
        """
        raise NotImplementedError("子类必须实现process方法")
```

### 提示词模板开发
- 所有提示词模板使用文本文件存储，支持变量替换
- 系统提示词和任务提示词分开定义
- 提示词需包含明确的角色定义、任务描述和输出格式要求

### 工作流开发
- 使用声明式YAML定义工作流
- 明确指定任务依赖关系
- 包含错误处理和回退策略

## 测试规范
- 单元测试覆盖率要求：核心模块≥80%
- 使用pytest框架编写测试
- 模拟与LLM API交互以进行离线测试
- 包含集成测试验证多Agent协作

## 文档规范
- 使用Markdown编写文档
- 每个主要组件都需要有详细文档
- 代码示例应当清晰且可执行
- API文档使用标准格式注释生成

## 安全实践
- 不在代码中硬编码API密钥
- 使用环境变量存储敏感信息
- 输入验证防止注入攻击
- 实现适当的错误处理，避免泄露系统信息

## 记忆管理
### mem0长期记忆体
- Agent必须使用mem0作为长期记忆存储机制
- 记忆操作包括：存储(save)、检索(retrieve)、更新(update)和遗忘(forget)
- 记忆优先级分为：重要(high)、常规(normal)、次要(low)
- 实现记忆相关方法:
```python
async def save_memory(self, key: str, content: Any, priority: str = "normal") -> bool:
    """
    将内容保存到长期记忆中
    
    Args:
        key: 记忆的唯一标识符
        content: 要存储的内容
        priority: 记忆优先级，可选值："high"、"normal"、"low"
        
    Returns:
        bool: 保存是否成功
    """
    pass

async def retrieve_memory(self, key: str) -> Optional[Any]:
    """
    从长期记忆中检索内容
    
    Args:
        key: 记忆的唯一标识符
        
    Returns:
        Optional[Any]: 检索到的内容，如果不存在则返回None
    """
    pass
```
- 记忆持久化：所有记忆应定期保存到持久化存储(Redis/MongoDB)
- 实现记忆上下文同步，确保多Agent间共享关键记忆
- 记忆元数据应包含：创建时间、访问频率、最后访问时间、相关性标签

## 多模型支持
- 代码应支持多种LLM提供商（OpenAI, Anthropic, Google等）
- 使用抽象接口处理不同模型差异
- 模型配置应可在运行时切换

## 提交规范
- 提交信息格式: `<type>(<scope>): <description>`
- 类型: feat, fix, docs, style, refactor, perf, test, chore
- 范围: 受影响的模块名称
- 描述: 简明扼要的变更说明
