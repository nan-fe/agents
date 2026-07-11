"""FastAPI 应用入口。"""

from pathlib import Path

from dotenv import load_dotenv

# 尽早加载 backend/.env，确保 lark_im.settings 能读到 LARK_OAUTH_* 等变量
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from app.agents.orchestrator.agent import DialogOrchestratorAgent
from app.config import settings
from app.memory import project_memory
from app.memory.db import close_db, get_session, init_db
from app.memory.models import VersionRow
from app.memory.project_memory import should_persist_project_row
from app.models.schemas import (
    HotspotAnalyzeRequest,
    LarkOAuthRegisterRequest,
    LarkOAuthRegisterResponse,
    LarkPushReviewRequest,
    LarkStatusResponse,
    ProductInfoConfirmRequest,
    ProductInfoCreateResponse,
    ProductInfoPreviewRequest,
    ProductInfoPreviewResponse,
    ProductItem,
    ProductListResponse,
    ProjectConversationResponse,
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectFinalizeRequest,
    ProjectFinalizeResponse,
    ProjectListItem,
    ProjectListResponse,
    PublishJobResponse,
    ShareCreateRequest,
    ShareCreateResponse,
    ShareSnapshot,
    SocialStatusResponse,
    SSEMessage,
    UserInput,
    VersionSnapshot,
    WeiboLoginStartResponse,
    WeiboLoginStatusResponse,
    WeiboPublishCreateResponse,
    WeiboPublishRequest,
    XPublishCreateResponse,
    XPublishRequest,
    XOAuthStartRequest,
    XOAuthSessionResponse,
)
from app.services.dialog_stream_store import (
    DialogStream,
    StreamSubscriber,
    dialog_stream_store,
    stream_matches_request,
)
from app.services.lark_oauth_service import lark_oauth_registry
from app.services.product_info_service import ProductInfoService
from app.services.product_page_scraper import get_product_screenshot_dir
from app.services.share_service import share_store
from app.services.social.social_service import get_social_publish_service
from app.services.social.weibo_login_session import weibo_login_session_manager
from app.services.social.weibo_publisher import (
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
    invalidate_weibo_login_state_cache,
)
from app.services.social.x_login_session import x_login_session_manager
from app.services.social.x_oauth_login_session import x_oauth_login_session_manager
from app.services.social.x_oauth_service import XOAuthError, x_oauth_service
from app.services.social.x_publisher import (
    invalidate_x_login_state_cache,
)
from app.services.social.x_sync_poller import run_x_sync_once, x_sync_poller_loop
from app.services.social_hotspot import hotspot_service
from app.services.sse_resume import ResumePhase, resolve_resume_phase
from app.utils.display_labels import (
    agent_display_label,
    display_label_maps,
    intent_display_label,
)
from app.utils.retry_policy import format_agent_failure_message
from lark_im import get_lark_im_service
from lark_im.client import LarkClient
from lark_im.im_service import LarkImService
from lark_im.notify import is_lark_notify_configured
from lark_im.oauth import LarkOAuthError
from lark_im.settings import lark_settings as lark_im_settings

logger = logging.getLogger(__name__)

_SSE_HEARTBEAT_PAYLOAD = {"comment": "heartbeat"}

# 编排器单例（向量索引在 ProductRagAgent 内延后构建，避免 import 即阻塞）
orchestrator = DialogOrchestratorAgent()
product_info_service = ProductInfoService(orchestrator.rag_agent)

