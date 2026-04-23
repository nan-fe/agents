from typing import Optional, Callable


class BaseAgent:
    """基础Agent类"""
    
    def __init__(self, name: str, role: str):
        """初始化Agent
        
        Args:
            name: Agent名称
            role: Agent角色
        """
        self.name = name
        self.role = role
    
    async def log(self, message: str, log_callback: Optional[Callable] = None):
        """记录日志
        
        Args:
            message: 日志消息
            log_callback: 日志回调函数
        """
        if log_callback:
            await log_callback(self.name, message)
    
    async def run(self, input_data: any, log_callback: Optional[Callable] = None, **kwargs):
        """运行Agent
        
        Args:
            input_data: 输入数据
            log_callback: 日志回调函数
            **kwargs: 额外参数
            
        Returns:
            运行结果
        """
        raise NotImplementedError("子类必须实现run方法")