import { expect, type Page } from '@playwright/test';

export const E2E_RESULT_TITLE = 'E2E 测试种草标题';
export const E2E_RESULT_CONTENT =
  '这是一段 E2E 模拟生成的正文，用于验证流式对话与分享链路。';

export const waitForDialogGenerationComplete = async (page: Page) => {
  await expect(page.getByText(/生成中/)).toBeVisible();
  await expect(page.getByText('正在分析需求…')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole('heading', { name: E2E_RESULT_TITLE })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText(E2E_RESULT_CONTENT)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('E2E测试')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/生成中/)).not.toBeVisible();
};

export const sendStudioPromptAndWaitForGeneration = async (
  page: Page,
  prompt: string,
) => {
  await page.getByLabel('描述你想创作的小红书内容').fill(prompt);

  const generateRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === 'POST' && request.url().includes('/dialog/generate'),
  );

  await page.getByRole('button', { name: '发送' }).click();

  const generateRequest = await generateRequestPromise;
  expect(generateRequest.postDataJSON()).toMatchObject({ prompt });

  const generateResponse = await page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/dialog/generate') &&
      response.status() === 200,
  );
  expect(generateResponse.headers()['content-type']).toContain('text/event-stream');

  await waitForDialogGenerationComplete(page);
};
