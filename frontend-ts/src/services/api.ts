/**
 * API服务 - 封装SSE连接
 */

import { LogType } from "../types";

const API_BASE_URL = 'http://localhost:8000';
export type SSEType = {
    prompt:string,
    onLog:(value:LogType)=>void,
    onResult:(value:any)=>void,
    onError:(value:any)=>void,
}

export type DialogSSEType = {
    user_input: string;
    session_id: string;
    log_callback: (from: string, message: string) => void;
};

export const generateContent = async (param:SSEType) => {

   const {prompt,onLog,onResult,onError} = param;
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
    
    const reader = response?.body?.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    if(!reader) return

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        break;
      }
      
      buffer += decoder.decode(value, { stream: true });
      
      // 处理SSE消息
      const lines = buffer.split('\n');
      buffer = lines.pop()||''; // 保留最后不完整的行
      
      for (const line of lines) {
        if (line.startsWith('data:')) {
          const dataStr = line.substring(5).trim();
          if (dataStr) {
            try {
              const data = JSON.parse(dataStr);
              
              if (data.type === 'log') {
                // 处理日志信息
                onLog?.(data.data);
              } else if (data.type === 'result') {
                // 处理最终结果
                onResult?.(data.data);
              }
            } catch (error) {
              console.error('解析SSE消息失败:', error);
              onError?.(error);
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

export const generateDialogContent = async (param: DialogSSEType): Promise<any> => {
  const { user_input, session_id, log_callback } = param;
  try {
    // 使用fetch API创建SSE连接
    const response = await fetch(`${API_BASE_URL}/dialog/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ prompt:user_input, session_id })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const reader = response?.body?.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let finalResult: any = null;
    
    if(!reader) return null;

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        break;
      }
      
      buffer += decoder.decode(value, { stream: true });
      
      // 处理SSE消息
      const lines = buffer.split('\n');
      buffer = lines.pop()||''; // 保留最后不完整的行
      
      for (const line of lines) {
        if (line.startsWith('data:')) {
          const dataStr = line.substring(5).trim();
          if (dataStr) {
            try {
              const data = JSON.parse(dataStr);
              
              if (data.type === 'log') {
                // 处理日志信息
                log_callback?.(data.data.from, data.data.message);
              } else if (data.type === 'result') {
                // 处理最终结果
                finalResult = data.data;
              }
            } catch (error) {
              console.error('解析SSE消息失败:', error);
            }
          }
        }
      }
    }
    
    return finalResult;
  } catch (error) {
    console.error('SSE连接错误:', error);
    throw error;
  }
};

export const rollbackToVersion = async (session_id: string, version: number): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/session/rollback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ session_id, version })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('回退版本失败:', error);
    throw error;
  }
};

export const compareVersions = async (session_id: string, version1: number, version2: number): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/session/compare`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ session_id, version1, version2 })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('比较版本失败:', error);
    throw error;
  }
};