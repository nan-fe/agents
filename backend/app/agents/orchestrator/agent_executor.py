"""Agent 执行器"""
import asyncio
from typing import Any, Callable, Dict, Optional

from app.config import settings
from app.utils.log_callback import emit_log


def _agent_timeout_seconds(agent_name: str) -> float:
    mapping: Dict[str, float] = {
        "PlannerAgent": settings.AGENT_TIMEOUT_PLANNER_AGENT_SECONDS,
        "CopywriterAgent": settings.AGENT_TIMEOUT_COPYWRITER_AGENT_SECONDS,
        "ImageAgent": settings.AGENT_TIMEOUT_IMAGE_AGENT_SECONDS,
        "ReviewerAgent": settings.AGENT_TIMEOUT_REVIEWER_AGENT_SECONDS,
        "RagAgent": settings.AGENT_TIMEOUT_RAG_AGENT_SECONDS,
    }
    return mapping.get(agent_name, 120.0)


class AgentExecutor:
    """统一的 Agent 执行管理"""

    def __init__(self, agent_map: dict):
        """
        Args:
            agent_map: Agent 映射表 {"AgentName": agent_instance}
        """
        self.agent_map = agent_map

    async def execute(
        self,
        agent_name: str,
        agent_input: Any,
        log_callback: Optional[Callable] = None,
        history: str = "",
    ) -> Any:
        """执行指定的 Agent
        
        Args:
            agent_name: Agent 名称
            agent_input: Agent 输入
            log_callback: 日志回调
            history: 历史数据
            
        Returns:
            Agent 执行结果
        """
        if agent_name not in self.agent_map:
            await emit_log(
                log_callback, agent_name, f"未知 Agent: {agent_name}，跳过"
            )
            return None

        agent = self.agent_map[agent_name]
        timeout = _agent_timeout_seconds(agent_name)
        try:
            result = await asyncio.wait_for(
                self._call_agent(
                    agent, agent_name, agent_input, log_callback, history
                ),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            msg = f"执行超时（>{timeout}s），请稍后重试"
            await emit_log(log_callback, agent_name, msg)
            raise TimeoutError(msg) from None
        except Exception:
            await emit_log(log_callback, agent_name, "执行失败，请稍后重试")
            raise

    async def _call_agent(
        self,
        agent: Any,
        agent_name: str,
        agent_input: Any,
        log_callback: Optional[Callable],
        history: str = "",
    ) -> Any:
        """调用 Agent 的 run 方法"""
        if agent_name in ("CopywriterAgent", "PlannerAgent"):
            return await agent.run(agent_input, log_callback, history=history)

        if agent_name == "ImageAgent":
            if isinstance(agent_input, dict):
                agent_input["history"] = history
            return await agent.run(agent_input, log_callback)

        return await agent.run(agent_input, log_callback)
