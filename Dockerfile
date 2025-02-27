# 使用官方 Python 3.11 slim 镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    DEBIAN_FRONTEND=noninteractive

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# 切换到非 root 用户
USER appuser

# 复制项目文件
COPY --chown=appuser:appuser pyproject.toml README.md ./
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser requirements.txt ./

# 安装项目依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口
EXPOSE 8000 8080

# 启动命令
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]