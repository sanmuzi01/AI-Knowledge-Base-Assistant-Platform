FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt
RUN python -m playwright install --with-deps chromium

COPY FasdtApi ./FasdtApi
COPY models ./models
COPY service ./service
COPY utils ./utils
COPY prompt ./prompt
COPY skills ./skills
COPY skills_packages ./skills_packages
COPY static ./static

RUN mkdir -p knowledge_files vector_db logs

EXPOSE 8000

CMD ["uvicorn", "FasdtApi.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
