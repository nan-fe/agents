import { demoShareSnapshot, isDemoShareId } from '@/lib/demo-share';
import type { ShareSnapshot } from '@/lib/share-types';

/** fetch 缓存 / ISR 再验证间隔（秒），须与 share/[shareId]/page.tsx 中 `revalidate` 字面量一致 */
export const SHARE_PAGE_REVALIDATE_SECONDS = 3600;

const shareCacheTag = (shareId: string) => `share:${shareId}`;

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
      next: {
        revalidate: SHARE_PAGE_REVALIDATE_SECONDS,
        tags: [shareCacheTag(shareId)],
      },
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
