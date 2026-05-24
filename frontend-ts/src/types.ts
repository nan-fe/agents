export type LogType = {
  agent_name: string;
  message: string;
  timestamp: string;
  agent_key?: string;
  intent?: string;
  intent_label?: string;
};

export type DisplayLabelMaps = {
  intent_labels: Record<string, string>;
  agent_labels: Record<string, string>;
};
