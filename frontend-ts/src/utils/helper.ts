
export const formatTimestamp = (timestamp:number) => {

    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString('zh-CN');
  };
  
  export const truncateText = (text:string, maxLength = 100) => {
    if (text.length <= maxLength) {
      return text;
    }
    return text.substring(0, maxLength) + '...';
  };
  