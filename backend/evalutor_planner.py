import asyncio
import json
from typing import Dict, List, Any, Optional
from langsmith import Client, wrappers
from langsmith.evaluation import aevaluate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import openai
from app.config import settings
from app.agents.orchestrator.planning import ContentStrategistAgent
from dotenv import load_dotenv

load_dotenv()

# 初始化 ContentStrategistAgent 和 LangSmith 客户端
content_strategist_agent = ContentStrategistAgent()
client = Client()

# 初始化 OpenAI 客户端（用于评估）
oai_client = wrappers.wrap_openai(openai.OpenAI(
    api_key=settings.API_KEY,
    base_url=settings.MODEL_BASE_URL,
))

# ========== 评估器定义 ==========

def executability_evaluator(inputs: dict, outputs: dict) -> dict:
    """
    评估规划的步骤是否逻辑正确、可执行
    参考 SWE-Bench 的可行性评估
    """
    class ScoreResponse(BaseModel):
        score: int  # 1-5
        reason: str
        issues: List[str] = Field(default_factory=list)
    
    parser = JsonOutputParser(pydantic_object=ScoreResponse)
    
    instructions = """
        你是一个专业的任务规划评估专家。请根据以下标准，评估规划方案的可执行性和逻辑正确性。

    可执行性标准：
    - 每一步是否有明确的执行主体和具体操作
    - 步骤之间是否存在依赖关系冲突
    - 所需资源是否明确且合理
    - 是否考虑了必要的边界条件

    评分标准（1-5分）：
    - 5分：逻辑完全正确，所有步骤可立即执行，无歧义，依赖关系清晰
    - 4分：逻辑正确，步骤基本可执行，有少量细节需补充
    - 3分：逻辑基本正确，但存在部分模糊步骤或执行障碍
    - 2分：逻辑存在明显错误，多个步骤难以执行
    - 1分：逻辑混乱，大部分步骤无法执行

    严格要求：只输出 JSON 对象，不要用 markdown 代码块
    请按 JSON 格式输出：{"score": 分数(1-5), "reason": "评分理由", "issues": ["问题1", "问题2"]}
        """
        
    user_msg = f"""
        【用户任务】
        {inputs['user_input']}

        【规划方案】
        目标受众: {outputs.get('target_audience', [])}
        核心卖点: {outputs.get('core_selling_points', [])}
        语气风格: {outputs.get('tone_style', '')}
        图片需求: {outputs.get('image_requirements', '')}
        选题: {outputs.get('topic', '')}
        产品类别: {outputs.get('product_category', '')}
    """
    
    response = oai_client.beta.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_msg}
        ],
        temperature=0.3
    )
    
    raw = response.choices[0].message.content
    try:
        result = parser.parse(raw)
        return {
            "key": "executability",
            "score": result.get("score") / 5.0,
            "comment": result.get("reason")
        }
    except Exception as e:
        return {"key": "executability", "score": 0.5, "comment": f"评估失败: {str(e)}"}


def optimality_evaluator(inputs: dict, outputs: dict) -> dict:
    """
    评估给定任务，规划的步骤是否最少、最直接（最优性）
    参考 Terminal-Bench 的效率评估
    """
    class ScoreResponse(BaseModel):
        score: int  # 1-5
        reason: str
        redundant_elements: List[str] = Field(default_factory=list)
        missing_elements: List[str] = Field(default_factory=list)
    
    parser = JsonOutputParser(pydantic_object=ScoreResponse)
    
    instructions = """
    你是一个任务规划优化专家。评估规划方案是否以最少的步骤/信息完成任务目标。

    评估要点：
    1. 是否包含不必要的内容或步骤
    2. 核心卖点是否冗余或重复
    3. 目标人群是否过于宽泛或定义精准
    4. 是否遗漏了关键信息

    评分标准（1-5分）：
    - 5分：完全精简，每一步都必要且充分，无冗余
    - 4分：整体精简，有少量可优化的细小冗余
    - 3分：存在明显冗余或遗漏，可以精简20-30%
    - 2分：冗余较多或遗漏关键信息，可以精简40%以上
    - 1分：严重冗余或关键信息缺失

    请按 JSON 格式输出：{"score": 分数, "reason": "评分理由", "redundant_elements": ["冗余元素"], "missing_elements": ["缺失元素"]}
        """
    
    user_msg = f"""
    【用户任务】
    {inputs['user_input']}

    【规划方案】
    {json.dumps(outputs, ensure_ascii=False, indent=2)}
    """
    
    response = oai_client.beta.chat.completions.create(
       model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_msg}
        ],
        temperature=0.3
    )
    
    raw = response.choices[0].message.content
    try:
        result = parser.parse(raw)
        return {
            "key": "optimality",
            "score": result.get("score") / 5.0,
            "comment": result.get("reason")
        }
    except Exception as e:
        return {"key": "optimality", "score": 0.5, "comment": f"评估失败: {str(e)}"}


