"""
阿里云通义千问模型适配器
"""

import logging
from typing import Dict, List, Any

from .base_adapter import BaseModelAdapter

logger = logging.getLogger(__name__)

class QwenAdapter(BaseModelAdapter):
    """阿里云通义千问API适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化通义千问适配器"""
        super().__init__(config, provider_name="qwen")
    
    def _init_api_endpoints(self):
        """初始化通义千问API端点"""
        self.completion_url = f"{self.api_base}services/aigc/text-generation/generation"
        self.models_url = f"{self.api_base}services/aigc/text-generation/models"
            
    def get_headers(self) -> Dict[str, str]:
        """获取通义千问API请求头"""
        return {
            "Content-Type": "application/json;charset=utf8",
            "Authorization": f"Bearer {self.api_key}"
        }
        
    def _extract_text_from_response(self, response: Dict[str, Any]) -> str:
        """从通义千问响应中提取文本"""
        return response.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    def _build_request_body(self, messages: List[Dict[str, str]], model: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建通义千问请求体"""
        return {
            "model": model,
            "input": {
                "messages": messages
            },
            "parameters": {
                "temperature": params.get("temperature", 0.7),
                "top_p": params.get("top_p", 1.0),
                "max_tokens": params.get("max_tokens", 1024)
            }
        }
    
    def _standardize_response(self, result: Dict[str, Any], messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """标准化通义千问响应为OpenAI格式"""
        output = result.get("output", {})
        choices = output.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""
        
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": choices[0].get("finish_reason", "stop") if choices else "stop"
            }],
            "usage": output.get("usage", {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }),
            "model": self.default_model
        }
    
    def _extract_models_from_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从通义千问响应中提取模型信息"""
        models = []
        raw_models = response.get("data", {}).get("models", [])
        
        for model in raw_models:
            models.append({
                "id": model.get("model", ""),
                "name": model.get("name", model.get("model", "")),
                "provider": self.provider_name,
                "created": 0
            })
                
        return models
    
    def _extract_error_message(self, response) -> str:
        """从通义千问错误响应中提取错误信息"""
        try:
            error_json = response.json()
            return error_json.get("message", error_json.get("error", response.text))
        except Exception:
            return response.text
