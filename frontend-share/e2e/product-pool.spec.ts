import { expect, test } from '@playwright/test';
import { registerAndEnterStudio, resetMockApi } from './helpers/auth';

test.beforeEach(async ({ page }) => {
  await resetMockApi(page);
});

test('product pool opens drawer, views detail, and deletes product', async ({ page }) => {
  test.setTimeout(60_000);
  await registerAndEnterStudio(page);

  await page.locator('.ant-menu').getByText('选品池').click();
  await expect(page.getByRole('heading', { name: '选品池', exact: true })).toBeVisible();
  await expect(page.getByText('E2E 测试蓝牙耳机')).toBeVisible({ timeout: 15_000 });

  await page.getByRole('button', { name: '添加商品' }).click();
  await expect(page.getByText('添加商品').first()).toBeVisible();
  await expect(
    page.getByText('粘贴淘宝、天猫或京东商品详情页链接'),
  ).toBeVisible();
  await page.getByRole('dialog', { name: '添加商品' }).getByRole('button', { name: 'Close' }).click();
  await expect(page.getByRole('dialog', { name: '添加商品' })).not.toBeVisible();

  const detailRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === 'GET' &&
      request.url().includes('/product_info/prod-e2e-1'),
  );

  await page.getByRole('button', { name: '查看 E2E 测试蓝牙耳机 详情' }).click();

  const detailRequest = await detailRequestPromise;
  expect(detailRequest.url()).toContain('/product_info/prod-e2e-1');

  await expect(page.getByRole('dialog', { name: '商品详情' })).toBeVisible();
  const detailDrawer = page.getByRole('dialog', { name: '商品详情' });
  await expect(detailDrawer.getByRole('heading', { name: 'E2E 测试蓝牙耳机' })).toBeVisible();
  await expect(detailDrawer.getByText('用于 E2E 测试的商品描述。')).toBeVisible();

  await detailDrawer.getByRole('button', { name: 'Close' }).click();
  await expect(page.getByRole('dialog', { name: '商品详情' })).not.toBeVisible();

  const deleteRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === 'DELETE' &&
      request.url().includes('/product_info/prod-e2e-1'),
  );

  await page.getByRole('button', { name: '删除 E2E 测试蓝牙耳机' }).click();
  const deleteConfirm = page.getByRole('dialog', { name: '删除商品？' });
  await expect(deleteConfirm).toBeVisible();
  await deleteConfirm.getByRole('button', { name: '删 除' }).click();

  const deleteRequest = await deleteRequestPromise;
  expect(deleteRequest.method()).toBe('DELETE');

  await expect(page.locator('.ant-table-cell').filter({ hasText: 'E2E 测试蓝牙耳机' })).toHaveCount(0, {
    timeout: 10_000,
  });
  await expect(
    page.getByText('暂无商品，点击「添加商品」从链接导入'),
  ).toBeVisible();
});
