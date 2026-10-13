import { expect, test, type Page } from '@playwright/test'

const email = process.env.GANFY_E2E_EMAIL
const password = process.env.GANFY_E2E_PASSWORD

test.skip(!email || !password, '设置 GANFY_E2E_EMAIL 与 GANFY_E2E_PASSWORD 后运行浏览器回归')
test.skip(process.env.GANFY_E2E_RESEARCH_RUN !== '1', '设置 GANFY_E2E_RESEARCH_RUN=1 后运行真实研究长任务回归')

async function login(page: Page) {
  await page.goto('/login')
  await page.getByPlaceholder('请输入邮箱').fill(email!)
  await page.getByPlaceholder('请输入密码').fill(password!)
  await page.getByRole('button', { name: /登录/ }).click()
  await expect(page).toHaveURL(/\/$/, { timeout: 30_000 })
  await expect(page.getByRole('heading', { name: '工作台总览' })).toBeVisible()
}

test('研究项目可完成真实队列运行并打开证据报告', async ({ page }) => {
  test.setTimeout(360_000)
  await login(page)
  await page.goto('/research')
  await page.getByRole('button', { name: /新建研究项目/ }).click()

  const dialog = page.locator('.el-dialog').filter({ hasText: '新建研究项目' })
  await expect(dialog).toBeVisible()
  const fields = dialog.getByRole('textbox')
  const projectName = `浏览器研究成功回归-${Date.now()}`
  await fields.nth(0).fill(projectName)
  await fields.nth(1).fill('验证固定公网来源可以进入研究队列并生成可追溯证据报告。')
  await fields.nth(2).fill('https://1.1.1.1/cdn-cgi/trace')
  await dialog.getByRole('button', { name: '创建项目' }).click()

  const projectCard = page.locator('.project-card').filter({ hasText: projectName })
  await expect(projectCard).toBeVisible()
  const runResponsePromise = page.waitForResponse(response => response.url().includes('/api/v1/research/projects/') && response.url().endsWith('/runs') && response.request().method() === 'POST')
  await projectCard.getByRole('button', { name: '运行研究' }).click()
  const runResponse = await runResponsePromise
  expect(runResponse.ok(), await runResponse.text()).toBeTruthy()

  await expect(projectCard).toContainText('已完成', { timeout: 300_000 })
  await projectCard.getByRole('button', { name: '报告' }).click()

  const reportDialog = page.locator('.el-dialog').filter({ hasText: '研究证据报告' })
  await expect(reportDialog).toBeVisible()
  await expect(reportDialog).toContainText('证据包')
  await expect(reportDialog.locator('.report-content')).toContainText('1.1.1.1')
})
