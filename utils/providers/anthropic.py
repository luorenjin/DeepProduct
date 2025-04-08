"""
Anthropic (Claude) 模型适配器
"""

import logging
from typing import Dict, List, Any

from .base_adapter import BaseModelAdapter

logger = logging.getLogger(__name__)

class AnthropicAdapter(BaseModelAdapter):
    """Anthropic (Claude) API适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化Anthropic适配器"""
        super().__init__(config, provider_name="anthropic")
    
    def _init_api_endpoints(self):
        """初始化Anthropic API端点"""
        self.completion_url = f"{self.api_base}messages"
        self.models_url = f"{self.api_base}models"
            
    def get_headers(self) -> Dict[str, str]:
        """获取Anthropic API请求头"""
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        
    def _extract_text_from_response(self, response: Dict[str, Any]) -> str:
        """从Anthropic响应中提取文本"""
        return response.get("content", [{}])[0].get("text", "")
    
    def _build_request_body(self, messages: List[Dict[str, str]], model: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建Anthropic请求体"""
        # 转换OpenAI格式到Anthropic格式
        anthropic_messages = []
        system_message = None
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                role = "assistant" if msg["role"] == "assistant" else "user"
                anthropic_messages.append({"role": role, "content": msg["content"]})
        
        request_body = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": params.get("max_tokens", 1024),
            "temperature": params.get("temperature", 0.7)
        }
        
        if system_message:
            request_body["system"] = system_message
            
        return request_body
    
    def _standardize_response(self, result: Dict[str, Any], messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """标准化Anthropic响应为OpenAI格式"""
        content = result.get("content", [{}])[0].get("text", "")
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": result.get("stop_reason", "stop")
            }],
            "usage": {
                "prompt_tokens": result.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": result.get("usage", {}).get("output_tokens", 0),
                "total_tokens": result.get("usage", {}).get("input_tokens", 0) + result.get("usage", {}).get("output_tokens", 0)
            },
            "model": result.get("model", self.default_model)
        }
    
    def _extract_models_from_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从Anthropic响应中提取模型信息"""
        models = []
        raw_models = response.get("models", [])
        
        for model in raw_models:
            models.append({
                "id": model.get("id", ""),
                "name": model.get("name", model.get("id", "")),
                "provider": self.provider_name,
                "created": 0,  # Anthropic通常不提供创建时间
                "description": model.get("description", "")
            })
            
        return models
    
    def _extract_error_message(self, response) -> str:
        """从Anthropic错误响应中提取错误信息"""
        try:
            error_json = response.json()
            return error_json.get("error", {}).get("message", response.text)
        except Exception:
            return response.text