def adaptability_evaluator(inputs: dict, outputs: dict) -> dict:
    """
    评估当遇到意外/反馈时，能否快速调整计划
    参考 SWE-Bench Verified 的适应性评估
    """
    class ScoreResponse(BaseModel):
        score: int
        reason: str
        adaptation_quality: str  # "excellent", "good", "partial", "poor"
        unchanged_elements: List[str] = Field(default_factory=list)
    
    parser = JsonOutputParser(pydantic_object=ScoreResponse)
    
    instructions = """
评估规划方案在面对意外约束或用户反馈时的调整能力。

测试场景：
{scenario}

评估维度：
1. 是否正确识别了需要调整的部分
2. 调整后的方案是否有效解决了新约束
3. 是否保持了核心目标的完整性
4. 调整的幅度是否合理（既不过度也不不足）

评分标准（1-5分）：
- 5分：完美适应，所有必要元素都正确调整，核心目标保留
- 4分：良好适应，主要元素正确调整，有少量优化空间
- 3分：部分适应，调整了部分元素但不够全面
- 2分：适应较差，调整方向错误或忽略了关键约束
- 1分：完全未适应或调整后方案不可行

请按 JSON 格式输出：{"score": 分数, "reason": "评分理由", "adaptation_quality": "等级", "unchanged_elements": ["未调整但应调整的元素"]}
    """
    
    scenario = inputs.get('unexpected_scenario', '标准场景（无意外）')
    
    user_msg = f"""
【原始任务】
{inputs['user_input']}

{scenario}

【调整后的规划方案】
{json.dumps(outputs, ensure_ascii=False, indent=2)}
"""
    
    response = oai_client.beta.chat.completions.create(
       model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_msg}
        ],
        temperature=0.3
    )
    
    raw = response.choices[0].message.content
    try:
        result = parser.parse(raw)
        return {
            "key": "adaptability",
            "score": result.get("score") / 5.0,
            "comment": result.get("reason")
        }
    except Exception as e:
        return {"key": "adaptability", "score": 0.5, "comment": f"评估失败: {str(e)}"}
def audience_precision_evaluator(inputs: dict, outputs: dict) -> dict:
    """
    评估目标人群界定的精准度
    """
    class ScoreResponse(BaseModel):
        score: int
        reason: str
        precision_level: str  # "exact", "broad", "vague", "wrong"
    
    parser = JsonOutputParser(pydantic_object=ScoreResponse)
    
    instructions = """
评估策划方案中"目标人群"的界定是否精准。

精准度判断：
- 具体人群如有明确画像：学生党、职场新人、宝妈、健身爱好者等
- 避免过于宽泛：如"所有人"、"大众"
- 应与产品/内容自然匹配

评分标准（1-5分）：
- 5分：人群非常具体，画像清晰，匹配度高
- 4分：人群具体，匹配度良好
- 3分：人群基本合理但稍显宽泛
- 2分：人群定义模糊或匹配度低
- 1分：人群定义错误或过于宽泛

请按 JSON 格式输出：{"score": 分数, "reason": "评分理由", "precision_level": "等级"}
    """
    
    user_msg = f"""
【用户任务】
{inputs['user_input']}

【规划的目标人群】
{outputs.get('target_audience', [])}
"""
    
    response = oai_client.beta.chat.completions.create(
       model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_msg}
        ],
        temperature=0.3
    )
    
    raw = response.choices[0].message.content
    try:
        result = parser.parse(raw)
        return {
            "key": "audience_precision",
            "score": result.get("score") / 5.0,
            "comment": result.get("reason"),
        }
    except Exception as e:
        return {"key": "audience_precision", "score": 0.5, "comment": f"评估失败: {str(e)}"}


