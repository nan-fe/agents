import { expect, test } from '@playwright/test';
import { registerAndEnterStudio, resetMockApi } from './helpers/auth';

test.beforeEach(async ({ page }) => {
  await resetMockApi(page);
});

test('creates share link and opens share page without errors', async ({ page }) => {
  await registerAndEnterStudio(page);

  await page.getByLabel('描述你想创作的小红书内容').fill('写一篇平价好物分享');
  await page.getByRole('button', { name: '发送' }).click();

  await expect(page.getByRole('heading', { name: 'E2E 测试种草标题' })).toBeVisible({
    timeout: 30_000,
  });

  const createShareRequestPromise = page.waitForRequest(
    (request) => request.method() === 'POST' && request.url().includes('/shares'),
  );

  await page.getByRole('button', { name: '生成分享链接' }).click();

  const createShareRequest = await createShareRequestPromise;
  expect(createShareRequest.postDataJSON()).toMatchObject({
    title: 'E2E 测试种草标题',
  });

  const createShareResponse = await page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/shares') &&
      response.status() === 200,
  );
  const { share_id: shareId } = (await createShareResponse.json()) as {
    share_id: string;
  };
  expect(shareId).toBeTruthy();

  await expect(page.getByRole('button', { name: '生成分享链接' })).toBeEnabled({
    timeout: 10_000,
  });

  const shareLink = page.locator('.result-display__share p').filter({ hasText: '/share/' });
  await expect(shareLink).toBeVisible({ timeout: 10_000 });
  const shareUrl = (await shareLink.textContent())?.trim();
  expect(shareUrl).toContain(`/share/${shareId}`);

  const sharePage = await page.context().newPage();
  const pageErrors: string[] = [];
  sharePage.on('pageerror', (error) => {
    pageErrors.push(error.message);
  });

  await sharePage.goto(shareUrl ?? `/share/${shareId}`);
  await expect(sharePage.getByRole('heading', { name: 'E2E 测试种草标题' })).toBeVisible({
    timeout: 15_000,
  });
  await expect(
    sharePage.getByText('这是一段 E2E 模拟生成的正文，用于验证流式对话与分享链路。'),
  ).toBeVisible();
  await expect(sharePage.getByText('E2E测试')).toBeVisible();
  expect(pageErrors).toEqual([]);

  await sharePage.close();
});
