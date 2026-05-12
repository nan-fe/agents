from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import asyncio
from datetime import datetime
from app.config import settings
from app.models.schemas import UserInput, SSEMessage
from app.agents.orchestrator.agent import DialogOrchestratorAgent

# 创建FastAPI应用实例
app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# 创建Orchestrator单例（全局实例）
orchestrator = DialogOrchestratorAgent()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def generate_dialog_event_stream(user_input: str, session_id: str):
    # 使用 asyncio.Queue 但不延迟消费
    event_queue = asyncio.Queue()

    async def log_callback(agent_name: str, message: str):
        log_message = SSEMessage(
            type="log",
            data={
                "from": agent_name,
                "message": message,
                "timestamp": int(datetime.now().timestamp() * 1000),
            },
        )
        # 立即放入队列
        await event_queue.put(
            {"event": "message", "data": log_message.model_dump_json()}
        )

    # 创建任务
    task = asyncio.create_task(orchestrator.run(user_input, session_id, log_callback))

    # 立即开始消费队列，不等待超时
    while True:
        # 检查任务是否完成且队列为空
        if task.done() and event_queue.empty():
            break

        try:
            # 立即获取事件，不等待（或极短超时）
            event = await asyncio.wait_for(event_queue.get(), timeout=0.01)
            yield event
            await asyncio.sleep(0)
            event_queue.task_done()
        except asyncio.TimeoutError:
            # 如果队列为空但任务未完成，继续等待
            if task.done():
                break
            continue

    # 获取最终结果（任务异常时也返回可消费的结果，避免前端一直 loading）
    try:
        final_result = await task
    except Exception as e:
        error_text = f"生成失败: {str(e)}"
        error_log_message = SSEMessage(
            type="log",
            data={
                "from": "Orchestrator",
                "message": error_text,
                "timestamp": int(datetime.now().timestamp() * 1000),
            },
        )
        yield {"event": "message", "data": error_log_message.model_dump_json()}
        final_result = {
            "title": "",
            "content": "",
            "hashtags": [],
            "image_url": "",
            "message": error_text,
        }

    # 发送最终结果
    result_message = SSEMessage(type="result", data=final_result)
    yield {"event": "message", "data": result_message.model_dump_json()}


@app.post("/dialog/generate")
async def generateDialog(request: Request, user_input: UserInput):
    """对话式生成小红书内容"""

    return EventSourceResponse(
        generate_dialog_event_stream(user_input.prompt, user_input.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
        },
    )


@app.get("/")
async def root():
    """根路径"""
    return {"message": "XHS Multi-Agent Creator API", "version": "1.0.0"}
