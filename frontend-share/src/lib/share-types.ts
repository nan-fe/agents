export type ShareSnapshot = {
  id: string;
  title?: string;
  content?: string;
  hashtags?: string[];
  image_url?: string | null;
  message?: string | null;
  created_at: string;
  expires_at?: string | null;
};
