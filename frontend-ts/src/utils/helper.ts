export const formatTimestamp = (timestamp: number) => {
  const date = new Date(timestamp);
  return date.toLocaleString();
};

export const truncateText = (text: string, maxLength = 100) => {
  if (text.length <= maxLength) {
    return text;
  }
  return text.substring(0, maxLength) + '...';
};
