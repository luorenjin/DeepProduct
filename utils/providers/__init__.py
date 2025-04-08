"""
模型服务提供商适配器包
"""

from .base_adapter import BaseModelAdapter
from .openai import OpenAIAdapter
from .anthropic import AnthropicAdapter
from .gemini import GeminiAdapter
from .ollama import OllamaAdapter
from .qwen import QwenAdapter
from .doubao import DoubaoAdapter
from .deepseek import DeepseekAdapter
from .openrouter import OpenRouterAdapter

# 服务提供商到适配器类的映射
PROVIDER_ADAPTERS = {
    'openai': OpenAIAdapter,
    'anthropic': AnthropicAdapter,
    'gemini': GeminiAdapter,
    'ollama': OllamaAdapter,
    'qwen': QwenAdapter,
    'doubao': DoubaoAdapter,
    'deepseek': DeepseekAdapter,
    'openrouter': OpenRouterAdapter,
}

def get_adapter_class(provider_name: str):
    """根据提供商名称获取适配器类"""
    return PROVIDER_ADAPTERS.get(provider_name, OpenAIAdapter)
