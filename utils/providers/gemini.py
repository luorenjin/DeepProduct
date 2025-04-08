"""
Google Gemini模型适配器
"""

import logging
from typing import Dict, List, Any

from .base_adapter import BaseModelAdapter

logger = logging.getLogger(__name__)

class GeminiAdapter(BaseModelAdapter):
    """Google Gemini API适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化Gemini适配器"""
        super().__init__(config, provider_name="gemini")
    
    def _init_api_endpoints(self):
        """初始化Gemini API端点"""
        self.completion_url = f"{self.api_base}models/{self.default_model}:generateContent"
        self.models_url = f"{self.api_base}models"
            
    def get_headers(self) -> Dict[str, str]:
        """获取Gemini API请求头"""
        return {
            "Content-Type": "application/json"
        }
    
    def _get_request_url(self) -> str:
        """添加API密钥到请求URL"""
        return f"{self.completion_url}?key={self.api_key}"
    
    def _get_models_url(self) -> str:
        """添加API密钥到模型列表URL"""
        return f"{self.models_url}?key={self.api_key}"
        
    def _extract_text_from_response(self, response: Dict[str, Any]) -> str:
        """从Gemini响应中提取文本"""
        candidates = response.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return ""
    
    def _build_request_body(self, messages: List[Dict[str, str]], model: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """构建Gemini请求体"""
        # 转换为Gemini格式
        gemini_messages = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else msg["role"]
            if role == "system":
                role = "user"  # Gemini没有系统角色，转为用户
            gemini_messages.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
            
        return {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": params.get("temperature", 0.7),
                "topP": params.get("top_p", 1.0),
                "maxOutputTokens": params.get("max_tokens", 1024)
            }
        }
    
    def _standardize_response(self, result: Dict[str, Any], messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """标准化Gemini响应为OpenAI格式"""
        content = ""
        candidates = result.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts:
                content = parts[0].get("text", "")
                
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": -1,  # Gemini通常不返回token数量
                "completion_tokens": -1,
                "total_tokens": -1
            },
            "model": self.default_model
        }
    
    def _extract_models_from_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从Gemini响应中提取模型信息"""
        models = []
        raw_models = response.get("models", [])
        
        for model in raw_models:
            if "generativeModel" in model.get("supportedGenerationMethods", []):
                models.append({
                    "id": model.get("name", "").split("/")[-1],
                    "name": model.get("displayName", model.get("name", "")),
                    "provider": self.provider_name,
                    "created": 0,
                    "description": model.get("description", "")
                })
                
        return models
    
    def _extract_error_message(self, response) -> str:
        """从Gemini错误响应中提取错误信息"""
        try:
            error_json = response.json()
            error = error_json.get("error", {})
            return f"{error.get('message', '')} (Code: {error.get('code', '')})"
        except Exception:
            return response.text
