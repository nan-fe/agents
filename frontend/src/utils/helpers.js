/**
 * 前端辅助函数
 */

export const formatTimestamp = (timestamp) => {
  /**
   * 格式化时间戳
   * 
   * @param {number} timestamp - 时间戳
   * @returns {string} - 格式化后的时间字符串
   */
  const date = new Date(timestamp * 1000);
  return date.toLocaleTimeString('zh-CN');
};

export const truncateText = (text, maxLength = 100) => {
  /**
   * 截断文本
   * 
   * @param {string} text - 原始文本
   * @param {number} maxLength - 最大长度
   * @returns {string} - 截断后的文本
   */
  if (text.length <= maxLength) {
    return text;
  }
  return text.substring(0, maxLength) + '...';
};
