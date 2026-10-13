import { expect, test, type Page } from '@playwright/test'

const email = process.env.GANFY_E2E_EMAIL
const password = process.env.GANFY_E2E_PASSWORD
const visualEmail = process.env.GANFY_E2E_VISUAL_EMAIL || email
const visualPassword = process.env.GANFY_E2E_VISUAL_PASSWORD || password

test.skip(!visualEmail || !visualPassword, '设置 GANFY_E2E_EMAIL 与 GANFY_E2E_PASSWORD 后运行视觉回归')

async function login(page: Page) {
  await page.goto('/login')
  await page.getByPlaceholder('请输入邮箱').fill(visualEmail!)
  await page.getByPlaceholder('请输入密码').fill(visualPassword!)
  await page.getByRole('button', { name: /登录/ }).click()
  await expect(page).toHaveURL(/\/$/)
}

const maskSelectors = {
  workbench: ['.app-header .username', '.metric-grid', '.dashboard-grid', '.recent-card'],
  content: ['.app-header .username', '.content-summary', '.content-grid', '.credentials-card', '.calendar-card'],
}

const allRouteVisuals = [
  ['home', '/', '工作台总览'],
  ['workbench', '/workbench', '把素材变成可用知识'],
  ['tasks', '/tasks', '待处理任务'],
  ['assets', '/assets', '统一素材中心'],
  ['knowledge', '/knowledge', '知识卡片'],
  ['knowledge-network', '/knowledge/network', '知识关系网络'],
  ['research', '/research', '行业知识研究'],
  ['agents', '/agents', 'Agent 运行中心'],
  ['content', '/content', '内容中心'],
  ['data-center', '/data-center', '工作台健康度与效果'],
  ['runs', '/runs', '运行档案'],
  ['datasets', '/datasets', '知识库'],
  ['chat', '/chat', '智能问答'],
] as const

const allRouteMaskSelectors = [
  '.app-header .username',
  '.metric-grid',
  '.dashboard-grid',
  '.content-summary',
  '.content-grid',
  '.recent-card',
  '.summary-card',
  '.run-grid',
  '.schedule-card',
  '.approval-card',
  '.tools-card',
  '.knowledge-summary',
  '.card-grid',
  '.project-grid',
  '.quota-summary',
  '.filter-card',
  '.calendar-card',
  '.insight-card',
]

for (const viewport of [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'mobile', width: 390, height: 844 },
]) {
  test(`工作台视觉基线 · ${viewport.name}`, async ({ page }) => {
    test.setTimeout(60_000)
    await login(page)
    await page.setViewportSize({ width: viewport.width, height: viewport.height })

    for (const [name, route, heading] of [
      ['workbench', '/', '工作台总览'],
      ['content', '/content', '内容中心'],
    ] as const) {
      // CI 上后端尾延迟（挂起的轮询请求）会让 networkidle 永不达成；
      // 视图挂载由标题断言保证，动态卡片区域已全部 mask。
      await page.goto(route)
      await expect(page.locator('h1').first()).toContainText(heading)
      await page.waitForTimeout(300)
      if (name === 'content') {
        await expect(page.locator('.calendar-card')).toBeVisible()
        await expect(page.locator('.calendar-card .el-table, .calendar-card .el-empty')).toBeVisible()
      }
      await expect(page).toHaveScreenshot(`${name}-${viewport.name}.png`, {
        animations: 'disabled',
        caret: 'hide',
        maskColor: '#f8f6ff',
        mask: maskSelectors[name].map((selector) => page.locator(selector)),
        maxDiffPixelRatio: 0.015,
        scale: 'css',
      })
    }
  })
}

for (const viewport of [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'mobile', width: 390, height: 844 },
]) {
  test(`全核心路由视觉基线 · ${viewport.name}`, async ({ page }) => {
    test.setTimeout(300_000)
    await login(page)
    await page.setViewportSize({ width: viewport.width, height: viewport.height })

    for (const [name, route, heading] of allRouteVisuals) {
      // CI 上后端尾延迟（挂起的轮询请求）会让 networkidle 永不达成；
      // 视图挂载由标题断言保证，动态卡片区域已全部 mask。
      await page.goto(route)
      await expect(page.locator('h1').first()).toContainText(heading)
      await page.waitForTimeout(300)
      await expect(page).toHaveScreenshot(`all-routes-${name}-${viewport.name}.png`, {
        animations: 'disabled',
        caret: 'hide',
        maskColor: '#f8f6ff',
        mask: allRouteMaskSelectors.map((selector) => page.locator(selector)),
        maxDiffPixelRatio: 0.02,
        scale: 'css',
      })
    }
  })
}