# 限制同时跑 orchestrator 的生成任务数；超额任务在 acquire 处排队等待
_dialog_generation_sem = asyncio.Semaphore(settings.MAX_ACTIVE_DIALOG_GENERATIONS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """后台预热 RAG 向量索引，便于就绪探针与首包体验。"""
    await init_db()

    studio_uris = (lark_im_settings.LARK_OAUTH_STUDIO_REDIRECT_URIS or "").strip()
    if studio_uris:
        try:
            await lark_oauth_registry.ensure_studio_default_client()
        except Exception:
            logger.exception("飞书 OAuth 默认 Studio 客户端注册失败")

    async def _warm_rag():
        try:
            await orchestrator.rag_agent.ensure_index_ready()
        except Exception:
            logger.exception("RAG 索引后台预热失败")

    async def _reap_stale_sse_subscribers() -> None:
        interval = settings.SSE_SUBSCRIBER_REAP_INTERVAL_SECONDS
        ttl = settings.SSE_SUBSCRIBER_IDLE_TTL_SECONDS
        while True:
            await asyncio.sleep(interval)
            try:
                reaped = await dialog_stream_store.reap_stale_subscribers(
                    idle_seconds=ttl,
                )
                if reaped:
                    logger.info("SSE 订阅回收扫描完成 reaped=%d", reaped)
            except Exception:
                logger.exception("SSE 订阅回收扫描失败")

    app.state.rag_warm_task = asyncio.create_task(_warm_rag())
    sse_reaper_task = None
    if settings.SSE_SUBSCRIBER_IDLE_TTL_SECONDS > 0:
        sse_reaper_task = asyncio.create_task(_reap_stale_sse_subscribers())
    x_sync_task = None
    if settings.X_SYNC_ENABLED:
        x_sync_task = asyncio.create_task(x_sync_poller_loop())
    yield
    t = getattr(app.state, "rag_warm_task", None)
    if t is not None and not t.done():
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
    if sse_reaper_task is not None and not sse_reaper_task.done():
        sse_reaper_task.cancel()
        try:
            await sse_reaper_task
        except asyncio.CancelledError:
            pass
    if x_sync_task is not None and not x_sync_task.done():
        x_sync_task.cancel()
        try:
            await x_sync_task
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
    intent: str | None = None,
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
    await stream.append_event({"event": "message", "data": result_message.model_dump_json()})


def _timeout_error_result() -> dict:
    return {
        "title": "",
        "content": "",
        "hashtags": [],
        "image_url": "",
        "message": ("生成失败：执行超时（常见于规划、模型调用等环节超过等待上限），请稍后重试。"),
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
    project_id: str | None = None,
    user_id: str | None = None,
) -> None:
    dialog_stream_store.mark_generation_started(session_id)

    async def log_callback(
        agent_key: str,
        message: str,
        *,
        intent: str | None = None,
    ) -> None:
        log_message = _build_log_message(agent_key, message, intent=intent)
        await stream.append_event({"event": "message", "data": log_message.model_dump_json()})

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
            except Exception as first_error:
                logger.exception(
                    "dialog generation failed session_id=%s project_id=%s user_id=%s",
                    session_id,
                    project_id,
                    user_id,
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
                except Exception as e:
                    logger.exception(
                        "dialog generation retry failed session_id=%s",
                        session_id,
                    )
                    error_text = format_agent_failure_message(e or first_error)
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
    subscriber: StreamSubscriber,
):
    heartbeat_interval = settings.SSE_HEARTBEAT_INTERVAL_SECONDS

    def _should_stop() -> bool:
        if subscriber.queue.empty() and (
            stream.is_complete or (stream.task is not None and stream.task.done())
        ):
            return True
        return False

    try:
        while True:
            if await request.is_disconnected():
                break

            if _should_stop():
                break

            try:
                event = await asyncio.wait_for(
                    subscriber.queue.get(),
                    timeout=heartbeat_interval,
                )
                subscriber.touch()
                yield _sanitize_sse_payload(event.sse_payload)
                subscriber.queue.task_done()
            except TimeoutError:
                if _should_stop():
                    break
                if await request.is_disconnected():
                    break
                subscriber.touch()
                yield _SSE_HEARTBEAT_PAYLOAD
    finally:
        await stream.unsubscribe(subscriber)


async def _start_generation_on_stream(
    stream: DialogStream,
    user_input: str,
    session_id: str,
    *,
    project_id: str | None = None,
    user_id: str | None = None,
) -> StreamSubscriber:
    stream.is_complete = False
    subscriber = await stream.subscribe()
    stream.task = asyncio.create_task(
        _run_dialog_generation(
            stream,
            user_input,
            session_id,
            project_id=project_id,
            user_id=user_id,
        )
    )
    return subscriber


async def generate_dialog_event_stream(
    request: Request,
    user_input: str,
    session_id: str,
    last_event_id: str | None = None,
    *,
    project_id: str | None = None,
    user_id: str | None = None,
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

        if not stream_matches_request(
            stream,
            user_input=user_input,
            user_id=user_id,
            project_id=project_id,
        ):
            async for event in _yield_resume_error("续传失败：请求与原始生成任务不一致。"):
                yield event
            return

        if not stream.has_event(last_event_id):
            async for event in _yield_resume_error(
                "续传失败：last_event_id 无效或已过期，请重新发起请求。"
            ):
                yield event
            return

        replay_events, subscriber = await stream.snapshot_events_after(last_event_id)
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
            await stream.unsubscribe(subscriber)
            return

        if phase is ResumePhase.ORPHAN_RESTART_FULL:
            await stream.unsubscribe(subscriber)
            logger.warning(
                "SSE 续传：后台任务已丢失，兜底重走全流程 session_id=%s last_event_id=%s replay=%d",
                session_id,
                last_event_id,
                len(replay_events),
            )
            stream = await dialog_stream_store.create_stream(
                session_id,
                user_input,
                user_id=user_id,
                project_id=project_id,
            )
            subscriber = await _start_generation_on_stream(
                stream,
                user_input,
                session_id,
                project_id=project_id,
                user_id=user_id,
            )
            async for event in _stream_subscribed_events(request, stream, subscriber):
                yield event
            return

        logger.info(
            "SSE 续传：订阅进行中的后台任务 session_id=%s last_event_id=%s",
            session_id,
            last_event_id,
        )
        async for event in _stream_subscribed_events(request, stream, subscriber):
            yield event
        return

    existing = await dialog_stream_store.get_stream(session_id)
    if (
        existing
        and not existing.is_complete
        and (existing.task is None or not existing.task.done())
        and stream_matches_request(
            existing,
            user_input=user_input,
            user_id=user_id,
            project_id=project_id,
        )
    ):
        logger.info(
            "SSE 订阅进行中的 stream session_id=%s events=%d",
            session_id,
            len(existing.events),
        )
        subscriber = await existing.subscribe()
        async for event in _stream_subscribed_events(request, existing, subscriber):
            yield event
        return

    existing = await dialog_stream_store.get_stream(session_id)
    if (
        existing
        and existing.is_complete
        and existing.has_result_event()
        and stream_matches_request(
            existing,
            user_input=user_input,
            user_id=user_id,
            project_id=project_id,
        )
    ):
        logger.info(
            "SSE 复用已完成 stream session_id=%s events=%d",
            session_id,
            len(existing.events),
        )
        async for payload in _yield_stream_events(request, existing.events):
            yield payload
        return

    stream = await dialog_stream_store.create_stream(
        session_id,
        user_input,
        user_id=user_id,
        project_id=project_id,
    )
    subscriber = await _start_generation_on_stream(
        stream,
        user_input,
        session_id,
        project_id=project_id,
        user_id=user_id,
    )

    async for event in _stream_subscribed_events(request, stream, subscriber):
        yield event


@app.get("/projects", response_model=ProjectListResponse)
async def list_projects(user_id: str | None = None):
    """进入页面时拉取项目列表，按用户最近打开时间降序，默认定位第一个。"""
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    rows = await project_memory.list_projects(user_id=uid)
    rows = [row for row in rows if should_persist_project_row(row.topic, row.final_version)]
    rows.sort(key=lambda row: (row.last_accessed_at, row.created_at), reverse=True)
    version_counts = await project_memory.version_counts(
        [row.project_id for row in rows],
        user_id=uid,
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
async def get_project_conversation(project_id: str, user_id: str | None = None):
    """加载指定 project 的对话（从 versions 重建）。"""
    project_id = (project_id or "").strip()
    uid = (user_id or "").strip()
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id 不能为空")
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    if not await project_memory.project_accessible(project_id, uid):
        raise HTTPException(status_code=404, detail="项目不存在")

    await project_memory.touch_project(project_id, user_id=uid)
    versions = await project_memory.list_versions(project_id, user_id=uid)
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
        topic=(project.topic if project and project.topic else None) or latest_label,
        final_version=(project.final_version if project else None) or latest_label,
        project_summary=project.project_summary if project else None,
        versions=snapshots,
    )


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str, user_id: str | None = None):
    """删除历史对话（project 行及全部 versions）。"""
    project_id = (project_id or "").strip()
    uid = (user_id or "").strip()
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id 不能为空")
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    if not await project_memory.delete_project(project_id, user_id=uid):
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"ok": True}


