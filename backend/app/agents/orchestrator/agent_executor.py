"""Agent 执行器"""
import asyncio
from typing import Any, Callable, Dict, Optional

from app.config import settings


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
            await self._log(log_callback, f"未知 Agent: {agent_name}，跳过")
            return None

        agent = self.agent_map[agent_name]
        timeout = _agent_timeout_seconds(agent_name)
        try:
            await self._log(log_callback, f"执行 {agent_name}, input: {agent_input}")
            
            # 根据 agent 类型调用不同的方法（分级超时，避免单节点拖死整条 SSE）
            result = await asyncio.wait_for(
                self._call_agent(agent, agent_name, agent_input, history),
                timeout=timeout,
            )
            
            await self._log(log_callback, f"{agent_name} 执行成功")
            return result
        except asyncio.TimeoutError:
            msg = f"{agent_name} 执行超时（>{timeout}s）"
            await self._log(log_callback, msg)
            raise TimeoutError(msg) from None
        except Exception as e:
            await self._log(log_callback, f"{agent_name} 执行失败: {str(e)}")
            raise

    async def _call_agent(
        self,
        agent: Any,
        agent_name: str,
        agent_input: Any,
        history: str = "",
    ) -> Any:
        """调用 Agent 的 run 方法"""
        # 需要 history 参数的 Agent
        if agent_name in ("CopywriterAgent", "PlannerAgent"):
            return await agent.run(agent_input, None, history=history)
        
        # ImageAgent 需要将 history 添加到输入中
        elif agent_name == "ImageAgent":
            if isinstance(agent_input, dict):
                agent_input["history"] = history
            return await agent.run(agent_input, None)
        
        # 其他 Agent
        else:
            return await agent.run(agent_input, None)

    async def _log(self, log_callback: Optional[Callable], message: str) -> None:
        """记录日志"""
        if log_callback:
            await log_callback("Orchestrator", message)
