import { expect, test } from '@playwright/test';

import { logoutToHome, registerAndEnterStudio } from './helpers/auth';

test('register, login, and reach studio', async ({ page }) => {
  await registerAndEnterStudio(page);
});

test('login redirects to studio', async ({ page }) => {
  const { username, password } = await registerAndEnterStudio(page);

  await logoutToHome(page);

  await page.goto('/login?returnUrl=%2Fstudio');
  await expect(page.getByLabel('账号')).toBeVisible({ timeout: 10_000 });
  await page.getByLabel('账号').fill(username);
  await page.getByLabel('密码').fill(password);
  await page.getByRole('button', { name: '登录并进入创作台' }).click();

  await expect(page).toHaveURL(/\/studio/, { timeout: 30_000 });
  await expect(page.getByText('创作画室')).toBeVisible();
});
