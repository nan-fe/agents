import { expect, type Page } from '@playwright/test';

export const uniqueUsername = () => `e2e_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

export const registerAndEnterStudio = async (
  page: Page,
  password = 'e2e-password-123',
) => {
  const username = uniqueUsername();

  await page.goto('/register');
  await page.getByLabel('账号').fill(username);
  await page.getByLabel('密码', { exact: true }).fill(password);
  await page.getByLabel('确认密码').fill(password);
  await page.getByRole('button', { name: '注册并进入创作台' }).click();

  await expect(page).toHaveURL(/\/studio/, { timeout: 30_000 });
  await expect(page.getByText('创作画室')).toBeVisible();
  await expect(page.getByRole('button', { name: '新对话' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '内容创作助手' })).toBeVisible({
    timeout: 15_000,
  });

  return { username, password };
};

export const resetMockApi = async (page: Page) => {
  await page.request.get('http://127.0.0.1:8000/e2e/reset');
};
