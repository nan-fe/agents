"""初始化 LarkImService 单例。"""

from __future__ import annotations

from lark_im import get_lark_im_service


def get_lark_im_service_singleton():
    return get_lark_im_service()


async def init_lark_stack() -> None:
    """兼容启动钩子；LarkImService 为懒加载单例，无需预热。"""
    get_lark_im_service()
