"""
模型适配器 - 提供统一的接口来调用不同的大语言模型服务
"""

import os
import json
import yaml
import logging
import importlib
from typing import Dict, List, Any, Optional, Union, Tuple
import requests
import time

logger = logging.getLogger(__name__)

class ModelAdapter:
    """
    大语言模型适配器，提供统一接口访问多种模型服务
    """
    
    def __init__(self, config_path: str = None):
        """
        初始化模型适配器
        
        Args:
            config_path: 配置文件路径，默认读取环境变量MODEL_CONFIG_PATH或使用默认路径
        """
        if config_path is None:
            config_path = os.environ.get(
                "MODEL_CONFIG_PATH", 
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "model_providers.yaml")
            )
            
        self.config = self._load_config(config_path)
        self.provider_adapters = {}
        self._load_provider_adapters()
        
        logger.info(f"ModelAdapter initialized with {len(self.config['providers'])} providers")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            # 处理环境变量
            for _, provider_config in config['providers'].items():
                if 'api_key' in provider_config and provider_config['api_key'].startswith("${") and provider_config['api_key'].endswith("}"):
                    env_var = provider_config['api_key'][2:-1]
                    provider_config['api_key'] = os.environ.get(env_var, "")
                
                # 添加超时配置（如果不存在）
                if 'timeout' not in provider_config:
                    provider_config['timeout'] = config.get('request_timeout', 60)
                if 'connect_timeout' not in provider_config:
                    provider_config['connect_timeout'] = config.get('connect_timeout', 10)
                if 'read_timeout' not in provider_config:
                    provider_config['read_timeout'] = config.get('read_timeout', 120)
                    
            return config
        except Exception as e:
            logger.error(f"Failed to load model config: {str(e)}")
            # 返回默认配置
            return {
                "providers": {
                    "openai": {
                        "api_base": "https://api.openai.com/v1",
                        "api_key": os.environ.get("OPENAI_API_KEY", ""),
                        "default_model": "gpt-3.5-turbo",
                        "default_params": {
                            "temperature": 0.7,
                            "max_tokens": 2048
                        },
                        "timeout": 60,
                        "connect_timeout": 10,
                        "read_timeout": 120
                    }
                },
                "default_provider": "openai",
                "default_retries": 3,
                "request_timeout": 60,
                "connect_timeout": 10,
                "read_timeout": 120
            }
    
    def _load_provider_adapters(self):
        """加载所有提供商的适配器"""
        from utils.providers import get_adapter_class
        
        for provider_name, provider_config in self.config['providers'].items():
            try:
                # 获取适配器类并实例化
                adapter_class = get_adapter_class(provider_name)
                self.provider_adapters[provider_name] = adapter_class(provider_config)
                logger.debug(f"Loaded adapter for {provider_name}")
            except Exception as e:
                logger.error(f"Failed to load adapter for {provider_name}: {str(e)}")
    
    def get_completion(self, 
                      prompt: str, 
                      provider: str = None, 
                      model: str = None, 
                      **kwargs) -> str:
        """
        使用指定提供商和模型获取文本补全
        
        Args:
            prompt: 输入提示词
            provider: 提供商名称，如果不指定则使用默认提供商
            model: 模型名称，如果不指定则使用提供商默认模型
            **kwargs: 其他参数
            
        Returns:
            模型生成的文本
        """
        provider = provider or self.config.get('default_provider', 'openai')
        
        if provider not in self.provider_adapters:
            logger.error(f"Provider {provider} not available, falling back to default")
            provider = self.config.get('default_provider', 'openai')
            
        adapter = self.provider_adapters[provider]
        return adapter.get_completion(prompt, model, **kwargs)
    
    def get_chat_completion(self, 
                           messages: List[Dict[str, str]], 
                           provider: str = None, 
                           model: str = None, 
                           **kwargs) -> Dict[str, Any]:
        """
        使用指定提供商和模型获取对话补全
        
        Args:
            messages: 对话历史消息列表，格式为OpenAI标准
            provider: 提供商名称，如果不指定则使用默认提供商
            model: 模型名称，如果不指定则使用提供商默认模型
            **kwargs: 其他参数
            
        Returns:
            包含生成文本的响应字典
        """
        provider = provider or self.config.get('default_provider', 'openai')
        
        if provider not in self.provider_adapters:
            logger.error(f"Provider {provider} not available, falling back to default")
            provider = self.config.get('default_provider', 'openai')
            
        adapter = self.provider_adapters[provider]
        
        # 获取重试次数
        retries = kwargs.pop('retries', self.config.get('default_retries', 3))
        
        # 处理超时配置
        timeout = kwargs.pop('timeout', self.config.get('request_timeout', 60))
        connect_timeout = kwargs.pop('connect_timeout', self.config.get('connect_timeout', 10))
        
        # 如果timeout是整数，将其转换为元组(连接超时, 读取超时)
        if isinstance(timeout, (int, float)):
            timeout = (connect_timeout, timeout)
        
        for attempt in range(retries):
            try:
                return adapter.get_chat_completion(messages, model, timeout=timeout, **kwargs)
            except (TimeoutError, ConnectionError) as e:
                error_type = "Timeout" if isinstance(e, TimeoutError) else "Connection"
                if attempt == retries - 1:
                    logger.error(f"{error_type} error after {retries} attempts: {str(e)}")
                    raise
                logger.warning(f"{error_type} error on attempt {attempt + 1}, retrying: {str(e)}")
                # 超时错误增加更长的等待时间
                time.sleep(min(2 ** attempt, 30))  # 指数退避，最长等待30秒
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"Failed to get completion after {retries} attempts: {str(e)}")
                    raise
                logger.warning(f"Attempt {attempt + 1} failed, retrying: {str(e)}")
                time.sleep(2 ** attempt)  # 指数退避
    
    def list_available_providers(self) -> List[str]:
        """获取所有可用的提供商名称列表"""
        return list(self.provider_adapters.keys())
    
    def list_available_models(self, provider: str = None) -> Union[List[str], Dict[str, List[str]]]:
        """
        获取指定提供商的可用模型列表
        
        Args:
            provider: 提供商名称，如果不指定则返回所有提供商的模型
            
        Returns:
            可用模型列表或按提供商分类的模型字典
        """
        if provider:
            if provider in self.config['providers']:
                return self.config['providers'][provider].get('available_models', [])
            return []
        
        # 返回所有提供商的模型
        all_models = {}
        for provider_name, provider_config in self.config['providers'].items():
            all_models[provider_name] = provider_config.get('available_models', [])
            
        return all_models
    
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        获取指定提供商的配置
        
        Args:
            provider: 提供商名称
            
        Returns:
            提供商配置字典
        """
        if provider in self.config['providers']:
            return self.config['providers'][provider]
        return {}
    
    def is_provider_available(self, provider: str) -> bool:
        """
        检查指定提供商是否可用
        
        Args:
            provider: 提供商名称
            
        Returns:
            提供商是否可用
        """
        # 检查提供商是否在配置中
        if provider not in self.config['providers']:
            return False
            
        # 检查是否有API密钥（ollama为本地模型，可以没有API密钥）
        if provider != 'ollama' and not self.config['providers'][provider].get('api_key'):
            return False
            
        # 检查适配器是否已加载
        return provider in self.provider_adapters
    
    def check_health(self) -> Dict[str, bool]:
        """
        检查所有提供商的健康状态
        
        Returns:
            各提供商的健康状态字典
        """
        health_status = {}
        
        for provider_name, adapter in self.provider_adapters.items():
            try:
                # 简单的健康检查 - 尝试获取可用模型
                models = self.list_available_models(provider_name)
                health_status[provider_name] = len(models) > 0
            except Exception:
                health_status[provider_name] = False
                
        return health_status
