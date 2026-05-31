"""执行上下文管理"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from app.agents.orchestrator.review_repair_router import derive_failure_category


@dataclass
class PlanningContext:
    """规划上下文"""
    topic: Optional[str] = None
    target_audience: Optional[str] = None
    core_selling_points: Optional[List[str]] = None
    tone_style: Optional[str] = None
    image_requirements: Optional[str] = None
    product_category: Optional[str] = None
    product_recommendations: Optional[List[Dict[str, Any]]] = None

    def __getitem__(self, key: str) -> Any:
        """支持字典方式访问"""
        return getattr(self, key, None)

    def get(self, key: str, default: Any = None) -> Any:
        """支持 get 方法"""
        return getattr(self, key, default)

    def model_dump(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            k: v for k, v in self.__dict__.items()
            if v is not None
        }


@dataclass
class CopywritingContext:
    """文案上下文"""
    title: str = ""
    content: str = ""
    hashtags: List[str] = field(default_factory=list)

    def model_dump(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "hashtags": self.hashtags,
        }


@dataclass
class ImageContext:
    """图片上下文"""
    image_url: str = ""
    prompt: str = ""

    def model_dump(self) -> Dict[str, Any]:
        return {
            "image_url": self.image_url,
            "prompt": self.prompt,
        }


@dataclass
class ReviewContext:
    """审核上下文"""
    approved: bool = False
    feedback: str = ""
    corrections: Optional[Dict[str, Any]] = None
    failure_category: Optional[str] = None
    review_executed: bool = False
    review_status: str = "skipped"

    def model_dump(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "approved": self.approved,
            "feedback": self.feedback,
            "review_executed": self.review_executed,
            "review_status": self.review_status,
        }
        if self.corrections:
            data["corrections"] = self.corrections
        if self.failure_category:
            data["failure_category"] = self.failure_category
        return data


class ExecutionContext:
    """统一的执行上下文管理"""

    def __init__(self):
        self.planning = PlanningContext()
        self.copywriting = CopywritingContext()
        self.image = ImageContext()
        self.review = ReviewContext()
        self.rag_context: Optional[Any] = None
        self._last_result: Optional[Dict[str, Any]] = None
        self.partial_errors: Dict[str, str] = {}
        self.executed_agents: List[str] = []
        self.review_repair_rounds: int = 0
        self.image_repair_attempts: int = 0

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典加载上下文"""
        if "planning" in data:
            plan_data = data["planning"]
            self.planning = PlanningContext(**plan_data)

        if "copywriting" in data:
            copy_data = data["copywriting"]
            self.copywriting = CopywritingContext(**copy_data)

        if "image" in data:
            img_data = data["image"]
            self.image = ImageContext(**img_data)

        if "result" in data:
            self._last_result = data["result"]

    def set_last_result(self, result: Dict[str, Any]) -> None:
        """设置上次结果（只保存引用）"""
        self._last_result = result

    def get_history_data(self) -> str:
        """按需生成历史数据字符串，不存储"""
        if not self._last_result:
            return ""
        return (
            f"上次生成的文案信息：\n"
            f"标题：{self._last_result.get('title', '')}\n"
            f"内容：{self._last_result.get('content', '')}\n"
            f"标签：{', '.join(self._last_result.get('hashtags', []))}"
        )

    def get_planning(self) -> Dict[str, Any]:
        """获取规划上下文字典"""
        return self.planning.model_dump()

    def set_planning(self, planning_result) -> None:
        """设置规划结果（支持对象或字典）"""
        if hasattr(planning_result, 'model_dump'):
            data = planning_result.model_dump()
        else:
            data = planning_result

        self.planning = PlanningContext(**{
            k: v for k, v in data.items()
            if k in PlanningContext.__dataclass_fields__
        })

    def set_copywriting(self, title: str = "", content: str = "", hashtags: List[str] = None) -> None:
        """设置文案结果"""
        self.copywriting = CopywritingContext(
            title=title,
            content=content,
            hashtags=hashtags or []
        )

    def set_copywriting_from_result(self, result) -> None:
        """从 Agent 执行结果设置文案"""
        self.copywriting = CopywritingContext(
            title=getattr(result, "title", ""),
            content=getattr(result, "content", ""),
            hashtags=getattr(result, "hashtags", []),
        )

    def set_image(self, image_url: str = "", prompt: str = "") -> None:
        """设置图片结果"""
        self.image = ImageContext(image_url=image_url, prompt=prompt)

    def set_image_from_result(self, result) -> None:
        """从 Agent 执行结果设置图片"""
        self.image = ImageContext(
            image_url=getattr(result, "image_url", ""),
            prompt=getattr(result, "prompt", ""),
        )

    def _normalize_corrections(self, corrections: Any) -> Optional[Dict[str, Any]]:
        if corrections is None:
            return None
        if hasattr(corrections, "model_dump"):
            data = corrections.model_dump(exclude_none=True)
            return data or None
        if isinstance(corrections, dict):
            cleaned = {k: v for k, v in corrections.items() if v is not None}
            return cleaned or None
        return None

    def _resolve_review_status(
        self, approved: bool, failure_category: Optional[str]
    ) -> str:
        if approved:
            return "passed"
        if failure_category == "policy_block":
            return "policy_block"
        if failure_category == "review_error":
            return "error"
        return "failed"

    def set_review_from_result(self, result) -> None:
        """从 Agent 执行结果设置审核"""
        approved = getattr(result, "approved", False)
        feedback = getattr(result, "feedback", "") or ""
        corrections = self._normalize_corrections(getattr(result, "corrections", None))
        failure_category = getattr(result, "failure_category", None)
        if not approved and not failure_category:
            failure_category = derive_failure_category(
                failure_category, feedback, corrections
            )

        self.review = ReviewContext(
            approved=approved,
            feedback=feedback,
            corrections=corrections,
            failure_category=failure_category,
            review_executed=True,
            review_status=self._resolve_review_status(approved, failure_category),
        )

    def mark_review_skipped(self) -> None:
        """Reviewer 未执行（无内容类 Agent）。"""
        self.review = ReviewContext(review_status="skipped", review_executed=False)

    def set_rag_context(self, context: Any) -> None:
        """设置 RAG 上下文"""
        self.rag_context = context

    def record_agent_executed(self, agent_name: str) -> None:
        if agent_name not in self.executed_agents:
            self.executed_agents.append(agent_name)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "planning": self.planning.model_dump(),
            "copywriting": self.copywriting.model_dump(),
            "image": self.image.model_dump(),
            "review": self.review.model_dump(),
            "rag_context": self.rag_context,
        }

    def build_final_result(self) -> Dict[str, Any]:
        """构建最终结果"""
        review = self.review
        is_policy_block = review.failure_category == "policy_block"
        is_review_error = review.review_status == "error"

        image_prompt = self.image.prompt or ""
        img_err = self.partial_errors.get("ImageAgent")

        if is_policy_block:
            image_url_val = ""
        elif self.image.image_url:
            image_url_val = self.image.image_url
        elif img_err:
            image_url_val = ""
        else:
            image_url_val = "https://via.placeholder.com/800x600"

        if is_policy_block:
            final: Dict[str, Any] = {
                "title": "",
                "content": "",
                "hashtags": [],
                "image_url": "",
                "image_prompt": "",
                "prompt": "",
                "message": review.feedback or "内容未通过审核，请更换主题或修改后重试。",
                "error_code": "POLICY_BLOCK",
            }
        else:
            final = {
                "title": self.copywriting.title or "默认标题",
                "content": self.copywriting.content or "默认内容",
                "hashtags": self.copywriting.hashtags or ["#小红书", "#推荐"],
                "image_url": image_url_val,
                "image_prompt": image_prompt,
                "prompt": image_prompt,
            }

        if review.review_executed:
            final["review_approved"] = review.approved
            final["review_feedback"] = review.feedback
            if review.failure_category:
                final["failure_category"] = review.failure_category
        if self.review_repair_rounds:
            final["review_retries"] = self.review_repair_rounds

        if is_review_error:
            final["error_code"] = "REVIEW_ERROR"
            final["message"] = review.feedback or "审核服务异常，请稍后重试。"
        elif review.review_executed and not review.approved and not is_policy_block:
            if not final.get("message"):
                final["message"] = (
                    f"内容未完全通过审核：{review.feedback}"
                    if review.feedback
                    else "内容未完全通过审核，请根据反馈修改后重试。"
                )

        if img_err:
            final["image_error_code"] = img_err
        if self.partial_errors:
            final["partial_errors"] = dict(self.partial_errors)
            if not final.get("message"):
                msgs = [f"{k}:{v}" for k, v in self.partial_errors.items()]
                final["message"] = "部分步骤失败：" + "; ".join(msgs)

        if self.planning.product_recommendations:
            final["product_recommendations"] = self.planning.product_recommendations

        return final