@app.post("/projects/finalize", response_model=ProjectFinalizeResponse)
async def finalize_project(payload: ProjectFinalizeRequest):
    """页面关闭或新建话题时，将 versions 汇总写入 projects 表。"""
    project_id = (payload.project_id or "").strip()
    uid = (payload.user_id or "").strip()
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id 不能为空")
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    if not await project_memory.project_accessible(project_id, uid):
        if await project_memory.project_has_versions(project_id):
            raise HTTPException(status_code=404, detail="项目不存在")
        return ProjectFinalizeResponse(
            project_id=project_id,
            finalized=False,
            version_count=0,
            message="无版本记录，跳过汇总",
        )

    versions = await project_memory.list_versions(project_id, user_id=uid)
    if not versions:
        return ProjectFinalizeResponse(
            project_id=project_id,
            finalized=False,
            version_count=0,
            message="无版本记录，跳过汇总",
        )

    row = await project_memory.finalize_project(project_id, user_id=uid)
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
        ping=settings.SSE_HEARTBEAT_INTERVAL_SECONDS,
        send_timeout=settings.SSE_SEND_TIMEOUT_SECONDS,
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


@app.post("/lark/oauth/register", response_model=LarkOAuthRegisterResponse)
async def lark_oauth_register(payload: LarkOAuthRegisterRequest):
    """动态客户端注册（DCR）：登记 redirect_uri 后用于 OAuth 授权回流。"""
    try:
        row = await lark_oauth_registry.register_client(
            client_name=payload.client_name,
            redirect_uris=payload.redirect_uris,
            scopes=payload.scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    issued_at = int(row.created_at.timestamp())
    return LarkOAuthRegisterResponse(
        client_id=row.client_id,
        client_secret=row.client_secret,
        client_id_issued_at=issued_at,
        redirect_uris=list(row.redirect_uris or []),
        scope=row.scopes,
    )


@app.get("/lark/oauth/authorize")
async def lark_oauth_authorize(
    user_id: str,
    return_url: str,
    client_id: str | None = None,
):
    """跳转飞书授权页（浏览器 302）。授权完成后回到 return_url。"""
    try:
        url = await lark_oauth_registry.start_authorize(
            client_id=client_id,
            user_id=user_id,
            return_url=return_url,
        )
    except LarkOAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url, status_code=302)


