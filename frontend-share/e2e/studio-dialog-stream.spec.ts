import { expect, test } from '@playwright/test';
import { registerAndEnterStudio, resetMockApi } from './helpers/auth';

test.beforeEach(async ({ page }) => {
  await resetMockApi(page);
});

test('studio dialog sends request and receives streaming SSE response', async ({
  page,
}) => {
  await registerAndEnterStudio(page);

  const prompt = '帮我写一篇防晒霜种草笔记';
  await page.getByLabel('描述你想创作的小红书内容').fill(prompt);

  const generateRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === 'POST' && request.url().includes('/dialog/generate'),
  );

  await page.getByRole('button', { name: '发送' }).click();

  const generateRequest = await generateRequestPromise;
  expect(generateRequest.postDataJSON()).toMatchObject({ prompt });

  const generateResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/dialog/generate') &&
      response.status() === 200,
  );

  const generateResponse = await generateResponsePromise;
  expect(generateResponse.headers()['content-type']).toContain('text/event-stream');

  await expect(page.getByText(/生成中/)).toBeVisible();
  await expect(page.getByText('正在分析需求…')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('heading', { name: 'E2E 测试种草标题' })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText(/生成中/)).not.toBeVisible();
});
