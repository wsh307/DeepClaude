"""Web 配置服务器模块"""

import os
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
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

# JWT 配置
SECRET_KEY = os.getenv("WEB_CONFIG_SECRET_KEY", "your-secret-key-here")  # JWT 加密密钥
ALGORITHM = "HS256"  # JWT 加密算法，使用 HMAC-SHA256
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("WEB_CONFIG_TOKEN_EXPIRE_MINUTES", 30))  # Token 过期时间（分钟）

# 初始化 FastAPI 应用
app = FastAPI(title="DeepClaude 配置管理", docs_url=None, redoc_url=None)

# 自定义认证处理类，同时支持 cookie 和 header 中的 token
class CookieOAuth2PasswordBearer(OAuth2PasswordBearer):
    """扩展的 OAuth2PasswordBearer，支持从 cookie 和 header 获取 token
    
    继承自 FastAPI 的 OAuth2PasswordBearer，添加了从 cookie 获取 token 的功能
    优先从 cookie 获取，如果没有则尝试从 header 获取
    """
    async def __call__(self, request: Request) -> Optional[str]:
        # 首先尝试从 cookie 获取 token
        token = request.cookies.get("access_token")
        if not token:
            # 如果 cookie 中没有，尝试从认证头获取
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未提供认证信息",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return token

# 使用自定义的认证 scheme
oauth2_scheme = CookieOAuth2PasswordBearer(tokenUrl=f"{WEB_CONFIG_PATH}/api/token")

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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建 JWT 访问令牌
    
    Args:
        data: 要编码到令牌中的数据
        expires_delta: 过期时间增量，如果不提供则默认 15 分钟
    
    Returns:
        str: 编码后的 JWT 令牌
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})  # 添加过期时间声明
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """验证当前用户的令牌并返回用户信息
    
    Args:
        token: JWT 令牌，通过依赖注入获取
    
    Returns:
        str: 用户名
        
    Raises:
        HTTPException: 当令牌无效或过期时抛出 401 错误
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # 解码并验证令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")  # sub 声明用于存储用户标识
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

@app.get(WEB_CONFIG_PATH)
async def read_root(request: Request):
    """根路径处理程序"""
    # 检查是否已登录
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url=f"{WEB_CONFIG_PATH}/login")
    
    try:
        username = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub")
        return templates.TemplateResponse(
            "index.html", 
            {"request": request, "username": username}
        )
    except JWTError:
        return RedirectResponse(url=f"{WEB_CONFIG_PATH}/login")

@app.get(f"{WEB_CONFIG_PATH}/login")
async def login_page(request: Request):
    """登录页面"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post(f"{WEB_CONFIG_PATH}/api/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """登录接口，验证用户凭据并返回访问令牌
    
    Args:
        form_data: 包含用户名和密码的表单数据
    
    Returns:
        JSONResponse: 包含访问令牌和相关信息的响应
        
    Raises:
        HTTPException: 当用户名或密码错误时抛出 401 错误
    """
    # 验证用户名和密码
    if not (form_data.username == WEB_CONFIG_USERNAME and 
            form_data.password == WEB_CONFIG_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, 
        expires_delta=access_token_expires
    )
    
    # 构建响应
    response = JSONResponse({
        "access_token": access_token, 
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # 过期时间（秒）
    })
    
    # 设置 cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,     # 防止 JavaScript 访问 cookie
        secure=False,      # 开发环境设为 False，生产环境应设为 True
        samesite="lax",    # 防止 CSRF 攻击
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60  # cookie 过期时间（秒）
    )
    
    return response

# 修改所有需要认证的 API 端点
@app.get(f"{WEB_CONFIG_PATH}/api/config")
async def get_config(current_user: str = Depends(get_current_user)):
    """获取配置 API"""
    return config_manager.get_config()

@app.post(f"{WEB_CONFIG_PATH}/api/config")
async def update_config(
    config: Dict[str, Any], 
    current_user: str = Depends(get_current_user)
):
    """更新配置 API"""
    logger.info(f"更新配置: API 密钥状态 - DeepSeek:{bool(config.get('api_keys', {}).get('deepseek'))}, Claude:{bool(config.get('api_keys', {}).get('claude'))}")
    
    success = config_manager.update_config(config)
    
    if success:
        from app.config import get_config
        get_config().reload_config()
        logger.info(f"配置已成功更新并重新加载")
        return {"status": "success", "message": "配置已更新"}
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "更新配置失败"}
        )

@app.get(f"{WEB_CONFIG_PATH}/api/model-mappings")
async def get_model_mappings(current_user: str = Depends(get_current_user)):
    """获取模型映射 API"""
    return config_manager.get_model_mappings()

@app.post(f"{WEB_CONFIG_PATH}/api/model-mappings")
async def add_or_update_model_mapping(
    mapping: Dict[str, str], 
    current_user: str = Depends(get_current_user)
):
    """添加或更新模型映射 API"""
    if "alias" not in mapping or "model_name" not in mapping:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "请提供 alias 和 model_name"}
        )
    
    success = config_manager.update_model_mapping(mapping["alias"], mapping["model_name"])
    
    if success:
        from app.config import get_config
        get_config().reload_config()
        return {"status": "success", "message": f"已更新映射: {mapping['alias']} -> {mapping['model_name']}"}
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "更新模型映射失败"}
        )

@app.delete(f"{WEB_CONFIG_PATH}/api/model-mappings/{{alias}}")
async def delete_model_mapping(
    alias: str, 
    current_user: str = Depends(get_current_user)
):
    """删除模型映射 API"""
    success = config_manager.delete_model_mapping(alias)
    
    if success:
        from app.config import get_config
        get_config().reload_config()
        return {"status": "success", "message": f"已删除映射: {alias}"}
    else:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"status": "error", "message": f"找不到映射: {alias}"}
        )

@app.post(f"{WEB_CONFIG_PATH}/api/logout")
async def logout():
    """登出接口，清除认证 cookie
    
    Returns:
        JSONResponse: 包含登出状态的响应
    """
    response = JSONResponse({"status": "success", "message": "已登出"})
    response.delete_cookie("access_token")  # 删除认证 cookie
    return response

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