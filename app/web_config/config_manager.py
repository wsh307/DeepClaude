"""配置管理模块，用于读写配置文件"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv, set_key
from app.utils.logger import logger
from app.config import get_config

class ConfigManager:
    """配置管理类，负责读写配置文件"""
    
    def __init__(self, config_path: str):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.app_config = get_config()
        self.config_data = {}
        self.loaded = False
        self._load_config()
    
    def _load_config(self) -> None:
        """从文件加载配置"""
        # 直接使用全局配置实例的数据
        self.config_data = self.app_config.get_config()
        
        # 确保配置中包含模型映射部分
        if "model_mappings" not in self.config_data:
            self.config_data["model_mappings"] = {}
            
        self.loaded = True
        logger.info(f"已加载配置")
    
    def _save_config(self) -> bool:
        """保存配置到文件
        
        Returns:
            bool: 是否成功保存
        """
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            if self.config_path.suffix.lower() in ['.yaml', '.yml']:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(self.config_data, f, allow_unicode=True, sort_keys=False)
            elif self.config_path.suffix.lower() == '.json':
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config_data, f, ensure_ascii=False, indent=2)
            else:
                logger.error(f"不支持的配置文件格式: {self.config_path.suffix}")
                return False
            
            logger.info(f"已保存配置到文件: {self.config_path}")
            
            # 更新全局配置实例
            self.app_config.reload_config()
            
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """获取完整配置
        
        Returns:
            Dict[str, Any]: 配置数据
        """
        return self.config_data
    
    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """更新配置
        
        Args:
            new_config: 新的配置数据
            
        Returns:
            bool: 是否成功更新
        """
        try:
            self.config_data = new_config
            success = self._save_config()
            if success:
                # 更新环境变量
                self._update_env_from_config()
            return success
        except Exception as e:
            logger.error(f"更新配置失败: {str(e)}")
            return False
    
    def _update_env_from_config(self) -> None:
        """将配置同步到环境变量"""
        dotenv_path = Path(".env")
        
        # API Keys
        set_key(dotenv_path, "DEEPSEEK_API_KEY", self.config_data.get("api_keys", {}).get("deepseek", ""))
        set_key(dotenv_path, "CLAUDE_API_KEY", self.config_data.get("api_keys", {}).get("claude", ""))
        set_key(dotenv_path, "OPENAI_COMPOSITE_API_KEY", self.config_data.get("api_keys", {}).get("openai_composite", ""))
        set_key(dotenv_path, "ALLOW_API_KEY", self.config_data.get("api_keys", {}).get("allow_api_key", ""))
        
        # Endpoints
        set_key(dotenv_path, "DEEPSEEK_API_URL", self.config_data.get("endpoints", {}).get("deepseek", ""))
        set_key(dotenv_path, "CLAUDE_API_URL", self.config_data.get("endpoints", {}).get("claude", ""))
        set_key(dotenv_path, "OPENAI_COMPOSITE_API_URL", self.config_data.get("endpoints", {}).get("openai_composite", ""))
        
        # Models
        set_key(dotenv_path, "DEEPSEEK_MODEL", self.config_data.get("models", {}).get("deepseek", ""))
        set_key(dotenv_path, "CLAUDE_MODEL", self.config_data.get("models", {}).get("claude", ""))
        set_key(dotenv_path, "OPENAI_COMPOSITE_MODEL", self.config_data.get("models", {}).get("openai_composite", ""))
        
        # Providers
        set_key(dotenv_path, "CLAUDE_PROVIDER", self.config_data.get("providers", {}).get("claude", ""))
        
        # Options
        set_key(dotenv_path, "ALLOW_ORIGINS", self.config_data.get("options", {}).get("allow_origins", "*"))
        set_key(dotenv_path, "IS_ORIGIN_REASONING", str(self.config_data.get("options", {}).get("is_origin_reasoning", True)).lower())
        set_key(dotenv_path, "LOG_LEVEL", self.config_data.get("options", {}).get("log_level", "INFO"))
        
        logger.info("已将配置同步到环境变量")
    
    def get_model_mappings(self) -> Dict[str, str]:
        """获取模型映射配置
        
        Returns:
            Dict[str, str]: 模型映射关系，格式为 {模型别名: 实际模型名称}
        """
        if not self.loaded:
            self._load_config()
        
        return self.config_data.get("model_mappings", {})
    
    def update_model_mapping(self, alias: str, model_name: str) -> bool:
        """更新单个模型映射
        
        Args:
            alias: 模型别名
            model_name: 实际模型名称
            
        Returns:
            bool: 是否成功更新
        """
        if not self.loaded:
            self._load_config()
        
        if "model_mappings" not in self.config_data:
            self.config_data["model_mappings"] = {}
        
        self.config_data["model_mappings"][alias] = model_name
        return self._save_config()
    
    def delete_model_mapping(self, alias: str) -> bool:
        """删除模型映射
        
        Args:
            alias: 要删除的模型别名
            
        Returns:
            bool: 是否成功删除
        """
        if not self.loaded:
            self._load_config()
        
        if "model_mappings" in self.config_data and alias in self.config_data["model_mappings"]:
            del self.config_data["model_mappings"][alias]
            return self._save_config()
        
        return False 