import os
import sys
import time

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.deepclaude.deepclaude import DeepClaude
from app.openai_composite import OpenAICompatibleComposite
from app.utils.auth import verify_api_key
from app.utils.logger import logger
from app.config import get_config, load_models_config

# 加载环境变量 - 仅用于初始化配置管理器
load_dotenv()

# 获取配置实例
config = get_config()

app = FastAPI(title="DeepClaude API")

# 从配置获取值
ALLOW_ORIGINS = config.get_value("options.allow_origins", "*")

CLAUDE_API_KEY = config.get_value("api_keys.claude", "")
ENV_CLAUDE_MODEL = config.get_value("models.claude", "")
CLAUDE_PROVIDER = config.get_value("providers.claude", "anthropic")
CLAUDE_API_URL = config.get_value("endpoints.claude", "https://api.anthropic.com/v1/messages")

DEEPSEEK_API_KEY = config.get_value("api_keys.deepseek", "")
DEEPSEEK_API_URL = config.get_value("endpoints.deepseek", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = config.get_value("models.deepseek", "deepseek-reasoner")

OPENAI_COMPOSITE_API_KEY = config.get_value("api_keys.openai_composite", "")
OPENAI_COMPOSITE_API_URL = config.get_value("endpoints.openai_composite", "")
OPENAI_COMPOSITE_MODEL = config.get_value("models.openai_composite", "")

IS_ORIGIN_REASONING = config.get_value("options.is_origin_reasoning", True)

# CORS设置
allow_origins_list = (
    ALLOW_ORIGINS.split(",") if ALLOW_ORIGINS else []
)  # 将逗号分隔的字符串转换为列表

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建 DeepClaude 实例, 提出为Global变量
if not DEEPSEEK_API_KEY or not CLAUDE_API_KEY:
    logger.critical("请设置环境变量 CLAUDE_API_KEY 和 DEEPSEEK_API_KEY")
    sys.exit(1)

deep_claude = DeepClaude(
    DEEPSEEK_API_KEY,
    CLAUDE_API_KEY,
    DEEPSEEK_API_URL,
    CLAUDE_API_URL,
    CLAUDE_PROVIDER,
    IS_ORIGIN_REASONING,
)

# 创建 OpenAICompatibleComposite 实例
# if not DEEPSEEK_API_KEY or not OPENAI_COMPOSITE_API_KEY:
#     logger.critical("请设置环境变量 OPENAI_COMPOSITE_API_KEY 和 DEEPSEEK_API_KEY")
#     sys.exit(1)

openai_composite = OpenAICompatibleComposite(
    DEEPSEEK_API_KEY,
    OPENAI_COMPOSITE_API_KEY,
    DEEPSEEK_API_URL,
    OPENAI_COMPOSITE_API_URL,
    IS_ORIGIN_REASONING,
)

# 验证日志级别
logger.debug("当前日志级别为 DEBUG")
logger.info("开始请求")

# 启动 Web 配置管理界面（如果启用）
if os.getenv("ENABLE_WEB_CONFIG", "false").lower() == "true":
    try:
        from app.web_config import start_web_config
        import asyncio
        web_config_port = os.getenv("WEB_CONFIG_PORT", "8080")
        web_config_path = os.getenv("WEB_CONFIG_PATH", "/admin")
        logger.info(f"启用 Web 配置管理界面: http://0.0.0.0:{web_config_port}{web_config_path}")
        asyncio.create_task(start_web_config())
    except ImportError as e:
        logger.error(f"加载 Web 配置模块失败: {e}, 请安装依赖: pip install jinja2 pyyaml uvicorn python-dotenv python-multipart")
    except Exception as e:
        logger.error(f"启动 Web 配置界面失败: {e}")

@app.get("/", dependencies=[Depends(verify_api_key)])
async def root():
    logger.info("访问了根路径")
    return {"message": "Welcome to DeepClaude API"}


@app.get("/v1/models")
async def list_models():
    """
    获取可用模型列表
    返回格式遵循 OpenAI API 标准
    """
    try:
        config = get_config()
        created_timestamp = int(time.time())
        
        # 创建标准格式的模型列表
        models_data = []
        if os.getenv("ENABLE_WEB_CONFIG", "false").lower() == "true":
            models_data.append({
                "id": "deepclaude",
                "object": "model",
                "created": created_timestamp,
                "owned_by": "deepclaude",
                "permission": [
                    {
                        "id": "modelperm-deepclaude",
                        "object": "model_permission",
                        "created": created_timestamp,
                        "allow_create_engine": False,
                        "allow_sampling": True,
                        "allow_logprobs": True,
                        "allow_search_indices": False,
                        "allow_view": True,
                        "allow_fine_tuning": False,
                        "organization": "*",
                        "group": None,
                        "is_blocking": False
                    }
                ],
                "root": "deepclaude",
                "parent": None
            })
            
            # 添加模型映射别名
            model_mappings = config.get_value("model_mappings", {})
            for alias, target_model in model_mappings.items():
                models_data.append({
                    "id": alias,
                    "object": "model",
                    "created": created_timestamp,
                    "owned_by": "deepclaude",
                    "permission": [
                        {
                            "id": f"modelperm-{alias}",
                            "object": "model_permission",
                            "created": created_timestamp,
                            "allow_create_engine": False,
                            "allow_sampling": True,
                            "allow_logprobs": True,
                            "allow_search_indices": False,
                            "allow_view": True,
                            "allow_fine_tuning": False,
                            "organization": "*",
                            "group": None,
                            "is_blocking": False
                        }
                    ],
                    "root": alias,
                    "parent": None
                })
            
            return {"object": "list", "data": models_data}
        config = load_models_config()
        return {"object": "list", "data": config["models"]}
    except Exception as e:
        logger.error(f"加载模型配置时发生错误: {e}")
        return {"error": str(e)}


@app.post("/v1/chat/completions", dependencies=[Depends(verify_api_key)])
async def chat_completions(request: Request):
    """处理聊天完成请求，支持流式和非流式输出

    请求体格式应与 OpenAI API 保持一致，包含：
    - messages: 消息列表
    - model: 模型名称（必需）
    - stream: 是否使用流式输出（可选，默认为 True)
    - temperature: 随机性 (可选)
    - top_p: top_p (可选)
    - presence_penalty: 话题新鲜度（可选）
    - frequency_penalty: 频率惩罚度（可选）
    """

    try:
        # 1. 获取基础信息
        body = await request.json()
        messages = body.get("messages")
        model = body.get("model")

        if not model:
            raise ValueError("必须指定模型名称")

        # 2. 获取并验证参数
        model_arg = get_and_validate_params(body)
        stream = model_arg[4]  # 获取 stream 参数

        # 3. 根据模型选择不同的处理方式
        if model == "deepclaude":
            # 使用 DeepClaude
            claude_model = ENV_CLAUDE_MODEL if ENV_CLAUDE_MODEL else "claude-3-5-sonnet-20241022"
            if stream:
                return StreamingResponse(
                    deep_claude.chat_completions_with_stream(
                        messages=messages,
                        model_arg=model_arg[:4],
                        deepseek_model=DEEPSEEK_MODEL,
                        claude_model=claude_model,
                    ),
                    media_type="text/event-stream",
                )
            else:
                return await deep_claude.chat_completions_without_stream(
                    messages=messages,
                    model_arg=model_arg[:4],
                    deepseek_model=DEEPSEEK_MODEL,
                    claude_model=claude_model,
                )
        else:
            # 使用 OpenAI 兼容组合模型
            if os.getenv("ENABLE_WEB_CONFIG", "false").lower() == "true":
                model_mapping = get_config().get_model_mapping(model)
            else:
                model_mapping = OPENAI_COMPOSITE_MODEL
            if stream:
                return StreamingResponse(
                    openai_composite.chat_completions_with_stream(
                        messages=messages,
                        model_arg=model_arg[:4],
                        deepseek_model=DEEPSEEK_MODEL,
                        target_model=model_mapping,
                    ),
                    media_type="text/event-stream",
                )
            else:
                return await openai_composite.chat_completions_without_stream(
                    messages=messages,
                    model_arg=model_arg[:4],
                    deepseek_model=DEEPSEEK_MODEL,
                    target_model=model_mapping,
                )

    except Exception as e:
        logger.error(f"处理请求时发生错误: {e}")
        return {"error": str(e)}


def get_and_validate_params(body):
    """提取获取和验证请求参数的函数"""
    # TODO: 默认值设定允许自定义
    temperature: float = body.get("temperature", 0.5)
    top_p: float = body.get("top_p", 0.9)
    presence_penalty: float = body.get("presence_penalty", 0.0)
    frequency_penalty: float = body.get("frequency_penalty", 0.0)
    stream: bool = body.get("stream", True)

    if "sonnet" in body.get(
        "model", ""
    ):  # Only Sonnet 设定 temperature 必须在 0 到 1 之间
        if (
            not isinstance(temperature, (float))
            or temperature < 0.0
            or temperature > 1.0
        ):
            raise ValueError("Sonnet 设定 temperature 必须在 0 到 1 之间")

    return (temperature, top_p, presence_penalty, frequency_penalty, stream)
