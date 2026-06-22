import { expect, test } from '@playwright/test';

const uniqueUsername = () => `e2e_${Date.now()}`;

test('register, login, and reach studio', async ({ page }) => {
  const username = uniqueUsername();
  const password = 'e2e-password-123';

  await page.goto('/register');
  await page.getByLabel('账号').fill(username);
  await page.getByLabel('密码', { exact: true }).fill(password);
  await page.getByLabel('确认密码').fill(password);
  await page.getByRole('button', { name: '注册并进入创作台' }).click();

  await expect(page).toHaveURL(/\/studio/, { timeout: 30_000 });
  await expect(page.getByText('创作画室')).toBeVisible();
  await expect(page.getByRole('button', { name: '新对话' })).toBeVisible();
});

test('login redirects to studio', async ({ page }) => {
  const username = uniqueUsername();
  const password = 'e2e-password-123';

  await page.goto('/register');
  await page.getByLabel('账号').fill(username);
  await page.getByLabel('密码', { exact: true }).fill(password);
  await page.getByLabel('确认密码').fill(password);
  await page.getByRole('button', { name: '注册并进入创作台' }).click();
  await expect(page).toHaveURL(/\/studio/, { timeout: 30_000 });

  await page.goto('/logout');
  await page.goto('/login?returnUrl=%2Fstudio');
  await page.getByLabel('账号').fill(username);
  await page.getByLabel('密码').fill(password);
  await page.getByRole('button', { name: '登录并进入创作台' }).click();

  await expect(page).toHaveURL(/\/studio/, { timeout: 30_000 });
  await expect(page.getByText('创作画室')).toBeVisible();
});
