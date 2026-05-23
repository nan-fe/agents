import { demoShareSnapshot, isDemoShareId } from '@/lib/demo-share';
import type { ShareSnapshot } from '@/lib/share-types';

export type { ShareSnapshot } from '@/lib/share-types';

const API_BASE_URL =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  'http://localhost:8000';

export const getShareSnapshot = async (
  shareId: string
): Promise<ShareSnapshot | null> => {
  if (isDemoShareId(shareId)) {
    return demoShareSnapshot;
  }

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
