import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from app.agents.orchestrator.agent import DialogOrchestratorAgent
from app.config import settings
from app.memory import project_memory
from app.memory.project_memory import should_persist_project_row
from app.memory.db import close_db, init_db
from app.models.schemas import (
    ProjectConversationResponse,
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectListItem,
    ProjectListResponse,
    ProjectFinalizeRequest,
    ProjectFinalizeResponse,
    ProductInfoCreateRequest,
    ProductInfoCreateResponse,
    ProductInfoConfirmRequest,
    ProductInfoPreviewRequest,
    ProductInfoPreviewResponse,
    ProductItem,
    ProductListResponse,
    ShareCreateRequest,
    ShareCreateResponse,
    ShareSnapshot,
    UserInput,
    SSEMessage,
    VersionSnapshot,
)
from app.services.product_info_service import ProductInfoService
from app.services.product_page_scraper import get_product_screenshot_dir
from app.security.input_guard import check_input_security, safety_rejection_payload
from app.services.dialog_stream_store import DialogStream, dialog_stream_store
from app.services.share_service import share_store
from app.services.sse_resume import ResumePhase, resolve_resume_phase
from app.utils.display_labels import (
    agent_display_label,
    display_label_maps,
    intent_display_label,
)
from app.utils.retry_policy import classify_agent_failure

logger = logging.getLogger(__name__)

# 编排器单例（向量索引在 ProductRagAgent 内延后构建，避免 import 即阻塞）
orchestrator = DialogOrchestratorAgent()
product_info_service = ProductInfoService(orchestrator.rag_agent)

# 限制同时跑 orchestrator 的生成任务数；超额任务在 acquire 处排队等待
_dialog_generation_sem = asyncio.Semaphore(settings.MAX_ACTIVE_DIALOG_GENERATIONS)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """后台预热 RAG 向量索引，便于就绪探针与首包体验。"""
    await init_db()

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
    await close_db()


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/product-screenshots",
    StaticFiles(directory=str(get_product_screenshot_dir())),
    name="product-screenshots",
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


@app.get("/api/display-labels")
async def get_display_labels():
    """意图与 Agent 展示名映射，供前端静态拉取或调试。"""
    return display_label_maps()


def _build_log_message(
    agent_key: str,
    message: str,
    *,
    intent: Optional[str] = None,
) -> SSEMessage:
    data = {
        "from": agent_display_label(agent_key),
        "agent_key": agent_key,
        "message": message,
        "timestamp": int(datetime.now().timestamp() * 1000),
    }
    if intent is not None:
        data["intent"] = intent
        data["intent_label"] = intent_display_label(intent)
    return SSEMessage(type="log", data=data)


def _build_meta_message() -> SSEMessage:
    return SSEMessage(type="meta", data=display_label_maps())


def _sanitize_sse_payload(payload: dict) -> dict:
    """去掉 sse_starlette 运行时注入的 sep 等字段，避免回放异常。"""
    return {key: value for key, value in payload.items() if key != "sep"}


async def _yield_stream_events(
    request: Request,
    events: list,
) -> AsyncIterator[dict]:
    for event in events:
        if await request.is_disconnected():
            return
        yield _sanitize_sse_payload(event.sse_payload)
        await asyncio.sleep(0)


async def _yield_resume_error(
    message: str,
    *,
    error_code: str = "RESUME_FAILED",
) -> AsyncIterator[dict]:
    log_message = _build_log_message("Orchestrator", message)
    yield {"event": "message", "data": log_message.model_dump_json(), "id": "1"}
    result_message = SSEMessage(
        type="result",
        data={
            "title": "",
            "content": "",
            "hashtags": [],
            "image_url": "",
            "message": message,
            "error_code": error_code,
        },
    )
    yield {"event": "message", "data": result_message.model_dump_json(), "id": "2"}


async def _schedule_stream_cleanup(session_id: str, stream_token: int) -> None:
    """生成完成后延迟清理 SSE 缓冲，避免内存长期占用；若 stream 已被新任务替换则跳过。"""
    await asyncio.sleep(settings.DIALOG_STREAM_RETENTION_SECONDS)
    stream = await dialog_stream_store.get_stream(session_id)
    if stream is None or id(stream) != stream_token or not stream.is_complete:
        return
    await dialog_stream_store.remove_stream(session_id)


