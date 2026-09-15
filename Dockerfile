# 后端镜像（api / worker 共用，靠 command 区分）。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# pdf/docx 解析、lxml、chromadb 的编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

# 先装 CPU 版 torch，避免 sentence-transformers 拖进几个 G 的 CUDA 轮子
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "FasdtApi.main:app", "--host", "0.0.0.0", "--port", "8000"]
