"""Web 配置服务器模块"""

import os
import asyncio
from typing import Dict, Any, Optional


from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
import secrets
import uvicorn
from pathlib import Path

from app.utils.logger import logger
from .config_manager import ConfigManager

# 获取环境变量
WEB_CONFIG_PORT = int(os.getenv("WEB_CONFIG_PORT", "8080"))
WEB_CONFIG_PATH = os.getenv("WEB_CONFIG_PATH", "/admin").rstrip("/")
WEB_CONFIG_USERNAME = os.getenv("WEB_CONFIG_USERNAME", "admin")
WEB_CONFIG_PASSWORD = os.getenv("WEB_CONFIG_PASSWORD", "admin")
CONFIG_FILE_PATH = os.getenv("CONFIG_FILE_PATH", "./config/app_config.yaml")

# 初始化 FastAPI 应用
app = FastAPI(title="DeepClaude 配置管理", docs_url=None, redoc_url=None)

# 安全验证
security = HTTPBasic()

# 配置管理器
config_manager = ConfigManager(CONFIG_FILE_PATH)

# 获取当前模块的路径
current_dir = Path(__file__).parent

# 设置静态文件目录
app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")

# 设置模板目录
templates = Jinja2Templates(directory=current_dir / "templates")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 验证凭据
def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """验证用户凭据
    
    Args:
        credentials: HTTP基本认证凭据
        
    Returns:
        str: 用户名
    
    Raises:
        HTTPException: 如果认证失败
    """
    is_username_correct = secrets.compare_digest(credentials.username, WEB_CONFIG_USERNAME)
    is_password_correct = secrets.compare_digest(credentials.password, WEB_CONFIG_PASSWORD)
    
    if not (is_username_correct and is_password_correct):
        logger.warning(f"认证失败: 用户名={credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    logger.info(f"用户 {credentials.username} 认证成功")
    return credentials.username

@app.get(WEB_CONFIG_PATH)
async def read_root(request: Request):
    """根路径处理程序
    
    Args:
        request: 请求对象
        
    Returns:
        HTML响应或重定向到登录页面
    """
    # 验证基本认证头部
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Basic "):
        # 重定向到登录页面
        return RedirectResponse(url=f"{WEB_CONFIG_PATH}/login")
    
    try:
        # 尝试验证凭据
        credentials = HTTPBasicCredentials(
            username=WEB_CONFIG_USERNAME, 
            password=WEB_CONFIG_PASSWORD
        )
        username = verify_credentials(credentials)
        # 返回主页面
        return templates.TemplateResponse(
            "index.html", 
            {"request": request, "username": username}
        )
    except HTTPException:
        # 认证失败，重定向到登录页面
        return RedirectResponse(url=f"{WEB_CONFIG_PATH}/login")

@app.get(f"{WEB_CONFIG_PATH}/login")
async def login_page(request: Request):
    """登录页面
    
    Args:
        request: 请求对象
        
    Returns:
        HTML响应
    """
    return templates.TemplateResponse("login.html", {"request": request})

@app.post(f"{WEB_CONFIG_PATH}/api/auth")
async def auth_api(credentials: HTTPBasicCredentials = Depends(security)):
    """认证API
    
    Args:
        credentials: HTTP基本认证凭据
        
    Returns:
        JSON响应
    """
    try:
        username = verify_credentials(credentials)
        return {"status": "success", "username": username}
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"status": "error", "message": e.detail}
        )

@app.get(f"{WEB_CONFIG_PATH}/api/config")
async def get_config(username: str = Depends(verify_credentials)):
    """获取配置 API
    
    Args:
        username: 已验证的用户名
        
    Returns:
        Dict[str, Any]: 配置数据
    """
    return config_manager.get_config()

@app.post(f"{WEB_CONFIG_PATH}/api/config")
async def update_config(config: Dict[str, Any], username: str = Depends(verify_credentials)):
    """更新配置 API
    
    Args:
        config: 新的配置数据
        username: 已验证的用户名
        
    Returns:
        Dict[str, Any]: 操作结果
    """
    # 记录更新前的 API 密钥信息
    logger.info(f"更新配置: API 密钥状态 - DeepSeek:{bool(config.get('api_keys', {}).get('deepseek'))}, Claude:{bool(config.get('api_keys', {}).get('claude'))}")
    
    success = config_manager.update_config(config)
    
    if success:
        # 重新加载主应用的配置
        from app.config import get_config
        get_config().reload_config()
        
        # 记录已更新的配置信息
        logger.info(f"配置已成功更新并重新加载")
        return {"status": "success", "message": "配置已更新"}
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "更新配置失败"}
        )

@app.get(f"{WEB_CONFIG_PATH}/api/model-mappings")
async def get_model_mappings(username: str = Depends(verify_credentials)):
    """获取模型映射 API
    
    Args:
        username: 已验证的用户名
        
    Returns:
        Dict[str, str]: 模型映射关系
    """
    return config_manager.get_model_mappings()

@app.post(f"{WEB_CONFIG_PATH}/api/model-mappings")
async def add_or_update_model_mapping(mapping: Dict[str, str], username: str = Depends(verify_credentials)):
    """添加或更新模型映射 API
    
    Args:
        mapping: 包含 alias 和 model_name 的字典
        username: 已验证的用户名
        
    Returns:
        Dict[str, Any]: 操作结果
    """
    if "alias" not in mapping or "model_name" not in mapping:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "请提供 alias 和 model_name"}
        )
    
    success = config_manager.update_model_mapping(mapping["alias"], mapping["model_name"])
    
    if success:
        # 重新加载主应用的配置
        from app.config import get_config
        get_config().reload_config()
        
        return {"status": "success", "message": f"已更新映射: {mapping['alias']} -> {mapping['model_name']}"}
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "更新模型映射失败"}
        )

@app.delete(f"{WEB_CONFIG_PATH}/api/model-mappings/{{alias}}")
async def delete_model_mapping(alias: str, username: str = Depends(verify_credentials)):
    """删除模型映射 API
    
    Args:
        alias: 要删除的模型别名
        username: 已验证的用户名
        
    Returns:
        Dict[str, Any]: 操作结果
    """
    success = config_manager.delete_model_mapping(alias)
    
    if success:
        # 重新加载主应用的配置
        from app.config import get_config
        get_config().reload_config()
        
        return {"status": "success", "message": f"已删除映射: {alias}"}
    else:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"status": "error", "message": f"找不到映射: {alias}"}
        )

async def start_web_config():
    """启动 Web 配置服务器"""
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=WEB_CONFIG_PORT,
        log_level="info"
    )
    server = uvicorn.Server(config)
    logger.info(f"启动 Web 配置服务器在 http://0.0.0.0:{WEB_CONFIG_PORT}{WEB_CONFIG_PATH}")
    await server.serve() 