import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.agents.orchestrator.agent import DialogOrchestratorAgent
from app.config import settings
from app.models.schemas import UserInput, SSEMessage

logger = logging.getLogger(__name__)

# 编排器单例（向量索引在 ProductRagAgent 内延后构建，避免 import 即阻塞）
orchestrator = DialogOrchestratorAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """后台预热 RAG 向量索引，便于就绪探针与首包体验。"""
    async def _warm_rag():
        try:
            await orchestrator.rag_agent.ensure_index_ready()
        except Exception:
            logger.exception("RAG 索引后台预热失败")

    app.state.rag_warm_task = asyncio.create_task(_warm_rag())
    yield
    t = getattr(app.state, "rag_warm_task", None)
    if t is not None and not t.done():
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """存活探针：进程已启动即可。"""
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    """就绪探针：RAG 向量索引已就绪后再接流量（Kubernetes readiness）。"""
    if orchestrator.rag_agent.is_rag_index_ready():
        return {"status": "ready"}
    detail = {
        "status": "not_ready",
        "detail": "RAG index is still building or failed",
    }
    err = getattr(orchestrator.rag_agent, "_index_error", None)
    if err:
        detail["error"] = err
    return JSONResponse(status_code=503, content=detail)


async def generate_dialog_event_stream(
    request: Request, user_input: str, session_id: str
):
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
        await event_queue.put(
            {"event": "message", "data": log_message.model_dump_json()}
        )

    task = asyncio.create_task(
        orchestrator.run(user_input, session_id, log_callback)
    )
    disconnected = False

    try:
        while True:
            if await request.is_disconnected():
                disconnected = True
                task.cancel()
                break

            if task.done() and event_queue.empty():
                break

            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=0.25)
                yield event
                await asyncio.sleep(0)
                event_queue.task_done()
            except asyncio.TimeoutError:
                if task.done() and event_queue.empty():
                    break
                continue

        if disconnected:
            try:
                await task
            except asyncio.CancelledError:
                pass
            return

        try:
            final_result = await task
        except asyncio.CancelledError:
            return
        except Exception as e:
            if isinstance(e, TimeoutError):
                error_text = (
                    "生成失败：执行超时（常见于规划、模型调用等环节超过等待上限），请稍后重试。"
                )
            else:
                detail = (str(e) or "").strip()
                if not detail and getattr(e, "args", None):
                    detail = " ".join(
                        str(a) for a in e.args if a is not None and str(a).strip()
                    ).strip()
                if not detail:
                    detail = type(e).__name__
                error_text = f"生成失败: {detail}"
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
            if isinstance(e, TimeoutError):
                final_result["error_code"] = "TIMEOUT"

        result_message = SSEMessage(type="result", data=final_result)
        yield {"event": "message", "data": result_message.model_dump_json()}
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


@app.post("/dialog/generate")
async def generateDialog(request: Request, user_input: UserInput):
    """对话式生成小红书内容"""

    return EventSourceResponse(
        generate_dialog_event_stream(
            request, user_input.prompt, user_input.session_id
        ),
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