def selling_points_completeness_evaluator(inputs: dict, outputs: dict) -> dict:
    """
    评估核心卖点的完整性和突出程度
    """
    class ScoreResponse(BaseModel):
        score: int
        reason: str
        completeness: str  # "complete", "partial", "insufficient"
    
    parser = JsonOutputParser(pydantic_object=ScoreResponse)
    
    instructions = """
评估核心卖点是否充分、有说服力。

评估标准：
- 卖点是否具体、有差异化
- 是否覆盖产品的关键优势
- 是否适合目标人群

评分标准（1-5分）：
- 5分：卖点鲜明、具体、有排他性，覆盖完整
- 4分：卖点良好，略有提升空间
- 3分：卖点基本合理，但不够突出
- 2分：卖点模糊或不完整
- 1分：缺乏有效卖点

请按 JSON 格式输出：{"score": 分数, "reason": "评分理由", "completeness": "等级"}
    """
    
    user_msg = f"""
【用户任务】
{inputs['user_input']}

【核心卖点】
{outputs.get('core_selling_points', [])}
"""
    
    response = oai_client.beta.chat.completions.create(
       model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_msg}
        ],
        temperature=0.3
    )
    
    raw = response.choices[0].message.content
    try:
        result = parser.parse(raw)
        return {
            "key": "selling_points_completeness",
            "score": result.get("score") / 5.0,
            "comment": result.get("reason"),
        }
    except Exception as e:
        return {"key": "selling_points_completeness", "score": 0.5, "comment": f"评估失败: {str(e)}"}


def format_compliance_evaluator(inputs: dict, outputs: dict) -> dict:
    """
    评估输出格式是否符合 PlanningResult 规范
    """
    required_fields = [
        "target_audience", "tone_style", "core_selling_points",
        "image_requirements", "topic", "product_category"
    ]
    
    missing_fields = []
    for field in required_fields:
        if field not in outputs or outputs[field] is None:
            missing_fields.append(field)
    
    type_errors = []
    if "target_audience" in outputs and not isinstance(outputs["target_audience"], list):
        type_errors.append("target_audience 应为 list 类型")
    if "core_selling_points" in outputs and not isinstance(outputs["core_selling_points"], list):
        type_errors.append("core_selling_points 应为 list 类型")
    
    score = 1.0
    if len(missing_fields) == 0 and len(type_errors) == 0:
        score = 1.0
    elif len(missing_fields) <= 1 and len(type_errors) == 0:
        score = 0.8
    elif len(missing_fields) <= 2:
        score = 0.6
    else:
        score = 0.3
    
    comment = ""
    if missing_fields:
        comment += f"缺失字段: {missing_fields}. "
    if type_errors:
        comment += f"类型错误: {type_errors}. "
    if score == 1.0:
        comment = "格式完全符合规范"
    
    return {
        "key": "format_compliance",
        "score": score,
        "comment": comment,
    }


# ========== 适应性测试场景 ==========
class AdaptabilityScenarios:
    """参考 SWE-Bench Verified 的适应性测试场景"""
    
    BUDGET_CONSTRAINT = """
【意外约束】
用户突然告知：预算非常紧张，只能选择性价比最高的方案，无法接受任何溢价的元素。
请调整策划方案以适应这个预算约束。
"""
    
    TIME_CONSTRAINT = """
【意外约束】
用户要求：必须在24小时内完成全部内容准备，紧急程度很高。
请调整方案以适应紧急时间要求。
"""
    
    AUDIENCE_CHANGE = """
【意外反馈】
用户反馈：目标受众不是之前说的大学生，实际是35岁以上的职场高管。
请重新调整目标人群和相关卖点。
"""
    
    COMPETITOR_RESPONSE = """
【意外情况】
刚发现主要竞争对手也在推广同类产品，他们的卖点是"价格最低"。
请调整方案以避免正面竞争，突出差异化优势。
"""
    
    REGULATION_COMPLIANCE = """
【合规约束】
平台最新规定：禁止使用"最""第一""绝对"等极限词，禁止夸大宣传。
请调整方案以符合平台合规要求。
"""


