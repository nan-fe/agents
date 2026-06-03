from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import BaseOutputParser
from langsmith import Client, traceable
from langsmith.run_helpers import get_current_run_tree
from app.utils.token_counter import token_counter
from app.utils.retry_policy import retry_with_backoff
from app.config import settings


class LLMFactory:
    """动态LLM工厂，自动计算max_tokens并创建LLM实例"""
    _langsmith_client = Client(api_key=settings.LANGCHAIN_API_KEY)

    @staticmethod
    def _report_feedback_safe(
        *,
        key: str,
        score: float | int | bool,
        comment: str = "",
    ) -> None:
        """向 LangSmith 上报反馈；失败时静默，不影响主流程。"""
        try:
            run_tree = get_current_run_tree()
            if not run_tree:
                return
            LLMFactory._langsmith_client.create_feedback(
                run_id=run_tree.id,
                key=key,
                score=score,
                comment=comment or None,
            )
        except Exception:
            # 指标上报失败不应影响业务链路
            print(f"[LangSmith] feedback上报失败: key={key}")
            return

    @staticmethod
    def create_llm_with_dynamic_tokens(
        prompt: str,
        history: str = "",
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        safety_buffer: int = 200,
        **kwargs,
    ) -> ChatOpenAI:
        """创建带有动态max_tokens的LLM实例

        Args:
            prompt: 当前prompt文本
            history: 历史数据文本
            model_name: 模型名称，默认使用settings.BASE_MODEL
            temperature: 温度参数，默认0.7
            safety_buffer: 安全缓冲token数，默认200
            **kwargs: 其他传递给ChatOpenAI的参数

        Returns:
            配置好的ChatOpenAI实例
        """
        model = model_name or settings.BASE_MODEL
        
        # 计算输入token总数
        input_text = prompt + history
        input_tokens = token_counter.count_tokens(input_text)
        
        # 检查输入是否超限
        is_valid, total_window, max_input = token_counter.is_input_valid(
            input_tokens, model_name=model, safety_buffer=safety_buffer
        )
        
        if not is_valid:
            raise ValueError(
                f"输入Token超限！最大允许 {max_input} token，当前 {input_tokens} token。"
                f"请减少历史记录或prompt长度。"
            )
        
        # 计算最大输出token数
        max_tokens = token_counter.calculate_max_tokens(
            input_tokens=input_tokens, model_name=model, safety_buffer=safety_buffer
        )
        
        print(
            f"LLMFactory - 输入Token: {input_tokens}/{max_input}, "
            f"最大输出Token: {max_tokens}, 总窗口: {total_window}"
        )
        
        return ChatOpenAI(
            model_name=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.API_KEY,
            base_url=settings.MODEL_BASE_URL,
            **kwargs,
        )

    @staticmethod
    @traceable(name="llm_factory.run_chain_with_dynamic_tokens", run_type="chain")
    async def run_chain_with_dynamic_tokens(
        prompt_template: PromptTemplate,
        chain_input: Dict[str, Any],
        parser: Optional[BaseOutputParser] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        history: str = "",
        safety_buffer: int = 200,
        http_retry_max_attempts: Optional[int] = None,
        agent_name: str = "",
        prompt_version: str = "",
        **kwargs,
    ) -> Any:
        """使用动态max_tokens执行chain

        Args:
            prompt_template: PromptTemplate实例
            chain_input: chain的输入数据字典
            parser: 输出解析器（可选）
            model_name: 模型名称
            temperature: 温度参数
            history: 历史数据文本
            safety_buffer: 安全缓冲token数
            http_retry_max_attempts: HTTP 层重试次数；None 则用全局 LLM_HTTP_RETRY_MAX_ATTEMPTS。
                意图/路由等外层另有 asyncio.wait_for 时，应设为 1，避免退避 sleep 撑爆外层超时。
            agent_name: 当前调用的 Agent 名称（用于 LangSmith 过滤）
            prompt_version: Prompt 版本标记（用于 LangSmith 对比）
            **kwargs: 其他传递给ChatOpenAI的参数

        Returns:
            chain执行结果
        """
        # 获取格式说明（如果需要）
        format_instructions = ""
        if parser and hasattr(parser, "get_format_instructions"):
            format_instructions = parser.get_format_instructions()
        
        # 创建新的prompt模板，设置partial_variables
        partial_input = {}
        if format_instructions:
            partial_input["format_instructions"] = format_instructions
        
        prompt_to_use = prompt_template.partial(**partial_input)
        
        # 先渲染一次prompt来计算token数
        test_input = {**chain_input}
        if format_instructions:
            test_input["format_instructions"] = format_instructions
        
        rendered_prompt = prompt_template.format(**test_input)
        
        # 创建LLM实例
        llm = LLMFactory.create_llm_with_dynamic_tokens(
            prompt=rendered_prompt,
            history=history,
            model_name=model_name,
            temperature=temperature,
            safety_buffer=safety_buffer,
            **kwargs,
        )
        
        # 构建chain
        if parser:
            chain = prompt_to_use | llm | parser
        else:
            chain = prompt_to_use | llm

        metadata: Dict[str, Any] = {}
        if agent_name:
            metadata["agent_name"] = agent_name
        if prompt_version:
            metadata["prompt_version"] = prompt_version
        if model_name or settings.BASE_MODEL:
            metadata["model_name"] = model_name or settings.BASE_MODEL

        invoke_config: Dict[str, Any] = {}
        if metadata:
            invoke_config["metadata"] = metadata

        async def _ainvoke_once():
            if invoke_config:
                return await chain.ainvoke(chain_input, config=invoke_config)
            return await chain.ainvoke(chain_input)

        attempts = (
            http_retry_max_attempts
            if http_retry_max_attempts is not None
            else settings.LLM_HTTP_RETRY_MAX_ATTEMPTS
        )
        attempts = max(1, int(attempts))
        try:
            result = await retry_with_backoff(
                _ainvoke_once,
                max_attempts=attempts,
                base_delay=settings.LLM_HTTP_RETRY_BASE_DELAY,
                max_delay=settings.LLM_HTTP_RETRY_MAX_DELAY,
                operation_name="langchain_ainvoke",
            )
            if parser:
                LLMFactory._report_feedback_safe(
                    key="parse_success",
                    score=1,
                    comment=f"agent={agent_name or 'unknown'}",
                )
            return result
        except Exception:
            if parser:
                LLMFactory._report_feedback_safe(
                    key="parse_success",
                    score=0,
                    comment=f"agent={agent_name or 'unknown'}",
                )
            raise


llm_factory = LLMFactory()
