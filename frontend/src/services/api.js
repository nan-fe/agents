/**
 * API服务 - 封装SSE连接
 */

const API_BASE_URL = 'http://localhost:8000';

export const generateContent = async (prompt, onLog, onResult, onError) => {
  /**
   * 生成小红书内容
   * 
   * @param {string} prompt - 用户输入的描述
   * @param {function} onLog - 日志回调函数
   * @param {function} onResult - 结果回调函数
   * @param {function} onError - 错误回调函数
   */
  
  try {
    // 使用fetch API创建SSE连接
    const response = await fetch(`${API_BASE_URL}/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ prompt })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        break;
      }
      
      buffer += decoder.decode(value, { stream: true });
      
      // 处理SSE消息
      const lines = buffer.split('\n');
      buffer = lines.pop(); // 保留最后不完整的行
      
      for (const line of lines) {
        if (line.startsWith('data:')) {
          const dataStr = line.substring(5).trim();
          if (dataStr) {
            try {
              const data = JSON.parse(dataStr);
              
              if (data.type === 'log') {
                // 处理日志信息
                onLog(data.data);
              } else if (data.type === 'result') {
                // 处理最终结果
                onResult(data.data);
              }
            } catch (error) {
              console.error('解析SSE消息失败:', error);
              onError(error);
            }
          }
        }
      }
    }
  } catch (error) {
    console.error('SSE连接错误:', error);
    onError(error);
  }
};
