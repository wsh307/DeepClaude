from fastapi import HTTPException, Header
from typing import Optional
import os
from dotenv import load_dotenv
from app.utils.logger import logger
from app.config import get_config

# 加载配置
logger.info(f"当前工作目录: {os.getcwd()}")
config = get_config()

# 获取API密钥
ALLOW_API_KEY = config.get_value("api_keys.allow_api_key", "")
logger.info(f"ALLOW_API_KEY环境变量状态: {'已设置' if ALLOW_API_KEY else '未设置'}")

if not ALLOW_API_KEY:
    raise ValueError("ALLOW_API_KEY 配置未设置")

# 打印API密钥的前4位用于调试
logger.info(f"Loaded API key starting with: {ALLOW_API_KEY[:4] if len(ALLOW_API_KEY) >= 4 else ALLOW_API_KEY}")


async def verify_api_key(authorization: Optional[str] = Header(None)) -> None:
    """验证API密钥

    Args:
        authorization (Optional[str], optional): Authorization header中的API密钥. Defaults to Header(None).

    Raises:
        HTTPException: 当Authorization header缺失或API密钥无效时抛出401错误
    """
    if authorization is None:
        logger.warning("请求缺少Authorization header")
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )
    
    api_key = authorization.replace("Bearer ", "").strip()
    if api_key != ALLOW_API_KEY:
        logger.warning(f"无效的API密钥: {api_key}")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    logger.info("API密钥验证通过")
