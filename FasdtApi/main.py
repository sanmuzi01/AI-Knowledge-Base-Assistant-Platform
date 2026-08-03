from pathlib import Path
from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from FasdtApi.login import router as login_router
from FasdtApi.agent import router as agent_router
app = FastAPI()

# 用绝对路径挂载 static 目录，避免依赖启动时的工作目录
BASE_DIR = Path(__file__).resolve().parent.parent
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='my_static')
app.include_router(login_router)
app.include_router(agent_router)
@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
