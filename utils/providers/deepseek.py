"""
DeepSeek模型适配器
"""

import logging
from typing import Dict, List, Any

from .base_adapter import BaseModelAdapter

logger = logging.getLogger(__name__)

class DeepseekAdapter(BaseModelAdapter):
    """DeepSeek API适配器(继承OpenAI接口格式)"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化DeepSeek适配器"""
        super().__init__(config, provider_name="deepseek")
    
    def _init_api_endpoints(self):
        """初始化DeepSeek API端点"""
        if self.api_base.endswith('v1/'):
            self.completion_url = f"{self.api_base}chat/completions"
            self.models_url = f"{self.api_base}models"
        else:
            self.completion_url = f"{self.api_base}v1/chat/completions"
            self.models_url = f"{self.api_base}v1/models"
            
    def get_headers(self) -> Dict[str, str]:
        """获取DeepSeek API请求头"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
    def _extract_text_from_response(self, response: Dict[str, Any]) -> str:
        """从DeepSeek响应中提取文本"""
        return response.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    def _build_request_body(self, messages: List[Dict[str, str]], model: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建DeepSeek请求体(OpenAI兼容格式)"""
        request_body = {
            "model": model,
            "messages": messages,
        }
        # 添加其他参数
        for key, value in params.items():
            if key not in ["model", "messages"]:
                request_body[key] = value
                
        return request_body
    
    def _standardize_response(self, result: Dict[str, Any], messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """DeepSeek响应已是OpenAI格式，无需转换"""
        return result
    
    def _extract_models_from_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从DeepSeek响应中提取模型信息"""
        models = []
        raw_models = response.get("data", [])
        
        for model in raw_models:
            models.append({
                "id": model.get("id", ""),
                "name": model.get("id", ""),
                "provider": self.provider_name,
                "created": model.get("created", 0)
            })
                
        return models
    
    def _extract_error_message(self, response) -> str:
        """从DeepSeek错误响应中提取错误信息"""
        try:
            error_json = response.json()
            return error_json.get("error", {}).get("message", response.text)
        except Exception:
            return response.text
