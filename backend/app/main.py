from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
from datetime import datetime

from app.config import settings
from app.models.schemas import UserInput, SSEMessage
from app.agents.orchestrator import AgentOrchestrator

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def generate_event_stream(user_input: str):
    """生成事件流"""
    orchestrator = AgentOrchestrator()
    
    # 定义日志事件队列
    log_queue = asyncio.Queue()
    
    # 定义日志回调函数
    async def log_callback(agent_name: str, message: str):
        log_message = SSEMessage(
            type="log",
            data={
                "agent_name": agent_name,
                "message": message,
                "timestamp": datetime.now().timestamp()
            }
        )
        await log_queue.put({
            "event": "message",
            "data": log_message.model_dump_json()
        })
        await asyncio.sleep(0.1)
    
    # 执行多Agent协作
    task = asyncio.create_task(orchestrator.run(user_input, log_callback))
    
    # 发送日志事件
    while not task.done() or not log_queue.empty():
        try:
            # 尝试从队列中获取事件，最多等待1秒
            event = await asyncio.wait_for(log_queue.get(), timeout=1.0)
            yield event
            log_queue.task_done()
        except asyncio.TimeoutError:
            # 超时，继续检查任务状态
            continue
    
    # 获取多Agent协作的结果
    final_result = await task
    
    # 发送最终结果
    result_message = SSEMessage(
        type="result",
        data=final_result
    )
    yield {
        "event": "message",
        "data": result_message.model_dump_json()
    }


@app.post("/generate")
async def generate(request: Request, user_input: UserInput):
    """生成小红书内容"""
    return EventSourceResponse(
        generate_event_stream(user_input.prompt),
        media_type="text/event-stream"
    )


@app.get("/")
async def root():
    """根路径"""
    return {"message": "XHS Multi-Agent Creator API", "version": "1.0.0"}
