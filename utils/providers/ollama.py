"""
Ollama本地模型适配器
"""

import logging
from typing import Dict, List, Any

from .base_adapter import BaseModelAdapter

logger = logging.getLogger(__name__)

class OllamaAdapter(BaseModelAdapter):
    """Ollama本地模型API适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化Ollama适配器"""
        super().__init__(config, provider_name="ollama")
    
    def _init_api_endpoints(self):
        """初始化Ollama API端点"""
        self.completion_url = f"{self.api_base}chat"
        self.models_url = f"{self.api_base}tags"
            
    def get_headers(self) -> Dict[str, str]:
        """获取Ollama API请求头"""
        return {
            "Content-Type": "application/json"
        }
        
    def _extract_text_from_response(self, response: Dict[str, Any]) -> str:
        """从Ollama响应中提取文本"""
        return response.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    def _build_request_body(self, messages: List[Dict[str, str]], model: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建Ollama请求体"""
        return {
            "model": model,
            "messages": messages,
            "options": {
                "temperature": params.get("temperature", 0.7),
                "top_p": params.get("top_p", 1.0),
                "num_predict": params.get("max_tokens", 1024)
            }
        }
    
    def _standardize_response(self, result: Dict[str, Any], messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """标准化Ollama响应为OpenAI格式"""
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": result.get("message", {}).get("content", "")
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": result.get("prompt_eval_count", 0),
                "completion_tokens": result.get("eval_count", 0),
                "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0)
            },
            "model": result.get("model", self.default_model)
        }
    
    def _extract_models_from_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从Ollama响应中提取模型信息"""
        models = []
        raw_models = response.get("models", [])
        
        for model in raw_models:
            models.append({
                "id": model.get("name", ""),
                "name": model.get("name", ""),
                "provider": self.provider_name,
                "created": 0,
                "size": model.get("size", 0),
                "modified_at": model.get("modified_at", "")
            })
                
        return models
    
    def _extract_error_message(self, response) -> str:
        """从Ollama错误响应中提取错误信息"""
        try:
            error_json = response.json()
            return error_json.get("error", response.text)
        except Exception:
            return response.text
