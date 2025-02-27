import os
import time
from typing import List, Dict

from app.config import get_config, load_models_config
from app.utils.logger import logger

def get_models_list() -> Dict:
    """
    获取可用模型列表
    返回格式遵循 OpenAI API 标准
    """
    try:
        if os.getenv("ENABLE_WEB_CONFIG", "false").lower() == "true":
            return get_dynamic_models_list()
        return get_static_models_list()
    except Exception as e:
        logger.error(f"加载模型配置时发生错误: {e}")
        return {"error": str(e)}

def get_dynamic_models_list() -> Dict:
    """获取动态配置的模型列表"""
    config = get_config()
    created_timestamp = int(time.time())
    models_data = [create_model_data("deepclaude", created_timestamp)]
    
    # 添加模型映射别名
    model_mappings = config.get_value("model_mappings", {})
    for alias, _ in model_mappings.items():
        models_data.append(create_model_data(alias, created_timestamp))
    
    return {"object": "list", "data": models_data}

def get_static_models_list() -> Dict:
    """获取静态配置文件中的模型列表"""
    config = load_models_config()
    return {"object": "list", "data": config["models"]}

def create_model_data(model_id: str, timestamp: int) -> Dict:
    """创建标准格式的模型数据"""
    return {
        "id": model_id,
        "object": "model",
        "created": timestamp,
        "owned_by": "deepclaude",
        "permission": [{
            "id": f"modelperm-{model_id}",
            "object": "model_permission",
            "created": timestamp,
            "allow_create_engine": False,
            "allow_sampling": True,
            "allow_logprobs": True,
            "allow_search_indices": False,
            "allow_view": True,
            "allow_fine_tuning": False,
            "organization": "*",
            "group": None,
            "is_blocking": False
        }],
        "root": model_id,
        "parent": None
    }