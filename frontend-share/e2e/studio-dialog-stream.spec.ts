import { test } from '@playwright/test';
import { registerAndEnterStudio, resetMockApi } from './helpers/auth';
import { sendStudioPromptAndWaitForGeneration } from './helpers/dialog';

test.beforeEach(async ({ page }) => {
  await resetMockApi(page);
});

test('studio dialog sends request and receives streaming SSE response', async ({
  page,
}) => {
  await registerAndEnterStudio(page);

  await sendStudioPromptAndWaitForGeneration(page, '帮我写一篇防晒霜种草笔记');
});
