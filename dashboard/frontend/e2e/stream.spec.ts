import { expect, test } from '@playwright/test'

test.describe('live stream page', () => {
  test('login and stream form visible', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: /hawk-eye/i })).toBeVisible()
    await page.getByPlaceholder('username').fill('admin')
    await page.getByPlaceholder('password').fill('admin123')
    await page.getByRole('button', { name: 'Continue' }).click()
    await page.waitForURL('**/', { timeout: 15_000 })
    await page.goto('/stream', { waitUntil: 'domcontentloaded' })
    await expect(page.locator('main h1')).toContainText(/live stream/i, { timeout: 15_000 })
    await expect(page.getByRole('button', { name: 'Start streaming' })).toBeVisible()
    await expect(page.getByLabel(/generate ai report when stream completes/i)).toBeVisible()
  })
})
