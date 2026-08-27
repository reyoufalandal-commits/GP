import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const thisDir = path.dirname(fileURLToPath(import.meta.url))
const sampleRowsJson = path.join(thisDir, 'fixtures', 'sample-rows.json')

test.describe('dashboard smoke', () => {
  test('start hub shows checklist and links', async ({ page }) => {
    await page.goto('/login')
    await page.getByPlaceholder('username').fill('admin')
    await page.getByPlaceholder('password').fill('admin123')
    await page.getByRole('button', { name: 'Continue' }).click()
    // Wait until session is established (same as the flow below); otherwise goto('/start') can race the login request.
    await expect(page.getByRole('heading', { name: 'Model lab' })).toBeVisible({ timeout: 15_000 })
    await page.goto('/start')
    await expect(page.getByRole('heading', { name: 'Start here' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Open Ops / health' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Open Model lab' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Open Live stream' })).toBeVisible()
  })

  test('login, model lab file upload + score, alert/case/rule/suppression, settings', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: /hawk-eye/i })).toBeVisible()
    await page.getByPlaceholder('username').fill('admin')
    await page.getByPlaceholder('password').fill('admin123')
    await page.getByRole('button', { name: 'Continue' }).click()
    await expect(page.getByRole('heading', { name: 'Model lab' })).toBeVisible()

    await page.getByTestId('model-lab-rows-file').setInputFiles(sampleRowsJson)
    await page.getByRole('button', { name: /Quick score/ }).click()
    await expect(
      page.locator('main').getByText(/Results \(score\)|Raw response|[45][0-9]/).first(),
    ).toBeVisible({ timeout: 60_000 })

    await page.goto('/alerts')
    await page.locator('.he-card').filter({ hasText: 'Create alert' }).getByRole('button', { name: 'Create' }).click()
    const alertPre = page.locator('pre').filter({ hasText: '"alert_id"' }).first()
    await expect(alertPre).toBeVisible({ timeout: 30_000 })
    const alertText = await alertPre.textContent()
    const alertMatch = alertText?.match(/"alert_id"\s*:\s*(\d+)/)
    expect(alertMatch).toBeTruthy()
    const alertId = alertMatch![1]

    await page.getByPlaceholder('Alert id').fill(alertId)
    await page.locator('.he-card').filter({ hasText: 'Update status' }).getByRole('button', { name: 'Apply' }).click()
    await expect(page.locator('pre').filter({ hasText: '"acknowledged"' }).first()).toBeVisible({ timeout: 15_000 })

    await page.goto('/cases')
    await page.getByPlaceholder('Link alert id (optional)').fill(alertId)
    await page.getByRole('button', { name: 'Create case' }).click()
    const casePre = page.locator('pre').filter({ hasText: '"case_id"' }).first()
    await expect(casePre).toBeVisible({ timeout: 15_000 })
    const caseText = await casePre.textContent()
    const caseMatch = caseText?.match(/"case_id"\s*:\s*(\d+)/)
    expect(caseMatch).toBeTruthy()
    const caseId = caseMatch![1]

    await page.getByRole('link', { name: new RegExp(`#${caseId} `) }).click()
    await expect(page.getByRole('heading', { name: `Case #${caseId}` })).toBeVisible()
    await page.getByPlaceholder('Add a note').fill('e2e comment')
    await page.getByRole('button', { name: 'Add comment' }).click()
    await page.getByRole('button', { name: 'Assign' }).click()

    await page.goto('/rules')
    const ruleName = `e2e-rule-${crypto.randomUUID()}`
    const ruleCard = page.locator('.he-card').filter({ hasText: 'Create rule' })
    await ruleCard.locator('input.he-input').first().fill(ruleName)
    await ruleCard.getByRole('button', { name: 'Create' }).click()
    await expect(page.locator('pre').filter({ hasText: ruleName }).first()).toBeVisible({ timeout: 15_000 })

    await page.goto('/suppressions')
    await page.locator('.he-card').filter({ hasText: 'Add suppression' }).getByRole('button', { name: 'Create' }).click()
    await expect(page.locator('main pre').first()).toBeVisible({ timeout: 15_000 })

    await page.goto('/settings')
    await page.locator('.he-card').filter({ hasText: 'PATCH body' }).locator('textarea').fill('{"stream_poll_seconds": 2}')
    await page.getByRole('button', { name: 'Apply changes' }).click()
    await expect(page.locator('pre').filter({ hasText: /stream_poll_seconds.*\b2\b/ }).first()).toBeVisible({
      timeout: 15_000,
    })
  })
})
