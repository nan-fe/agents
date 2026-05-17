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

const API_BASE_URL =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  'http://localhost:8000';

export const getShareSnapshot = async (
  shareId: string
): Promise<ShareSnapshot | null> => {
  const response = await fetch(
    `${API_BASE_URL}/shares/${encodeURIComponent(shareId)}`,
    {
      next: { revalidate: 60 },
    }
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Failed to load share ${shareId}: ${response.status}`);
  }

  return response.json();
};
