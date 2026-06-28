import { expect, test } from '@playwright/test';
import { registerAndEnterStudio, resetMockApi } from './helpers/auth';
import {
  E2E_RESULT_CONTENT,
  E2E_RESULT_TITLE,
  sendStudioPromptAndWaitForGeneration,
} from './helpers/dialog';

test.beforeEach(async ({ page }) => {
  await resetMockApi(page);
});

test('creates share link and opens share page without errors', async ({ page }) => {
  await registerAndEnterStudio(page);

  await sendStudioPromptAndWaitForGeneration(page, '写一篇平价好物分享');

  const createShareRequestPromise = page.waitForRequest(
    (request) => request.method() === 'POST' && request.url().includes('/shares'),
  );

  await page.getByRole('button', { name: '生成分享链接' }).click();

  const createShareRequest = await createShareRequestPromise;
  expect(createShareRequest.postDataJSON()).toMatchObject({
    title: E2E_RESULT_TITLE,
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
  await expect(sharePage.getByRole('heading', { name: E2E_RESULT_TITLE })).toBeVisible({
    timeout: 15_000,
  });
  await expect(sharePage.getByText(E2E_RESULT_CONTENT)).toBeVisible();
  await expect(sharePage.getByText('E2E测试')).toBeVisible();
  expect(pageErrors).toEqual([]);

  await sharePage.close();
});