# ========== 目标Agent函数 ==========
async def evaluate_planner(inputs: dict) -> dict:
    """
    评估 PlannerAgent 的输出
    支持标准评估和适应性评估
    """
    user_input = inputs["user_input"]
    history = inputs.get("history", "")
    unexpected_scenario = inputs.get("unexpected_scenario", None)
    
    # 如果有意外场景，将其添加到输入中模拟适应性
    if unexpected_scenario:
        user_input = f"{user_input}\n\n【额外要求】\n{unexpected_scenario}"
    
    try:
        result: PlanningResult = await content_strategist_agent.run(
            input_data=user_input,
            history=history
        )
        
        return {
            "target_audience": result.target_audience,
            "core_selling_points": result.core_selling_points,
            "tone_style": result.tone_style,
            "image_requirements": result.image_requirements,
            "topic": result.topic,
            "product_category": result.product_category
        }
    except Exception as e:
        # 如果出错，返回默认值以便评估继续
        return {
            "target_audience": ["通用人群"],
            "core_selling_points": ["质量好"],
            "tone_style": "亲切自然",
            "image_requirements": "产品图",
            "topic": "默认主题",
            "product_category": "默认类别",
            "_error": str(e)
        }


async def evaluate_planner_with_history(inputs: dict) -> dict:
    """
    带历史数据的 PlannerAgent 评估
    测试自适应性：根据历史反馈调整计划
    """
    user_input = inputs["user_input"]
    history = inputs.get("history", "")
    
    # 模拟多轮迭代
    # 第一轮：初始计划
    first_result = await content_strategist_agent.run(
        input_data=user_input,
        history=""
    )
    
    # 模拟用户反馈
    feedback = inputs.get("user_feedback", "")
    
    # 第二轮：根据反馈调整
    if feedback:
        adjusted_input = f"{user_input}\n\n【用户反馈】\n{feedback}"
        second_result = await content_strategist_agent.run(
            input_data=adjusted_input,
            history=f"上一轮计划：{first_result.topic}"
        )
        result = second_result
    else:
        result = first_result
    
    return {
        "target_audience": result.target_audience,
        "core_selling_points": result.core_selling_points,
        "tone_style": result.tone_style,
        "image_requirements": result.image_requirements,
        "topic": result.topic,
        "product_category": result.product_category,
        "previous_topic": getattr(first_result, "topic", "") if feedback else ""
    }


# ========== 测试数据集定义 ==========
def create_test_dataset():
    """
    创建测试数据集
    参考 SWE-Bench 的测试集结构
    """
    dataset_name = "Planner Agent Evaluation Suite"
    
    # 检查数据集是否存在
    try:
        dataset = client.read_dataset(dataset_name=dataset_name)
        print(f"数据集 '{dataset_name}' 已存在")
        return dataset
    except Exception:
        print(f"创建数据集 '{dataset_name}'...")
        
        test_cases = [
            {
                "user_input": "帮我策划一篇年轻人用的无线耳机种草笔记",
                "expected_hallmarks": ["学生党", "音质", "性价比"],
                "difficulty": "easy",
                "category": "e-commerce"
            },
            {
                "user_input": "写一篇适合敏感肌的面霜推广，预算有限",
                "expected_hallmarks": ["敏感肌", "温和", "平价"],
                "difficulty": "medium",
                "category": "beauty"
            },
            {
                "user_input": "策划一篇高端商务笔记本的内容，面向企业采购人员",
                "expected_hallmarks": ["商务", "企业", "专业"],
                "difficulty": "medium",
                "category": "electronics"
            },
            {
                "user_input": "推广一款健身蛋白粉，目标人群是健身新手，要强调安全性",
                "expected_hallmarks": ["健身新手", "安全", "入门"],
                "difficulty": "easy",
                "category": "health"
            },
            {
                "user_input": "儿童学习平板的推广，家长最关心护眼和学习资源",
                "expected_hallmarks": ["家长", "护眼", "学习资源"],
                "difficulty": "easy",
                "category": "education"
            },
            {
                "user_input": "高端旅行箱推广，要突出轻便和耐用，面向经常出差的人",
                "expected_hallmarks": ["出差", "轻便", "耐用"],
                "difficulty": "medium",
                "category": "travel"
            },
            {
                "user_input": "新品牌手冲咖啡器具推广，需要建立专业形象",
                "expected_hallmarks": ["咖啡爱好者", "专业", "仪式感"],
                "difficulty": "hard",
                "category": "food"
            }
        ]
        
        # 添加适应性测试用例
        adaptability_cases = [
            {
                "user_input": "推广一款200元左右的蓝牙耳机",
                "unexpected_scenario": AdaptabilityScenarios.BUDGET_CONSTRAINT,
                "difficulty": "hard",
                "category": "adaptability",
                "test_adaptability": True
            },
            {
                "user_input": "策划美妆产品的上市推广",
                "unexpected_scenario": AdaptabilityScenarios.COMPETITOR_RESPONSE,
                "difficulty": "hard",
                "category": "adaptability",
                "test_adaptability": True
            },
            {
                "user_input": "保健品推广，要强调功效",
                "unexpected_scenario": AdaptabilityScenarios.REGULATION_COMPLIANCE,
                "difficulty": "hard",
                "category": "adaptability",
                "test_adaptability": True
            }
        ]
        
        all_cases = test_cases + adaptability_cases
        
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description="PlannerAgent 综合评估测试集 - 评估可执行性、最优性、自适应性",
        )
        
        for case in all_cases:
            client.create_example(
                inputs={"user_input": case["user_input"]},
                outputs={"expected": case.get("expected_hallmarks", [])},
                dataset_id=dataset.id,
                metadata={
                    "difficulty": case.get("difficulty", "medium"),
                    "category": case.get("category", "general"),
                    "test_adaptability": case.get("test_adaptability", False)
                }
            )
        
        print(f"数据集创建完成，共 {len(all_cases)} 个测试用例")
        return dataset


