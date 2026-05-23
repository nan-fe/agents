import type { ShareSnapshot } from '@/lib/share-types';

export const DEMO_SHARE_ID = 'demo';

export const demoShareSnapshot: ShareSnapshot = {
  id: DEMO_SHARE_ID,
  title: '学生党必入！这款平价防晒霜真的绝了 ☀️',
  content: `姐妹们！夏天来了防晒真的不能偷懒 🙌

最近挖到一款适合学生党的平价防晒霜，SPF50+ PA++++，通勤户外都够用。质地像乳液一样轻薄，上脸不搓泥、不闷痘，敏感肌也可以放心试。

✨ 我的使用感受：
· 成膜快，后续跟妆不打架
· 微微提亮，伪素颜出门很省心
· 50ml 容量耐用，性价比拉满

如果你也在找「清爽 + 平价 + 好推开」的防晒，这篇可以先马住。评论区也可以告诉我你的肤质，我再帮你细化推荐～`,
  hashtags: ['防晒霜', '学生党护肤', '平价好物', '夏日防晒', '小红书种草'],
  image_url: null,
  message: null,
  created_at: '2026-01-15T08:30:00.000Z',
  expires_at: null,
};

export const isDemoShareId = (shareId: string): boolean =>
  shareId === DEMO_SHARE_ID;
