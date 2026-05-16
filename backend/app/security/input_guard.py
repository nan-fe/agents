"""Input safety checks for user prompts before they reach any agent."""

import re
from dataclasses import dataclass, field
from typing import List, Pattern


@dataclass(frozen=True)
class SafetyCheckResult:
    allowed: bool
    reason: str = ""
    category: str = ""
    matches: List[str] = field(default_factory=list)


_JAILBREAK_PATTERNS: List[Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\b(ignore|forget|disregard)\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)\b",
        r"\b(reveal|show|print|dump|leak|expose)\s+(the\s+)?(system|developer|hidden|initial)\s+(prompt|instructions?|message)\b",
        r"\b(system|developer|hidden)\s+(prompt|instructions?|message)\b",
        r"\b(prompt\s*injection|jailbreak|DAN\s*mode|do\s+anything\s+now)\b",
        r"\b(bypass|override|disable)\s+(safety|policy|guardrails?|filters?|restrictions?)\b",
        r"(忽略|无视|忘记|覆盖).{0,12}(之前|以上|前面).{0,12}(指令|规则|提示词|prompt)",
        r"(泄露|显示|打印|输出|告诉我).{0,12}(系统|开发者|隐藏|初始).{0,12}(提示词|指令|prompt)",
        r"(越权|绕过|关闭|禁用).{0,12}(安全|审核|过滤|限制|权限)",
        r"(你现在是|扮演).{0,12}(DAN|无限制|无审查|开发者模式)",
        r"(调用|使用|执行).{0,12}(敏感工具|系统命令|shell|数据库|删除|写文件)",
    ]
]

_HIGH_RISK_PATTERNS: List[Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"(违法|犯罪|诈骗|洗钱|套现|博彩|赌博|毒品|枪支|爆炸物|恐怖主义|暴恐)",
        r"(色情|成人内容|裸露|约炮|性交易)",
        r"(政治敏感|煽动|仇恨|极端主义)",
        r"(包治百病|三天瘦十斤|无效退款|特效药|神药)",
    ]
]


def _collect_matches(patterns: List[Pattern[str]], text: str) -> List[str]:
    matches: List[str] = []
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            matches.append(match.group(0))
    return matches


def check_user_input_safety(user_input: str) -> SafetyCheckResult:
    """Block obvious jailbreak, prompt injection, and high-risk generation requests."""
    text = (user_input or "").strip()
    if not text:
        return SafetyCheckResult(
            allowed=False,
            category="empty_input",
            reason="请输入想要生成的小红书文案需求。",
        )

    jailbreak_matches = _collect_matches(_JAILBREAK_PATTERNS, text)
    if jailbreak_matches:
        return SafetyCheckResult(
            allowed=False,
            category="prompt_injection",
            reason="输入疑似包含越权或 prompt injection 指令，已拒绝处理。",
            matches=jailbreak_matches,
        )

    high_risk_matches = _collect_matches(_HIGH_RISK_PATTERNS, text)
    if high_risk_matches:
        return SafetyCheckResult(
            allowed=False,
            category="high_risk_content",
            reason="输入涉及高风险或平台不适合推广的内容，已拒绝生成。",
            matches=high_risk_matches,
        )

    return SafetyCheckResult(allowed=True)


async def check_input_security(user_input: str) -> SafetyCheckResult:
    """Unified input safety entry point."""
    return check_user_input_safety(user_input)


def safety_rejection_payload(result: SafetyCheckResult) -> dict:
    """Return a stable response shape for blocked requests."""
    return {
        "title": "",
        "content": "",
        "hashtags": [],
        "image_url": "",
        "message": result.reason,
        "error_code": "SAFETY_BLOCKED",
        "safety_category": result.category,
    }
