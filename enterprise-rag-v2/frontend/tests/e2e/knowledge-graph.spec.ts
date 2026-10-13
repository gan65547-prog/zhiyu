import { expect, test, type Page } from '@playwright/test'

const email = process.env.GANFY_E2E_EMAIL
const password = process.env.GANFY_E2E_PASSWORD

test.skip(!email || !password, '设置 GANFY_E2E_EMAIL 与 GANFY_E2E_PASSWORD 后运行知识治理回归')

async function login(page: Page) {
  await page.goto('/login')
  await page.getByPlaceholder('请输入邮箱').fill(email!)
  await page.getByPlaceholder('请输入密码').fill(password!)
  await page.getByRole('button', { name: /登录/ }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('heading', { name: '工作台总览' })).toBeVisible()
}

async function apiJson(page: Page, path: string, init?: RequestInit) {
  return page.evaluate(async ({ path, init }) => {
    const headers = new Headers(init?.headers)
    if ((init?.method || 'GET').toUpperCase() !== 'GET' && !headers.has('x-csrf-token')) {
      const csrf = document.cookie.match(/(?:^|; )csrf_token=([^;]+)/)?.[1]
      if (csrf) headers.set('x-csrf-token', decodeURIComponent(csrf))
    }
    const response = await fetch(path, { ...init, headers })
    const body = await response.json()
    if (!response.ok) throw new Error(`${response.status}: ${JSON.stringify(body)}`)
    return body
  }, { path, init })
}

test('知识卡片审核后自动给出候选关系并支持批量确认', async ({ page }) => {
  await login(page)
  const suffix = Date.now().toString()
  const workspacePayload = await apiJson(page, '/api/v1/workspaces/current')
  const workspaceId = workspacePayload?.data?.id
  expect(workspaceId).toBeTruthy()

  const asset = await apiJson(page, '/api/v1/assets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workspace_id: workspaceId,
      source_type: 'text',
      title: `知识治理证据-${suffix}`,
    }),
  })
  const itemTitles = [`供应链韧性方法-${suffix}`, `供应链韧性案例-${suffix}`]
  for (const [index, title] of itemTitles.entries()) {
    const item = await apiJson(page, '/api/v1/knowledge/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: workspaceId,
        title,
        item_type: index === 0 ? 'method' : 'case',
        definition: `供应链韧性是第 ${index + 1} 个可追溯知识治理样本。`,
        conclusions: ['供应链韧性需要持续复盘'],
      }),
    })
    await apiJson(page, `/api/v1/knowledge/items/${item.id}/evidence`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asset_id: asset.id, quote: `供应链韧性证据摘录 ${index + 1}` }),
    })
  }

  await page.goto('/knowledge')
  for (const title of itemTitles) {
    const card = page.locator('.knowledge-card').filter({ hasText: title })
    await expect(card).toBeVisible()
    await card.getByRole('button', { name: '审核通过' }).click()
    await expect(page.getByText('知识卡片已通过')).toBeVisible()
  }

  await page.goto('/knowledge/network')
  await expect(page.getByRole('heading', { name: '知识关系网络' })).toBeVisible()
  const suggestion = page.locator('.suggestion-row').filter({ hasText: itemTitles[0] }).filter({ hasText: itemTitles[1] }).first()
  await expect(suggestion).toBeVisible()
  await suggestion.locator('.el-checkbox').click()
  await page.getByRole('button', { name: /批量确认/ }).click()
  await expect(page.getByText('已确认 1 条候选关系')).toBeVisible()
  await expect(page.getByText('关系 1', { exact: true })).toBeVisible()
})
