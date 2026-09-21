# Skill 脚本沙箱镜像。刻意与主服务镜像分开：这里没有项目代码、没有密钥，只有运行器和常用的数据处理库。
FROM python:3.12-slim

ARG PIP_INDEX_URL=https://pypi.org/simple/
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt \
    && pip freeze > /opt/installed-packages.txt

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin sandbox
COPY runner.py /opt/runner/runner.py

USER sandbox
WORKDIR /opt/runner
EXPOSE 8090
CMD ["uvicorn", "runner:app", "--host", "0.0.0.0", "--port", "8090"]
