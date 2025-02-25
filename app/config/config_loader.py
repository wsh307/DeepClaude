"""统一配置加载模块"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from app.utils.logger import logger

class AppConfig:
    """应用配置管理类"""
    
    _instance = None  # 单例实例
    
    def __new__(cls, *args, **kwargs):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super(AppConfig, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化配置管理器"""
        if self._initialized:
            return
            
        self._initialized = True
        self.config_data = {}
        self.use_yaml_config = os.getenv("ENABLE_WEB_CONFIG", "false").lower() == "true"
        self.config_file_path = Path(os.getenv("CONFIG_FILE_PATH", "./config/app_config.yaml"))
        
        # 加载配置
        self.reload_config()
    
    def reload_config(self) -> None:
        """重新加载配置"""
        if self.use_yaml_config:
            self._load_from_yaml()
        else:
            self._load_from_env()
    
    def _load_from_yaml(self) -> None:
        """从YAML文件加载配置"""
        try:
            if self.config_file_path.exists():
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    self.config_data = yaml.safe_load(f) or {}
                logger.info(f"已从 {self.config_file_path} 加载配置")
            else:
                logger.warning(f"配置文件 {self.config_file_path} 不存在，将创建默认配置")
                self._load_from_env()  # 先从环境变量加载
                self._create_default_config()  # 然后创建默认配置文件
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            self._load_from_env()  # 失败时从环境变量加载
    
    def _load_from_env(self) -> None:
        """从环境变量加载配置"""
        # 加载环境变量
        load_dotenv()
        
        # 初始化配置数据结构
        self.config_data = {
            "api_keys": {},
            "endpoints": {},
            "models": {},
            "providers": {},
            "options": {},
            "model_mappings": {}  # 添加模型映射部分
        }
        
        # 加载 API 密钥
        self.config_data["api_keys"]["deepseek"] = os.getenv("DEEPSEEK_API_KEY", "")
        self.config_data["api_keys"]["claude"] = os.getenv("CLAUDE_API_KEY", "")
        self.config_data["api_keys"]["openai_composite"] = os.getenv("OPENAI_COMPOSITE_API_KEY", "")
        self.config_data["api_keys"]["allow_api_key"] = os.getenv("ALLOW_API_KEY", "")
        
        # 加载接口端点
        self.config_data["endpoints"]["deepseek"] = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
        self.config_data["endpoints"]["claude"] = os.getenv("CLAUDE_API_URL", "https://api.anthropic.com/v1/messages")
        self.config_data["endpoints"]["openai_composite"] = os.getenv("OPENAI_COMPOSITE_API_URL", "")
        
        # 加载模型设置
        self.config_data["models"]["deepseek"] = os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner")
        self.config_data["models"]["claude"] = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
        self.config_data["models"]["openai_composite"] = os.getenv("OPENAI_COMPOSITE_MODEL", "")
        
        # 加载服务提供商
        self.config_data["providers"]["claude"] = os.getenv("CLAUDE_PROVIDER", "anthropic")
        
        # 加载选项
        self.config_data["options"]["allow_origins"] = os.getenv("ALLOW_ORIGINS", "*")
        self.config_data["options"]["is_origin_reasoning"] = os.getenv("IS_ORIGIN_REASONING", "true").lower() == "true"
        self.config_data["options"]["log_level"] = os.getenv("LOG_LEVEL", "INFO")
        
        # 如果环境变量中有模型映射配置，加载它们
        model_mappings_env = os.getenv("MODEL_MAPPINGS", "")
        if model_mappings_env:
            try:
                # 格式可以是 "alias1:model1,alias2:model2"
                mappings = {}
                for mapping in model_mappings_env.split(","):
                    if ":" in mapping:
                        alias, model = mapping.split(":", 1)
                        mappings[alias.strip()] = model.strip()
                self.config_data["model_mappings"] = mappings
            except Exception as e:
                logger.error(f"解析环境变量中的模型映射失败: {str(e)}")
        
        logger.info("已从环境变量加载配置")
    
    def _create_default_config(self) -> None:
        """创建默认配置文件"""
        try:
            # 确保目录存在
            self.config_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入当前配置到文件
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            logger.info(f"已创建默认配置文件: {self.config_file_path}")
        except Exception as e:
            logger.error(f"创建默认配置文件失败: {str(e)}")
    
    def get_config(self) -> Dict[str, Any]:
        """获取完整配置
        
        Returns:
            Dict[str, Any]: 配置数据
        """
        return self.config_data
    
    def get_value(self, key_path: str, default: Any = None) -> Any:
        """获取指定路径的配置值
        
        Args:
            key_path: 配置键路径，如 "api_keys.deepseek"
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        keys = key_path.split('.')
        value = self.config_data
        
        try:
            for key in keys:
                value = value[key]
            
            # 如果是 API 密钥且为空，尝试从环境变量获取
            if value == "" and "api_keys." in key_path:
                env_key = key_path.split('.')[-1].upper() + "_API_KEY"
                env_value = os.getenv(env_key, "")
                if env_value:
                    logger.debug(f"从环境变量 {env_key} 获取 API 密钥")
                    return env_value
            
            return value
        except (KeyError, TypeError):
            # 对于 API 密钥，特别尝试从环境变量获取
            if "api_keys." in key_path:
                env_key = key_path.split('.')[-1].upper() + "_API_KEY"
                env_value = os.getenv(env_key, "")
                if env_value:
                    logger.debug(f"配置路径 {key_path} 未找到，从环境变量 {env_key} 获取")
                    return env_value
            
            return default
    
    def get_model_mapping(self, model_name: str) -> str:
        """获取模型映射，如果存在映射则返回实际模型名称，否则返回原名称
        
        Args:
            model_name: 请求的模型名称
            
        Returns:
            str: 映射后的模型名称或原名称
        """
        if not model_name:
            return ""
        
        mappings = self.config_data.get("model_mappings", {})
        return mappings.get(model_name, model_name)

# 创建全局配置实例
app_config = AppConfig()

def get_config() -> AppConfig:
    """获取配置实例
    
    Returns:
        AppConfig: 配置实例
    """
    return app_config 