async def _append_result_event(stream: DialogStream, data: dict) -> None:
    result_message = SSEMessage(type="result", data=data)
    await stream.append_event(
        {"event": "message", "data": result_message.model_dump_json()}
    )


def _timeout_error_result() -> dict:
    return {
        "title": "",
        "content": "",
        "hashtags": [],
        "image_url": "",
        "message": (
            "生成失败：执行超时（常见于规划、模型调用等环节超过等待上限），请稍后重试。"
        ),
        "error_code": "TIMEOUT",
    }


def _error_result(message: str) -> dict:
    return {
        "title": "",
        "content": "",
        "hashtags": [],
        "image_url": "",
        "message": message,
    }


async def _run_dialog_generation(
    stream: DialogStream,
    user_input: str,
    session_id: str,
    *,
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    dialog_stream_store.mark_generation_started(session_id)
    async def log_callback(
        agent_key: str,
        message: str,
        *,
        intent: Optional[str] = None,
    ) -> None:
        log_message = _build_log_message(agent_key, message, intent=intent)
        await stream.append_event(
            {"event": "message", "data": log_message.model_dump_json()}
        )

    try:
        async with _dialog_generation_sem:
            await stream.append_event(
                {
                    "event": "message",
                    "data": _build_meta_message().model_dump_json(),
                }
            )

            try:
                final_result = await orchestrator.run(
                    user_input,
                    session_id,
                    log_callback,
                    project_id=project_id,
                    user_id=user_id,
                )
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                final_result = _timeout_error_result()
            except Exception:
                try:
                    final_result = await orchestrator.run(
                        user_input, session_id, log_callback
                    )
                except asyncio.CancelledError:
                    raise
                except TimeoutError:
                    final_result = _timeout_error_result()
                except Exception as e:
                    error_text = f"生成失败: {classify_agent_failure(e)}"
                    await log_callback("Orchestrator", error_text)
                    final_result = _error_result(error_text)

            await _append_result_event(stream, final_result)
    finally:
        dialog_stream_store.mark_generation_finished(session_id)
        stream.is_complete = True
        await dialog_stream_store.mark_complete(stream)
        asyncio.create_task(_schedule_stream_cleanup(session_id, id(stream)))


async def _stream_subscribed_events(
    request: Request,
    stream: DialogStream,
    subscriber_queue: asyncio.Queue,
):
    try:
        while True:
            if await request.is_disconnected():
                break

            if stream.is_complete and subscriber_queue.empty():
                break

            try:
                event = await asyncio.wait_for(subscriber_queue.get(), timeout=0.25)
                yield _sanitize_sse_payload(event.sse_payload)
                subscriber_queue.task_done()
            except asyncio.TimeoutError:
                if stream.is_complete and subscriber_queue.empty():
                    break
                continue
    finally:
        await stream.unsubscribe(subscriber_queue)


async def _start_generation_on_stream(
    stream: DialogStream,
    user_input: str,
    session_id: str,
    *,
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> asyncio.Queue:
    stream.is_complete = False
    subscriber_queue = await stream.subscribe()
    stream.task = asyncio.create_task(
        _run_dialog_generation(
            stream,
            user_input,
            session_id,
            project_id=project_id,
            user_id=user_id,
        )
    )
    return subscriber_queue


async def generate_dialog_event_stream(
    request: Request,
    user_input: str,
    session_id: str,
    last_event_id: Optional[str] = None,
    *,
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    is_resume = bool((last_event_id or "").strip())

    if is_resume:
        stream = await dialog_stream_store.get_stream(session_id)
        if stream is None:
            logger.warning("SSE 续传失败：未找到 stream session_id=%s", session_id)
            async for event in _yield_resume_error(
                "续传失败：未找到进行中的生成任务，请重新发起请求。"
            ):
                yield event
            return

        if user_input != stream.prompt:
            async for event in _yield_resume_error(
                "续传失败：请求内容与原始生成任务不一致。"
            ):
                yield event
            return

        if not stream.has_event(last_event_id):
            async for event in _yield_resume_error(
                "续传失败：last_event_id 无效或已过期，请重新发起请求。"
            ):
                yield event
            return

        replay_events, subscriber_queue = await stream.snapshot_events_after(
            last_event_id
        )
        logger.info(
            "SSE 续传 session_id=%s last_event_id=%s replay=%d complete=%s",
            session_id,
            last_event_id,
            len(replay_events),
            stream.is_complete,
        )
        async for payload in _yield_stream_events(request, replay_events):
            yield payload

        phase = resolve_resume_phase(stream)
        if phase is ResumePhase.REPLAY_DONE:
            await stream.unsubscribe(subscriber_queue)
            return

        if phase is ResumePhase.ORPHAN_RESTART_FULL:
            await stream.unsubscribe(subscriber_queue)
            logger.warning(
                "SSE 续传：后台任务已丢失，兜底重走全流程 session_id=%s last_event_id=%s replay=%d",
                session_id,
                last_event_id,
                len(replay_events),
            )
            stream = await dialog_stream_store.create_stream(session_id, user_input)
            subscriber_queue = await _start_generation_on_stream(
                stream,
                user_input,
                session_id,
                project_id=project_id,
                user_id=user_id,
            )
            async for event in _stream_subscribed_events(
                request, stream, subscriber_queue
            ):
                yield event
            return

        logger.info(
            "SSE 续传：订阅进行中的后台任务 session_id=%s last_event_id=%s",
            session_id,
            last_event_id,
        )
        async for event in _stream_subscribed_events(
            request, stream, subscriber_queue
        ):
            yield event
        return

    existing = await dialog_stream_store.get_stream(session_id)
    if (
        existing
        and existing.is_complete
        and existing.prompt == user_input
        and existing.has_result_event()
    ):
        logger.info(
            "SSE 复用已完成 stream session_id=%s events=%d",
            session_id,
            len(existing.events),
        )
        async for payload in _yield_stream_events(request, existing.events):
            yield payload
        return

    stream = await dialog_stream_store.create_stream(session_id, user_input)
    subscriber_queue = await _start_generation_on_stream(
        stream,
        user_input,
        session_id,
        project_id=project_id,
        user_id=user_id,
    )

    async for event in _stream_subscribed_events(request, stream, subscriber_queue):
        yield event


@app.get("/projects", response_model=ProjectListResponse)
async def list_projects(user_id: Optional[str] = None):
    """进入页面时拉取项目列表，按用户最近打开时间降序，默认定位第一个。"""
    rows = await project_memory.list_projects(user_id=user_id)
    rows = [
        row
        for row in rows
        if should_persist_project_row(row.topic, row.final_version)
    ]
    rows.sort(key=lambda row: (row.last_accessed_at, row.created_at), reverse=True)
    version_counts = await project_memory.version_counts(
        [row.project_id for row in rows]
    )
    items: list[ProjectListItem] = []
    for row in rows:
        count = version_counts.get(row.project_id, 0)
        items.append(
            ProjectListItem(
                project_id=row.project_id,
                topic=row.topic or "",
                final_version=row.final_version,
                project_summary=row.project_summary or "",
                version_count=count,
                updated_at=row.updated_at,
                last_accessed_at=row.last_accessed_at,
                finalized=count > 0 and bool(row.final_version),
            )
        )
    return ProjectListResponse(projects=items)


@app.post("/projects", response_model=ProjectCreateResponse)
async def create_project(payload: ProjectCreateRequest | None = None):
    """新建对话时分配 project_id；无 topic/final_version 时不写入 projects 表。"""
    body = payload or ProjectCreateRequest()
    project_id = await project_memory.create_project(user_id=body.user_id)
    return ProjectCreateResponse(project_id=project_id)


@app.get("/projects/{project_id}", response_model=ProjectConversationResponse)
async def get_project_conversation(project_id: str):
    """加载指定 project 的对话（从 versions 重建）。"""
    project_id = (project_id or "").strip()
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id 不能为空")

    await project_memory.touch_project(project_id)
    versions = await project_memory.list_versions(project_id)
    project = await project_memory.get_project(project_id)

    snapshots = [
        VersionSnapshot(
            version_id=v.version_id,
            version_label=v.version_label,
            version_number=v.version_number,
            parent_version_id=v.parent_version_id,
            summary=v.summary,
            user_input=v.user_input,
            result=v.result,
            intent=v.intent,
            created_at=v.created_at,
        )
        for v in versions
    ]

    latest_label = versions[-1].version_label if versions else None
    return ProjectConversationResponse(
        project_id=project_id,
        topic=(project.topic if project and project.topic else None)
        or latest_label,
        final_version=(project.final_version if project else None) or latest_label,
        project_summary=project.project_summary if project else None,
        versions=snapshots,
    )


@app.post("/projects/finalize", response_model=ProjectFinalizeResponse)
async def finalize_project(payload: ProjectFinalizeRequest):
    """页面关闭或新建话题时，将 versions 汇总写入 projects 表。"""
    project_id = (payload.project_id or "").strip()
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id 不能为空")

    versions = await project_memory.list_versions(project_id)
    if not versions:
        return ProjectFinalizeResponse(
            project_id=project_id,
            finalized=False,
            version_count=0,
            message="无版本记录，跳过汇总",
        )

    row = await project_memory.finalize_project(
        project_id, user_id=payload.user_id
    )
    return ProjectFinalizeResponse(
        project_id=project_id,
        finalized=row is not None,
        final_version=row.final_version if row else None,
        version_count=len(versions),
    )


@app.post("/dialog/generate")
async def generateDialog(request: Request, user_input: UserInput):
    """对话式生成小红书内容"""

    return EventSourceResponse(
        generate_dialog_event_stream(
            request,
            user_input.prompt,
            user_input.session_id,
            user_input.last_event_id,
            project_id=user_input.project_id,
            user_id=user_input.user_id,
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


@app.get("/product_info/list", response_model=ProductListResponse)
def list_product_info():
    """获取选品池商品列表。"""
    return product_info_service.list_products()


@app.post("/product_info/preview", response_model=ProductInfoPreviewResponse)
async def preview_product_info(payload: ProductInfoPreviewRequest):
    """识别商品链接信息，返回预览供用户确认（不入库）。"""
    try:
        return await product_info_service.preview_from_url(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="无法访问商品页面，请稍后重试或更换链接",
        ) from exc
    except Exception as exc:
        logger.exception("识别选品池商品失败")
        raise HTTPException(
            status_code=500,
            detail="商品信息解析失败，请稍后重试",
        ) from exc


@app.post("/product_info/confirm", response_model=ProductInfoCreateResponse)
async def confirm_product_info(payload: ProductInfoConfirmRequest):
    """确认将已识别的商品加入选品池与 RAG 索引。"""
    try:
        return await product_info_service.confirm_preview(payload.preview_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("确认选品池商品失败")
        raise HTTPException(
            status_code=500,
            detail="商品入库失败，请稍后重试",
        ) from exc


@app.post("/product_info/create", response_model=ProductInfoCreateResponse)
async def create_product_info(payload: ProductInfoCreateRequest):
    """从商品链接抓取信息并加入选品池与 RAG 索引。"""
    try:
        return await product_info_service.create_from_url(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="无法访问商品页面，请稍后重试或更换链接",
        ) from exc
    except Exception as exc:
        logger.exception("创建选品池商品失败")
        raise HTTPException(
            status_code=500,
            detail="商品信息解析失败，请稍后重试",
        ) from exc


@app.get("/product_info/{product_id}", response_model=ProductItem)
def get_product_info(product_id: str):
    """获取选品池商品详情（含头图与评论）。"""
    product = product_info_service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product


@app.delete("/product_info/{product_id}")
def delete_product_info(product_id: str):
    """从选品池删除商品。"""
    if not product_info_service.delete_product(product_id):
        raise HTTPException(status_code=404, detail="商品不存在")
    return {"ok": True}


@app.post("/shares", response_model=ShareCreateResponse)
async def create_share(payload: ShareCreateRequest):
    """保存生成结果快照，用于公开分享页读取。"""

    snapshot = share_store.create_share(payload)
    return ShareCreateResponse(share_id=snapshot.id, share=snapshot)


@app.get("/shares/{share_id}", response_model=ShareSnapshot)
async def get_share(share_id: str):
    """读取公开分享快照。"""

    snapshot = share_store.get_share(share_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Share not found")
    return snapshot


@app.get("/")
async def root():
    """根路径"""
    return {"message": "XHS Multi-Agent Creator API", "version": "1.0.0"}
