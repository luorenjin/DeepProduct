"""
基础模型适配器 - 为所有LLM服务提供基础功能
"""

import os
import json
import requests
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

logger = logging.getLogger(__name__)

class BaseModelAdapter:
    """
    大语言模型基础适配器类，定义通用接口和功能
    """
    
    def __init__(self, config: Dict[str, Any], provider_name: str = "generic"):
        """
        初始化基础适配器
        
        Args:
            config: 提供商配置
            provider_name: 提供商名称
        """
        self.config = config
        self.provider_name = provider_name
        self.api_base = config.get('api_base', '')
        self.api_key = config.get('api_key', '')
        self.default_model = config.get('default_model', '')
        self.default_params = config.get('default_params', {})
        
        # 添加默认超时配置
        self.default_timeout = config.get('timeout', 60)
        self.default_connect_timeout = config.get('connect_timeout', 10)
        self.default_read_timeout = config.get('read_timeout', 90)
        
        # 确保API基础URL正确结尾
        if self.api_base and not self.api_base.endswith('/'):
            self.api_base = self.api_base + '/'
        
        # 初始化API端点，子类需要实现这个方法
        self._init_api_endpoints()
    
    def get_provider_config(self) -> Dict[str, Any]:
        """
        获取提供商配置信息
        
        Returns:
            包含API密钥和基础URL等配置的字典
        """
        return {
            "provider_name": self.provider_name,
            "api_key": self.api_key,
            "api_base": self.api_base,
            "default_model": self.default_model
        }
            
    def _init_api_endpoints(self):
        """初始化API端点，子类必须实现此方法"""
        self.completion_url = ""
        self.models_url = ""
        raise NotImplementedError("子类必须实现_init_api_endpoints方法")
        
    def get_headers(self) -> Dict[str, str]:
        """获取请求头，子类必须实现此方法"""
        raise NotImplementedError("子类必须实现get_headers方法")
        
    def get_completion(self, prompt: str, model: str = None, **kwargs) -> str:
        """
        获取文本补全 (转换为聊天格式)
        
        Args:
            prompt: 输入提示词
            model: 模型名称
            **kwargs: 其他参数
            
        Returns:
            生成的文本
        """
        messages = [{"role": "user", "content": prompt}]
        response = self.get_chat_completion(messages, model, **kwargs)
        return self._extract_text_from_response(response)
    
    def _extract_text_from_response(self, response: Dict[str, Any]) -> str:
        """从响应中提取文本，子类必须实现此方法"""
        raise NotImplementedError("子类必须实现_extract_text_from_response方法")
        
    def get_chat_completion(self, 
                           messages: List[Dict[str, str]], 
                           model: str = None, 
                           **kwargs) -> Dict[str, Any]:
        """
        获取聊天补全
        
        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 其他参数
            
        Returns:
            API响应
        """
        model = model or self.default_model
        
        # 处理超时配置
        timeout = kwargs.pop('timeout', self.default_timeout)
        
        # 如果timeout是单个值，将其转换为元组(连接超时, 读取超时)
        if isinstance(timeout, (int, float)):
            timeout = (self.default_connect_timeout, timeout)
        elif isinstance(timeout, Tuple) and len(timeout) == 2:
            pass
        else:
            timeout = (self.default_connect_timeout, self.default_read_timeout)
        
        # 合并默认参数和用户参数
        params = self.default_params.copy()
        params.update(kwargs)
        
        # 构建请求体
        request_body = self._build_request_body(messages, model, params)
        
        # 获取请求头和URL
        headers = self.get_headers()
        url = self._get_request_url()
        
        try:
            logger.debug(f"Sending request to {self.provider_name} at {url} with timeout {timeout}")
            response = requests.post(
                url,
                headers=headers,
                json=request_body,
                timeout=timeout  # 使用元组格式 (连接超时, 读取超时)
            )
            
            # 检查响应
            if response.status_code != 200:
                error_detail = self._extract_error_message(response)
                logger.error(f"API request to {self.provider_name} failed with status {response.status_code}: {error_detail}")
                raise Exception(f"API request failed: {response.status_code} - {error_detail}")
            
            result = response.json()
            
            # 标准化响应格式
            result = self._standardize_response(result, messages)
                
            return result
            
        except requests.exceptions.Timeout as e:
            # 超时错误特殊处理
            error_msg = f"Request to {self.provider_name} timed out after {timeout[1]} seconds"
            logger.error(error_msg)
            raise TimeoutError(error_msg) from e
        except requests.exceptions.ConnectionError as e:
            # 连接错误特殊处理
            error_msg = f"Connection error when connecting to {self.provider_name}: {str(e)}"
            logger.error(error_msg)
            raise ConnectionError(error_msg) from e
        except requests.RequestException as e:
            logger.error(f"Request error for {self.provider_name}: {str(e)}")
            raise
    
    def _get_request_url(self) -> str:
        """获取请求URL，默认返回completion_url，子类可以覆盖此方法"""
        return self.completion_url
    
    def _build_request_body(self, messages: List[Dict[str, str]], model: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建请求体，子类必须实现此方法"""
        raise NotImplementedError("子类必须实现_build_request_body方法")
    
    def _standardize_response(self, result: Dict[str, Any], messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """标准化响应为OpenAI格式，子类必须实现此方法"""
        raise NotImplementedError("子类必须实现_standardize_response方法")
    
    def list_models(self, timeout: Union[int, Tuple[int, int]] = None) -> List[Dict[str, Any]]:
        """
        获取提供商支持的模型列表
        
        Args:
            timeout: 请求超时时间（秒）或(连接超时, 读取超时)元组
            
        Returns:
            模型信息列表
        """
        # 处理超时配置
        if timeout is None:
            timeout = (self.default_connect_timeout, self.default_timeout)
        elif isinstance(timeout, (int, float)):
            timeout = (self.default_connect_timeout, timeout)
        
        url = self._get_models_url()
        headers = self.get_headers()
        
        try:
            logger.debug(f"Fetching models from {self.provider_name} at {url}")
            response = requests.get(url, headers=headers, timeout=timeout)
            
            if response.status_code != 200:
                error_detail = self._extract_error_message(response)
                logger.error(f"Failed to fetch models from {self.provider_name}: {error_detail}")
                return []
                
            result = response.json()
            
            # 提取模型列表
            models = self._extract_models_from_response(result)
            return models
            
        except requests.exceptions.Timeout as e:
            logger.error(f"Request to fetch models from {self.provider_name} timed out after {timeout[1]} seconds")
            return []
        except requests.RequestException as e:
            logger.error(f"Request error when fetching models from {self.provider_name}: {str(e)}")
            return []
    
    def _get_models_url(self) -> str:
        """获取模型列表URL，默认返回models_url，子类可以覆盖此方法"""
        return self.models_url
            
    def _extract_models_from_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从响应中提取模型信息，子类必须实现此方法"""
        raise NotImplementedError("子类必须实现_extract_models_from_response方法")
    
    def _extract_error_message(self, response) -> str:
        """从错误响应中提取错误信息，子类应覆盖此方法以提供更详细的错误处理"""
        try:
            error_json = response.json()
            if isinstance(error_json, dict):
                for key in ["error", "message", "detail", "description"]:
                    if key in error_json:
                        if isinstance(error_json[key], dict):
                            return str(error_json[key].get("message", error_json[key]))
                        return str(error_json[key])
            return response.text
        except Exception as e:
            logger.debug(f"Error parsing error response: {str(e)}")
            return response.text