# ========== 主评估函数 ==========
async def run_standard_evaluation():
    """
    运行标准评估 - 评估可执行性、最优性
    """
    print("=" * 60)
    print("开始 PlannerAgent 标准评估...")
    print("评估维度：可执行性、最优性、格式规范、受众精准度、卖点完整性")
    print("=" * 60)
    
    dataset_name = "Planner Agent Evaluation Suite"
    
    # 确保数据集存在
    create_test_dataset()
    
    results = await aevaluate(
        evaluate_planner,
        data=dataset_name,
        evaluators=[
            executability_evaluator,
            optimality_evaluator,
            format_compliance_evaluator,
            audience_precision_evaluator,
            selling_points_completeness_evaluator
        ],
        experiment_prefix="planner_agent_standard_eval",
        metadata={
            "evaluation_type": "standard",
            "evaluated_dimensions": ["executability", "optimality", "format", "audience", "selling_points"]
        }
    )
    
    print("\n" + "=" * 60)
    print("标准评估完成！")
    print("=" * 60)
    
    return results


async def run_adaptability_evaluation():
    """
    运行适应性评估 - 测试意外场景下的调整能力
    参考 SWE-Bench Verified
    """
    print("=" * 60)
    print("开始 PlannerAgent 适应性评估...")
    print("测试场景：预算约束、竞品应对、合规调整")
    print("=" * 60)
    
    # 创建适应性测试专用数据集
    adaptability_dataset_name = "Planner Agent Adaptability Test"
    
    try:
        dataset = client.read_dataset(dataset_name=adaptability_dataset_name)
    except Exception:
        dataset = client.create_dataset(
            dataset_name=adaptability_dataset_name,
            description="PlannerAgent 适应性评估 - 意外场景测试"
        )
        
        adaptability_tests = [
            {
                "user_input": "推广一款200元左右的蓝牙耳机，主打性价比",
                "unexpected_scenario": AdaptabilityScenarios.BUDGET_CONSTRAINT,
                "metadata": {"scenario": "budget_constraint"}
            },
            {
                "user_input": "策划中端价位护肤品的上市推广，主打天然成分",
                "unexpected_scenario": AdaptabilityScenarios.COMPETITOR_RESPONSE,
                "metadata": {"scenario": "competitor_response"}
            },
            {
                "user_input": "保健品推广，要强调功效和用户见证",
                "unexpected_scenario": AdaptabilityScenarios.REGULATION_COMPLIANCE,
                "metadata": {"scenario": "regulation_compliance"}
            },
            {
                "user_input": "策划一个高端品牌的新品发布会内容",
                "unexpected_scenario": AdaptabilityScenarios.TIME_CONSTRAINT,
                "metadata": {"scenario": "time_constraint"}
            },
            {
                "user_input": "大学生笔记本电脑的推广文案",
                "unexpected_scenario": AdaptabilityScenarios.AUDIENCE_CHANGE,
                "metadata": {"scenario": "audience_change"}
            }
        ]
        
        for test in adaptability_tests:
            client.create_example(
                inputs={
                    "user_input": test["user_input"],
                    "unexpected_scenario": test["unexpected_scenario"]
                },
                outputs={},
                dataset_id=dataset.id,
                metadata=test["metadata"]
            )
    
    results = await aevaluate(
        evaluate_planner,
        data=adaptability_dataset_name,
        evaluators=[adaptability_evaluator, executability_evaluator, optimality_evaluator],
        experiment_prefix="planner_agent_adaptability_eval",
        metadata={
            "evaluation_type": "adaptability",
            "reference": "SWE-Bench Verified"
        }
    )
    
    print("\n" + "=" * 60)
    print("适应性评估完成！")
    print("=" * 60)
    
    return results


