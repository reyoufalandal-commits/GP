import { expect, test } from '@playwright/test'

test.describe('governance fusion policy', () => {
  test('login and fusion policy JSON visible', async ({ page }) => {
    await page.goto('/login')
    await page.getByPlaceholder('username').fill('admin')
    await page.getByPlaceholder('password').fill('admin123')
    await page.getByRole('button', { name: 'Continue' }).click()
    await page.waitForURL('**/', { timeout: 15_000 })
    await page.goto('/governance', { waitUntil: 'domcontentloaded' })
    await expect(page.getByRole('heading', { name: /governance/i })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText(/policy_composite_sha256|resolved_fusion_kwargs/).first()).toBeVisible({
      timeout: 30_000,
    })
  })
})
