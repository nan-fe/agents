
import asyncio
from langsmith import Client, wrappers
from langsmith.evaluation import aevaluate
from langchain_core.output_parsers import JsonOutputParser
from app.config import settings

import openai
from pydantic import BaseModel
from app.agents.copywriter_agent import CopywriterAgent
from dotenv import load_dotenv

load_dotenv()
# 初始化文案Agent和LangSmith客户端
copywriter_agent = CopywriterAgent()
client = Client()

# 初始化 OpenAI 客户端（用于评估）
oai_client = wrappers.wrap_openai(openai.OpenAI(
    api_key=settings.SILICONFLOW_API_KEY,
    base_url=settings.SILICONFLOW_BASE_URL,
))
# ========== 评估器定义 ==========
def relevance_evaluator(inputs: dict, outputs: dict) -> dict:
    """
    评估生成的文案是否与产品卖点、主题、用户需求相关
    """
    class ScoreResponse(BaseModel):
        score: int  # 1-5
        reason: str
    parser = JsonOutputParser(pydantic_object=ScoreResponse)
    instructions = """
你是一个专业的文案质量评估专家。请根据以下标准，评估生成的文案是否与产品卖点、主题以及用户需求强相关。

评分标准（1-5分）：
- 5分：完全覆盖所有核心卖点，紧密围绕主题，直接回应用户需求，无冗余。
- 4分：覆盖大部分核心卖点，基本围绕主题，较好回应用户需求。
- 3分：覆盖部分核心卖点，与主题相关但略有偏离，对用户需求回应一般。
- 2分：仅提及极少数卖点，主题不清晰，未有效回应用户需求。
- 1分：完全偏离主题和卖点，与用户需求无关。

严格要求：只输出 JSON 对象，不要用 markdown 代码块
请按 JSON 格式输出：{"score": 分数(1-5), "reason": "评分理由"}
    """

    # 构造 prompt
    user_msg = f"""
【核心卖点】
{', '.join(inputs['core_selling_points'])}

【主题】
{inputs['topic']}

【用户输入】
{inputs['user_input']}

【待评估文案】
{outputs['content']}
"""

    response = oai_client.beta.chat.completions.create(
        model="Pro/zai-org/GLM-5.1",
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_msg}
        ],
        temperature=0.3
    )
    raw = response.choices[0].message.content
    print("response raw",raw)
    # 处理 API 响应，添加错误处理
    try:
        result = parser.parse(raw)
        print("response result",result)
        # LangSmith 要求 score 在 0-1 之间，所以除以 5
        return {"key": "relevance", "score": result.get("score") / 5.0, "comment": result.get("reason")}
    except Exception as e:
        # 如果解析失败，返回默认分数
        return {"key": "relevance", "score": 0.5, "comment": f"评估失败: {str(e)}"}

def style_evaluator(inputs: dict, outputs: dict) -> dict:
    """
    评估文案的语言风格是否匹配 tone_style 和 target_audience
    """
    class ScoreResponse(BaseModel):
        score: int
        reason: str

    parser = JsonOutputParser(pydantic_object=ScoreResponse)    
    instructions = """
你是一个专业的品牌营销评估专家。请根据以下标准，评估文案的语言风格是否匹配指定的调性和受众。

评分标准（1-5分）：
- 5分：风格高度匹配指定调性（专业文艺），语气统一自然，对目标受众（咖啡爱好者、上班族）有很强吸引力。
- 4分：风格整体匹配，偶有轻微不一致。
- 3分：风格基本匹配，但存在明显不一致或用词不当。
- 2分：风格与指定调性存在明显偏差，语气不稳定。
- 1分：风格完全不符合调性或受众预期。

严格要求：只输出 JSON 对象，不要用 markdown 代码块
请按 JSON 格式输出：{"score": 分数, "reason": "评分理由"}
    """

    user_msg = f"""
【要求的调性风格】
{inputs['tone_style']}

【目标受众】
{', '.join(inputs['target_audience'])}

【待评估文案】
{outputs['content']}
"""

    response = oai_client.beta.chat.completions.create(
       model="Pro/zai-org/GLM-5.1",
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_msg}
        ],
        temperature =1
    )

    raw = response.choices[0].message.content

    # 处理 API 响应，添加错误处理
    try:
        result = parser.parse(raw)
        return {"key": "style_tone", "score": result.get("score") / 5.0, "comment": result.get("reason")}
    except Exception as e:
        # 如果解析失败，返回默认分数
        return {"key": "style_tone", "score": 0.5, "comment": f"评估失败: {str(e)}"}


def structure_evaluator(inputs: dict, outputs: dict) -> dict:
    """
    评估文案的结构清晰度、逻辑连贯性、阅读流畅度
    """
    class ScoreResponse(BaseModel):
        score: int
        reason: str
    
    parser = JsonOutputParser(pydantic_object=ScoreResponse)
    instructions = """
你是一个专业的文本质量评估专家。请根据以下标准，评估文案的结构与可读性。

评分标准（1-5分）：
- 5分：结构清晰（有标题/分段/重点突出），逻辑通顺，阅读体验优秀。
- 4分：结构良好，逻辑通顺，但有微小优化空间。
- 3分：结构基本合理，但逻辑不够连贯或存在冗余。
- 2分：结构混乱，逻辑跳跃较多，阅读不流畅。
- 1分：无清晰结构，逻辑不通顺，难以阅读。

请按 JSON 格式输出：{"score": 分数, "reason": "评分理由"}
    """

    user_msg = f"【待评估文案】\n{outputs['content']}"

    response = oai_client.beta.chat.completions.create(
       model="Pro/zai-org/GLM-5.1",
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_msg}
        ],
        temperature=0.3
    )

    # 处理 API 响应，添加错误处理
    raw = response.choices[0].message.content

    try:
        result = parser.parse(raw)
        return {"key": "structure_readability", "score": result.get("score") / 5.0, "comment": result.get("reason")}
    except Exception as e:
        # 如果解析失败，返回默认分数
        return {"key": "structure_readability", "score": 0.5, "comment": f"评估失败: {str(e)}"}

# ========== 目标Agent函数 ==========
async def evaluate_copywriter(input_data):
    """评估文案Agent的输出"""
    planning_result = {
        "target_audience": input_data["target_audience"],
        "core_selling_points": input_data["core_selling_points"],
        "tone_style": input_data["tone_style"],
        "topic": input_data["topic"],
        "user_input": input_data.get("user_input", "")
    }
    result = await copywriter_agent.run(planning_result)
    return {
        "title": result.title,
        "content": result.content,
        "hashtags": result.hashtags
    }

# ========== 主评估函数 ==========
async def run_evaluation():
    print("开始评估文案Agent...")
    dataset_name = "Copywriter Agent Test Set"
    results = await aevaluate(
        evaluate_copywriter,
        data=dataset_name,
        evaluators=[relevance_evaluator,style_evaluator,structure_evaluator],
        experiment_prefix="copywriter_agent_eval",
    )
    print("评估完成！")
    print(f"评估结果: {results}")

if __name__ == "__main__":
    asyncio.run(run_evaluation())