@app.get("/lark/oauth/callback")
async def lark_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """飞书 OAuth 回调：用 code 换 user_access_token 并跳回业务页。"""
    if error:
        raise HTTPException(status_code=400, detail=f"飞书授权被拒绝: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="缺少 code 或 state")

    try:
        return_url = await lark_oauth_registry.complete_callback(code, state)
    except LarkOAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    separator = "&" if "?" in return_url else "?"
    target = f"{return_url}{separator}lark_oauth=connected"
    return RedirectResponse(target, status_code=302)


@app.get("/lark/oauth/user")
async def lark_oauth_user_status(user_id: str):
    """查询用户是否已完成飞书 OAuth 授权。"""
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    return await lark_oauth_registry.user_status(uid)


@app.delete("/lark/oauth/user")
async def lark_oauth_disconnect(user_id: str):
    """解除用户飞书 OAuth 绑定。"""
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    removed = await lark_oauth_registry.disconnect_user(uid)
    return {"ok": removed}


@app.get("/lark/status", response_model=LarkStatusResponse)
async def lark_status(user_id: str | None = None):
    """飞书 bot 鉴权状态与通知群是否已配置。"""
    service = get_lark_im_service()
    auth = await service.get_auth_status()
    mode = (lark_im_settings.LARK_NOTIFY_MODE or "auto").strip().lower()
    user_oauth = None
    if user_id and user_id.strip():
        user_oauth = await lark_oauth_registry.user_status(user_id.strip())
    return LarkStatusResponse(
        auth=auth,
        notify_chat_configured=is_lark_notify_configured(),
        notify_enabled=lark_im_settings.LARK_NOTIFY_ENABLED,
        notify_mode=mode if mode in {"auto", "prompt", "off"} else "auto",
        user_oauth=user_oauth,
    )


@app.post("/lark/push-review")
async def lark_push_review(payload: LarkPushReviewRequest):
    """将审核通过内容推送到飞书通知群（须服务端已配置 LARK_*）。"""
    result: dict = {}
    version_id = (payload.version_id or "").strip()

    if version_id:
        async with get_session() as session:
            row = await session.get(VersionRow, version_id)
            if row is None:
                raise HTTPException(status_code=404, detail="版本不存在")
            stored = dict(row.result or {})
            result.update(stored)
            result.setdefault("project_id", row.project_id)
            result.setdefault("version_id", row.version_id)
            result.setdefault("version", row.version_label)

    for key in (
        "title",
        "content",
        "project_id",
        "version",
        "version_id",
        "image_url",
        "review_feedback",
    ):
        val = getattr(payload, key, None)
        if val is not None and str(val).strip():
            result[key] = val

    if payload.hashtags is not None:
        result["hashtags"] = payload.hashtags

    if not (result.get("title") or result.get("content")):
        raise HTTPException(
            status_code=400,
            detail="需提供 title/content 或有效的 version_id",
        )

    try:
        user_id = (payload.user_id or "").strip()
        if user_id:
            token = await lark_oauth_registry.get_valid_user_access_token(user_id)
            if not token:
                raise HTTPException(
                    status_code=401,
                    detail="用户未完成飞书授权，请先连接飞书账号",
                )
            user_client = LarkClient(user_access_token=token)
            user_service = LarkImService(client=user_client, use_cli=False)
            data = await user_service.send_review_notification(result)
        else:
            data = await get_lark_im_service().send_review_notification(result)
        return {"ok": True, "message_id": data.get("message_id")}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("飞书推送失败: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/social/status", response_model=SocialStatusResponse)
async def social_status(user_id: str = "", force_refresh: bool = False):
    """微博发布与 X 同步配置状态。"""
    data = await get_social_publish_service().get_status(
        user_id=user_id,
        force_refresh=force_refresh,
    )
    return SocialStatusResponse(**data)


@app.post("/social/weibo/login/start", response_model=WeiboLoginStartResponse)
async def social_weibo_login_start():
    """启动微博登录会话（打开 Profile 浏览器，用户手动完成登录）。"""
    try:
        session = await weibo_login_session_manager.start()
        state = await session.evaluate_login()
        if state["logged_in"]:
            invalidate_weibo_login_state_cache()
            from app.services.social.weibo_auth_store import save_weibo_auth

            await save_weibo_auth(
                profile_path=str(state["profile_path"]),
                logged_in=True,
                current_url=str(state["current_url"]),
            )
            await weibo_login_session_manager.close(session.session_id)
        return WeiboLoginStartResponse(
            session_id=session.session_id,
            logged_in=bool(state["logged_in"]),
            current_url=str(state["current_url"]),
            profile_path=str(state["profile_path"]),
            viewport_width=VIEWPORT_WIDTH,
            viewport_height=VIEWPORT_HEIGHT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        from app.services.social.weibo_publisher import format_weibo_browser_error

        logger.warning("微博登录会话启动失败: %s", exc)
        raise HTTPException(status_code=502, detail=format_weibo_browser_error(exc)) from exc


@app.delete("/social/weibo/login/{session_id}")
async def social_weibo_login_close(session_id: str):
    """结束可视化登录会话。"""
    await weibo_login_session_manager.close(session_id)
    return {"ok": True}


@app.post("/social/weibo/login/{session_id}/confirm", response_model=WeiboLoginStatusResponse)
async def social_weibo_login_confirm(session_id: str):
    """用户确认已在浏览器完成登录：检测并持久化 Profile。"""
    try:
        state = await weibo_login_session_manager.confirm(session_id)
        if not state["logged_in"]:
            raise HTTPException(
                status_code=400,
                detail="尚未检测到微博登录，请先在弹出的浏览器窗口完成登录",
            )
        return WeiboLoginStatusResponse(
            session_id=session_id,
            logged_in=True,
            current_url=str(state["current_url"]),
            profile_path=str(state["profile_path"]),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("微博登录确认失败: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/social/publish/weibo", response_model=WeiboPublishCreateResponse)
async def social_publish_weibo(payload: WeiboPublishRequest):
    """异步发布到微博，返回 job_id 供轮询。"""
    result: dict = {}
    version_id = (payload.version_id or "").strip()

    if version_id:
        async with get_session() as session:
            row = await session.get(VersionRow, version_id)
            if row is None:
                raise HTTPException(status_code=404, detail="版本不存在")
            stored = dict(row.result or {})
            result.update(stored)
            result.setdefault("version_id", row.version_id)

    for key in ("title", "content", "image_url", "share_url"):
        val = getattr(payload, key, None)
        if val is not None and str(val).strip():
            result[key] = val

    if payload.hashtags is not None:
        result["hashtags"] = payload.hashtags

    if payload.review_approved is not None:
        result["review_approved"] = payload.review_approved

    if not (result.get("title") or result.get("content")):
        raise HTTPException(status_code=400, detail="需提供 title/content 或有效的 version_id")

    try:
        job_id = await get_social_publish_service().start_weibo_publish(
            title=str(result.get("title") or ""),
            content=str(result.get("content") or ""),
            hashtags=result.get("hashtags"),
            image_url=result.get("image_url"),
            share_url=result.get("share_url"),
            review_approved=result.get("review_approved"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("微博发布任务创建失败: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return WeiboPublishCreateResponse(job_id=job_id, status="pending")


@app.post("/social/x/oauth/start", response_model=XOAuthSessionResponse)
async def social_x_oauth_start(payload: XOAuthStartRequest):
    """在 Playwright Profile 内启动 X OAuth 授权。"""
    uid = (payload.user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    try:
        session = await x_oauth_login_session_manager.start(user_id=uid)
        state = await session.evaluate_profile_login()
        return XOAuthSessionResponse(
            session_id=session.session_id,
            user_id=uid,
            logged_in=bool(state.get("logged_in")),
            oauth_completed=session.oauth_completed,
            oauth_error=session.oauth_error,
            x_username=session.x_username,
            current_url=str(state.get("current_url") or ""),
            profile_path=str(state.get("profile_path") or ""),
            viewport_width=VIEWPORT_WIDTH,
            viewport_height=VIEWPORT_HEIGHT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        from app.services.social.x_publisher import format_x_browser_error

        logger.warning("X OAuth 会话启动失败: %s", exc)
        raise HTTPException(status_code=502, detail=format_x_browser_error(exc)) from exc


@app.get("/social/x/oauth/session/{session_id}", response_model=XOAuthSessionResponse)
async def social_x_oauth_session_status(session_id: str):
    session = await x_oauth_login_session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="OAuth 会话不存在或已过期")
    state = await session.evaluate_profile_login()
    return XOAuthSessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        logged_in=bool(state.get("logged_in")),
        oauth_completed=session.oauth_completed,
        oauth_error=session.oauth_error,
        x_username=session.x_username,
        current_url=str(state.get("current_url") or ""),
        profile_path=str(state.get("profile_path") or ""),
        viewport_width=VIEWPORT_WIDTH,
        viewport_height=VIEWPORT_HEIGHT,
    )


@app.delete("/social/x/oauth/session/{session_id}")
async def social_x_oauth_session_close(session_id: str):
    await x_oauth_login_session_manager.close(session_id)
    return {"ok": True}


@app.post("/social/x/oauth/session/{session_id}/confirm", response_model=WeiboLoginStatusResponse)
async def social_x_oauth_session_confirm(session_id: str):
    try:
        state = await x_oauth_login_session_manager.confirm(session_id)
        return WeiboLoginStatusResponse(
            session_id=session_id,
            logged_in=True,
            current_url=str(state.get("current_url") or ""),
            profile_path=str(state.get("profile_path") or ""),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except XOAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("X OAuth 确认失败: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/social/x/oauth/callback")
async def social_x_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """X OAuth 浏览器回调页（token 交换由 Playwright 会话内监听完成）。"""
    if error:
        return HTMLResponse(
            f"<html><body><h2>授权失败</h2><p>{error}</p></body></html>",
            status_code=400,
        )
    if code and state:
        return HTMLResponse(
            "<html><body><h2>正在处理 X 授权…</h2>"
            "<p>请返回 Studio 并点击「我已完成授权」。</p></body></html>"
        )
    return HTMLResponse(
        "<html><body><h2>缺少授权参数</h2></body></html>",
        status_code=400,
    )


@app.get("/social/x/oauth/user")
async def social_x_oauth_user_status(user_id: str, force_refresh: bool = False):
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    return await get_social_publish_service().get_x_user_status(uid, force_refresh=force_refresh)


@app.delete("/social/x/oauth/user")
async def social_x_oauth_disconnect(user_id: str):
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    removed = await x_oauth_service.disconnect_user(uid)
    from app.services.social.x_auth_store import clear_x_auth

    await clear_x_auth(uid)
    invalidate_x_login_state_cache(uid)
    return {"ok": removed}


@app.post("/social/x/login/start", response_model=WeiboLoginStartResponse)
async def social_x_login_start(payload: XOAuthStartRequest):
    """Fallback：手动 Profile 登录 X（OAuth 未配置时使用）。"""
    uid = (payload.user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    try:
        session = await x_login_session_manager.start(user_id=uid)
        state = await session.evaluate_login()
        if state["logged_in"]:
            invalidate_x_login_state_cache(uid)
            from app.services.social.x_auth_store import save_x_auth

            await save_x_auth(
                user_id=uid,
                profile_path=str(state["profile_path"]),
                logged_in=True,
                current_url=str(state["current_url"]),
            )
            await x_login_session_manager.close(session.session_id)
        return WeiboLoginStartResponse(
            session_id=session.session_id,
            logged_in=bool(state["logged_in"]),
            current_url=str(state["current_url"]),
            profile_path=str(state["profile_path"]),
            viewport_width=VIEWPORT_WIDTH,
            viewport_height=VIEWPORT_HEIGHT,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        from app.services.social.x_publisher import format_x_browser_error

        logger.warning("X 登录会话启动失败: %s", exc)
        raise HTTPException(status_code=502, detail=format_x_browser_error(exc)) from exc


@app.delete("/social/x/login/{session_id}")
async def social_x_login_close(session_id: str):
    """结束 X 可视化登录会话。"""
    await x_login_session_manager.close(session_id)
    return {"ok": True}


@app.post("/social/x/login/{session_id}/confirm", response_model=WeiboLoginStatusResponse)
async def social_x_login_confirm(session_id: str):
    """用户确认已在浏览器完成 X 登录：检测并持久化 Profile。"""
    try:
        state = await x_login_session_manager.confirm(session_id)
        if not state["logged_in"]:
            raise HTTPException(
                status_code=400,
                detail="尚未检测到 X 登录，请先在弹出的浏览器窗口完成登录",
            )
        return WeiboLoginStatusResponse(
            session_id=session_id,
            logged_in=True,
            current_url=str(state["current_url"]),
            profile_path=str(state["profile_path"]),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("X 登录确认失败: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/social/publish/x", response_model=XPublishCreateResponse)
async def social_publish_x(payload: XPublishRequest):
    """异步发布到 X，返回 job_id 供轮询。"""
    result: dict = {}
    version_id = (payload.version_id or "").strip()

    if version_id:
        async with get_session() as session:
            row = await session.get(VersionRow, version_id)
            if row is None:
                raise HTTPException(status_code=404, detail="版本不存在")
            stored = dict(row.result or {})
            result.update(stored)
            result.setdefault("version_id", row.version_id)

    for key in ("title", "content", "image_url", "share_url"):
        val = getattr(payload, key, None)
        if val is not None and str(val).strip():
            result[key] = val

    if payload.hashtags is not None:
        result["hashtags"] = payload.hashtags

    if payload.review_approved is not None:
        result["review_approved"] = payload.review_approved

    if not (result.get("title") or result.get("content")):
        raise HTTPException(status_code=400, detail="需提供 title/content 或有效的 version_id")

    try:
        job_id = await get_social_publish_service().start_x_publish(
            user_id=payload.user_id,
            title=str(result.get("title") or ""),
            content=str(result.get("content") or ""),
            hashtags=result.get("hashtags"),
            image_url=result.get("image_url"),
            share_url=result.get("share_url"),
            review_approved=result.get("review_approved"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("X 发布任务创建失败: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return XPublishCreateResponse(job_id=job_id, status="pending")


@app.get("/social/publish/{job_id}", response_model=PublishJobResponse)
async def social_publish_job_status(job_id: str):
    """查询社交媒体发布任务状态（微博 / X）。"""
    job = await get_social_publish_service().get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return PublishJobResponse(**job)


@app.post("/social/sync/x")
async def social_sync_x_once():
    """手动触发一次 X → 微博同步（调试/运维）。"""
    try:
        return await run_x_sync_once()
    except Exception as exc:
        logger.warning("X 同步失败: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/social-hotspots/analyze/stream")
async def social_hotspots_analyze_stream(request: Request, payload: HotspotAnalyzeRequest):
    """SSE 流式热点分析：阶段性返回检索与大模型整合结果。"""
    if not settings.SOCIAL_HOTSPOT_ENABLED:
        raise HTTPException(status_code=503, detail="社交媒体热点分析未启用")

    async def event_generator():
        async for event in hotspot_service.stream_analysis_events(payload):
            if await request.is_disconnected():
                return
            yield event

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        ping=settings.SSE_HEARTBEAT_INTERVAL_SECONDS,
        send_timeout=settings.SSE_SEND_TIMEOUT_SECONDS,
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
