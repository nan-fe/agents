import asyncio
from app.agents.dialog_orchestrator import DialogOrchestratorAgent

async def test_orchestrator_agent():
    """测试编排器代理"""
    orchestrator_agent = DialogOrchestratorAgent()
    assert orchestrator_agent is not None