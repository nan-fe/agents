const dateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
  
  /** API 时间为 UTC；无时区后缀的 ISO 字符串按 UTC 解析，避免被当成本地时间。 */
  export const parseApiDateTime = (value: number | string): Date => {
    if (typeof value === 'number') {
      return new Date(value);
    }
  
    const trimmed = value.trim();
    if (!trimmed) {
      return new Date(Number.NaN);
    }
  
    const hasTimezone =
      /[zZ]$/.test(trimmed) || /[+-]\d{2}:\d{2}$/.test(trimmed);
    if (!hasTimezone && /^\d{4}-\d{2}-\d{2}T/.test(trimmed)) {
      return new Date(`${trimmed}Z`);
    }
  
    return new Date(trimmed);
  };
  
  export const formatTimestamp = (value: number | string) => {
    const date = parseApiDateTime(value);
    if (Number.isNaN(date.getTime())) {
      return '';
    }
    return dateTimeFormatter.format(date);
  };
  
  export const truncateWithEllipsis = (text: string, maxLength = 100) => {
    if (text.length <= maxLength) {
      return text;
    }
    return `${text.slice(0, maxLength - 1)}…`;
  };