async def run_iterative_evaluation():
    """
    运行迭代评估 - 测试多轮对话中的自适应性
    类似 Terminal-Bench 的交互式评估
    """
    print("=" * 60)
    print("开始 PlannerAgent 迭代评估...")
    print("测试场景：根据用户反馈调整计划")
    print("=" * 60)
    
    dataset_name = "Planner Agent Iterative Test"
    
    try:
        dataset = client.read_dataset(dataset_name=dataset_name)
    except Exception:
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description="PlannerAgent 迭代评估 - 多轮反馈测试"
        )
        
        iterative_tests = [
            {
                "user_input": "推广一款智能手表",
                "user_feedback": "目标用户不是年轻人，是50岁以上的健康监测需求者",
                "difficulty": "medium"
            },
            {
                "user_input": "策划一篇咖啡机的种草笔记",
                "user_feedback": "定价是5000元高端款，不是平价款，要突出专业感",
                "difficulty": "medium"
            },
            {
                "user_input": "儿童编程玩具推广",
                "user_feedback": "家长反馈价格太高了，需要补充性价比方面的说明",
                "difficulty": "hard"
            }
        ]
        
        for test in iterative_tests:
            client.create_example(
                inputs={
                    "user_input": test["user_input"],
                    "user_feedback": test["user_feedback"]
                },
                outputs={},
                dataset_id=dataset.id,
                metadata={"difficulty": test["difficulty"]}
            )
    
    results = await aevaluate(
        evaluate_planner_with_history,
        data=dataset_name,
        evaluators=[
            adaptability_evaluator,
            optimality_evaluator,
            audience_precision_evaluator
        ],
        experiment_prefix="planner_agent_iterative_eval",
        metadata={
            "evaluation_type": "iterative",
            "reference": "Terminal-Bench"
        }
    )
    
    print("\n" + "=" * 60)
    print("迭代评估完成！")
    print("=" * 60)
    
    return results


async def run_full_evaluation():
    """
    运行完整评估套件
    """
    print("\n" + "=" * 60)
    print("PlannerAgent 完整评估套件")
    print("=" * 60)
    print("评估维度：")
    print("  1. 可执行性 - 步骤逻辑正确、可执行")
    print("  2. 最优性 - 步骤最少、最直接")
    print("  3. 自适应性 - 意外场景下的调整能力")
    print("  4. 迭代适应性 - 多轮反馈中的调整能力")
    print("  5. 格式规范 - 输出格式正确性")
    print("  6. 受众精准度 - 目标人群界定的准确性")
    print("  7. 卖点完整性 - 核心卖点的完整程度")
    print("=" * 60)
    
    # 运行各类评估
    standard_results = await run_standard_evaluation()
    adaptability_results = await run_adaptability_evaluation()
    iterative_results = await run_iterative_evaluation()
    
    # 汇总报告
    print("\n" + "=" * 60)
    print("评估汇总报告")
    print("=" * 60)
    print("\n各评估任务已完成，详细结果请查看 LangSmith 控制台")
    print(f"标准评估实验: planner_agent_standard_eval")
    print(f"适应性评估实验: planner_agent_adaptability_eval")
    print(f"迭代评估实验: planner_agent_iterative_eval")
    
    return {
        "standard": standard_results,
        "adaptability": adaptability_results,
        "iterative": iterative_results
    }


# ========== 命令行入口 ==========
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PlannerAgent 评估工具")
    parser.add_argument("--mode", type=str, default="full",
                        choices=["full", "standard", "adaptability", "iterative"],
                        help="评估模式")
    
    args = parser.parse_args()
    
    if args.mode == "standard":
        asyncio.run(run_standard_evaluation())
    elif args.mode == "adaptability":
        asyncio.run(run_adaptability_evaluation())
    elif args.mode == "iterative":
        asyncio.run(run_iterative_evaluation())
    else:
        asyncio.run(run_full_evaluation())