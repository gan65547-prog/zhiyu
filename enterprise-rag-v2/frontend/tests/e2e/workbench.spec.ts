import { expect, test, type Page } from '@playwright/test'

const email = process.env.GANFY_E2E_EMAIL
const password = process.env.GANFY_E2E_PASSWORD

test.skip(!email || !password, '设置 GANFY_E2E_EMAIL 与 GANFY_E2E_PASSWORD 后运行浏览器回归')

async function login(page: Page) {
  await page.goto('/login')
  await page.getByPlaceholder('请输入邮箱').fill(email!)
  await page.getByPlaceholder('请输入密码').fill(password!)
  await page.getByRole('button', { name: /登录/ }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('heading', { name: '工作台总览' })).toBeVisible()
}

test.describe('AI 工作台核心浏览器回归', () => {
  test('登录后工作台主入口可用', async ({ page }) => {
    await login(page)

    await page.getByRole('button', { name: /导入素材/ }).click()
    await expect(page).toHaveURL(/\/assets$/)
    await expect(page.getByRole('heading', { name: '统一素材中心' })).toBeVisible()

    await page.goto('/')
    await expect(page.getByRole('heading', { name: '工作台总览' })).toBeVisible()
    await page.getByRole('button', { name: /开始问答/ }).click()
    await expect(page).toHaveURL(/\/chat$/)

  })

  test('素材新增弹窗可切换来源并关闭', async ({ page }) => {
    await login(page)
    await page.goto('/assets')
    await page.getByRole('button', { name: /添加素材/ }).click()

    const dialog = page.locator('.el-dialog').filter({ hasText: '添加素材' })
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText('网页 URL', { exact: true })).toBeVisible()
    await dialog.getByText('网页 URL', { exact: true }).click()
    await expect(dialog.getByPlaceholder(/https?:\/\//)).toBeVisible()
    await dialog.getByText('粘贴文本', { exact: true }).click()
    await expect(dialog.getByPlaceholder('例如：2026 行业报告')).toBeVisible()
    await dialog.getByRole('button', { name: '取消' }).click()
    await expect(dialog).toBeHidden()
  })

  test('批量导入入口支持多文件并默认进入资料库', async ({ page }) => {
    await login(page)
    await page.goto('/assets')
    await page.getByRole('button', { name: '添加素材' }).click()

    const dialog = page.locator('.el-dialog').filter({ hasText: '添加素材' })
    await expect(dialog).toBeVisible()
    // Element Plus 的 upload 容器本身也带 role=button；这里断言实际操作按钮，避免严格模式匹配两个节点。
    await expect(dialog.getByRole('button', { name: '选择多个文件', exact: true }).last()).toBeVisible()
    await expect(dialog).toContainText('自动绑定到默认资料库')
    const fileInputs = dialog.locator('input[type="file"]')
    expect(await fileInputs.count()).toBeGreaterThan(0)
    expect(await fileInputs.first().getAttribute('multiple')).not.toBeNull()
    await dialog.getByRole('button', { name: '取消' }).click()
  })

  test('非核心旧链接重定向到已交付流程', async ({ page }) => {
    await login(page)

    for (const [legacyPath, expectedPath] of [
      ['/insights', '/research'],
      ['/brainstorm', '/content'],
      ['/hot-topics', '/research'],
      ['/inspiration', '/knowledge'],
      ['/bookshelf', '/datasets'],
      ['/platform-data', '/content'],
    ] as const) {
      await page.goto(legacyPath)
      await expect(page).toHaveURL(new RegExp(`${expectedPath}$`))
    }
  })

  test('核心路由矩阵加载主标题且无页面级 JavaScript 错误', async ({ page }) => {
    test.setTimeout(120_000)
    await login(page)

    const routes = [
      ['/', '工作台总览'],
      ['/workbench', '把素材变成可用知识'],
      ['/tasks', '待处理任务'],
      ['/assets', '统一素材中心'],
      ['/knowledge', '知识卡片'],
      ['/knowledge/network', '知识关系网络'],
      ['/research', '行业知识研究'],
      ['/agents', 'Agent 运行中心'],
      ['/content', '内容中心'],
      ['/data-center', '工作台健康度与效果'],
      ['/runs', '运行档案'],
      ['/datasets', '知识库'],
      ['/chat', '智能问答'],
    ] as const

    for (const [route, heading] of routes) {
      const pageErrors: string[] = []
      const onPageError = (error: Error) => pageErrors.push(error.message)
      page.on('pageerror', onPageError)
      await page.goto(route, { waitUntil: 'domcontentloaded' })
      await expect(page).toHaveURL(new RegExp(`${route.replace('/', '\\/')}$`))
      await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible({ timeout: 20_000 })
      await expect(page.locator('body')).not.toContainText(/服务器内部错误|页面加载失败|Failed to resolve|Cannot read properties of undefined/)
      expect(pageErrors, `${route} 存在未捕获 pageerror`).toEqual([])
      page.off('pageerror', onPageError)
    }
  })

  test('全核心路由在桌面与移动视口无结构性溢出', async ({ page }) => {
    test.setTimeout(180_000)
    await login(page)

    const routes = [
      ['/', '工作台总览'],
      ['/workbench', '把素材变成可用知识'],
      ['/tasks', '待处理任务'],
      ['/assets', '统一素材中心'],
      ['/knowledge', '知识卡片'],
      ['/knowledge/network', '知识关系网络'],
      ['/research', '行业知识研究'],
      ['/agents', 'Agent 运行中心'],
      ['/content', '内容中心'],
      ['/data-center', '工作台健康度与效果'],
      ['/runs', '运行档案'],
      ['/datasets', '知识库'],
      ['/chat', '智能问答'],
    ] as const

    for (const viewport of [
      { width: 1440, height: 1000 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(viewport)
      for (const [route, heading] of routes) {
        const pageErrors: string[] = []
        const onPageError = (error: Error) => pageErrors.push(error.message)
        page.on('pageerror', onPageError)
        await page.goto(route, { waitUntil: 'domcontentloaded' })
        await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible({ timeout: 20_000 })
        await expect(page.locator('body')).not.toContainText(/服务器内部错误|页面加载失败|Failed to resolve|Cannot read properties of undefined/)
        await expect.poll(async () => page.evaluate(() => ({
          documentWidth: document.documentElement.scrollWidth,
          viewportWidth: window.innerWidth,
        }))).toEqual(expect.objectContaining({ documentWidth: expect.any(Number), viewportWidth: viewport.width }))
        const overflow = await page.evaluate(() => ({
          documentWidth: document.documentElement.scrollWidth,
          viewportWidth: window.innerWidth,
        }))
        expect(overflow.documentWidth, `${route} @ ${viewport.width}px 存在横向溢出`).toBeLessThanOrEqual(overflow.viewportWidth + 1)
        expect(pageErrors, `${route} @ ${viewport.width}px 存在未捕获 pageerror`).toEqual([])
        page.off('pageerror', onPageError)
      }
    }
  })

  test('内容执行、指标录入与复盘闭环可用', async ({ page }) => {
    test.setTimeout(90_000)
    await login(page)
    await page.goto('/content')

    const suffix = Date.now().toString()
    const topicTitle = `浏览器回归选题-${suffix}`
    const draftTitle = `浏览器回归草稿-${suffix}`

    await page.getByRole('button', { name: '新建选题' }).click()
    const topicDialog = page.locator('.el-dialog').filter({ hasText: '新建选题' })
    await expect(topicDialog).toBeVisible()
    await topicDialog.getByRole('textbox').nth(0).fill(topicTitle)
    await topicDialog.getByRole('textbox').nth(1).fill('用于验证内容执行与数据复盘的浏览器闭环。')
    await topicDialog.getByRole('button', { name: '创建' }).click()
    await expect(page.getByText(topicTitle, { exact: true })).toBeVisible()

    await page.getByRole('button', { name: '新建草稿' }).click()
    const draftDialog = page.locator('.el-dialog').filter({ hasText: '新建内容草稿' })
    await expect(draftDialog).toBeVisible()
    const draftTextboxes = draftDialog.getByRole('textbox')
    await draftTextboxes.nth(0).fill(draftTitle)
    await draftTextboxes.nth(1).fill('这是一篇用于验证素材、洞察、内容执行和平台数据复盘闭环的测试正文。')
    await draftDialog.getByRole('button', { name: '创建' }).click()

    const draftRow = page.locator('.draft-row').filter({ hasText: draftTitle })
    await expect(draftRow).toBeVisible()
    await draftRow.getByRole('button', { name: '通过' }).click()
    await expect(page.getByText('草稿已通过')).toBeVisible()
    await expect(draftRow).toContainText('已通过')

    await draftRow.getByRole('button', { name: '记录发布' }).click()
    const publishDialog = page.locator('.el-dialog').filter({ hasText: '记录发布' })
    await expect(publishDialog).toBeVisible()
    await publishDialog.getByRole('button', { name: '保存发布记录' }).click()
    await expect(page.getByText('发布记录已保存')).toBeVisible()

    const readyRow = page.locator('.calendar-card .el-table__row').filter({ hasText: '人工发布' }).first()
    await expect(readyRow).toBeVisible()
    await readyRow.getByRole('button', { name: '确认已发布' }).click()
    const confirmDialog = page.locator('.el-dialog').filter({ hasText: '确认已发布' })
    await expect(confirmDialog).toBeVisible()
    await confirmDialog.getByRole('button', { name: '确认已发布' }).click()
    await expect(page.getByText('发布状态已确认')).toBeVisible()

    const publishedRow = page.locator('.calendar-card .el-table__row').filter({ hasText: '人工发布' }).first()
    await publishedRow.getByRole('button', { name: '录入指标' }).click()
    const metricDialog = page.locator('.el-dialog').filter({ hasText: '录入内容指标' })
    await expect(metricDialog).toBeVisible()
    const metricInputs = metricDialog.getByRole('spinbutton')
    for (const [index, value] of ['1200', '96', '40', '8', '4'].entries()) {
      await metricInputs.nth(index).fill(value)
    }
    await metricDialog.getByRole('button', { name: '保存指标' }).click()
    await expect(page.getByText('内容指标已保存')).toBeVisible()

    const publishId = await page.evaluate(async () => {
      const workspaceResponse = await fetch('/api/v1/workspaces/current')
      const workspacePayload = await workspaceResponse.json()
      const workspaceId = workspacePayload?.data?.id
      const publishResponse = await fetch(`/api/v1/content/publishes?workspace_id=${workspaceId}`)
      const publishPayload = await publishResponse.json()
      return publishPayload?.items?.find((item: { platform?: string; status?: string }) => item.platform === 'manual' && item.status === 'published')?.id || ''
    })
    expect(publishId, '应能读取刚刚确认发布的记录 ID').toBeTruthy()
    await page.getByRole('button', { name: '批量导入指标' }).click()
    const batchDialog = page.locator('.el-dialog').filter({ hasText: '批量导入内容指标' })
    await expect(batchDialog).toBeVisible()
    await batchDialog.getByRole('textbox').fill(JSON.stringify([{
      publish_id: publishId,
      collected_at: '2026-08-02T12:00:00Z',
      metric: { impressions: 1800, clicks: 120, likes: 55, comments: 12, shares: 7 },
    }]))
    await batchDialog.getByRole('button', { name: '导入' }).click()
    await expect(page.getByText(/指标导入完成：新增 1 条/)).toBeVisible()

    await publishedRow.getByRole('button', { name: '复盘' }).click()
    const retrospectiveDialog = page.locator('.el-dialog').filter({ hasText: '内容效果复盘' })
    await expect(retrospectiveDialog).toBeVisible()
    await expect(retrospectiveDialog).toContainText('1200')
    await retrospectiveDialog.locator('.el-dialog__headerbtn').click()

  })

  test('核心工作台页面在移动视口不产生横向溢出', async ({ page }) => {
    test.setTimeout(60_000)
    await login(page)
    await page.setViewportSize({ width: 390, height: 844 })

    for (const [route, heading] of [['/', '工作台总览'], ['/content', '内容中心'], ['/research', '行业知识研究']]) {
      await page.goto(route, { waitUntil: 'domcontentloaded' })
      await expect(page.locator('h1').first()).toContainText(heading)
      const overflow = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }))
      expect(overflow.scrollWidth, `${route} 存在移动端横向溢出`).toBeLessThanOrEqual(overflow.clientWidth + 1)
    }
  })

  test('研究项目创建表单与外部搜索字段联动可用', async ({ page }) => {
    test.setTimeout(60_000)
    await login(page)
    await page.goto('/research')
    await page.getByRole('button', { name: /新建研究项目/ }).click()

    const dialog = page.locator('.el-dialog').filter({ hasText: '新建研究项目' })
    await expect(dialog).toBeVisible()
    const fields = dialog.getByRole('textbox')
    const projectName = `浏览器研究表单回归-${Date.now()}`
    await fields.nth(0).fill(projectName)
    await fields.nth(1).fill('验证研究项目创建、受控搜索开关和额度边界。')
    await dialog.locator('.el-switch').click()
    await expect(dialog.getByRole('textbox', { name: '外部搜索问题' })).toBeVisible()
    await dialog.locator('.el-switch').click()
    await expect(dialog.getByRole('textbox', { name: '外部搜索问题' })).toBeHidden()
    await dialog.getByRole('button', { name: '创建项目' }).click()

    const projectCard = page.locator('.project-card').filter({ hasText: projectName })
    await expect(projectCard).toBeVisible()
    await expect(projectCard).toContainText(/运行研究|额度不足/)
  })

  test('Agent 工具定义与只读工具运行可用', async ({ page }) => {
    test.setTimeout(60_000)
    await login(page)
    await page.goto('/agents')
    await page.getByRole('button', { name: '新建工具 Agent' }).click()

    const definitionDialog = page.locator('.el-dialog').filter({ hasText: '新建工具 Agent' })
    await expect(definitionDialog).toBeVisible()
    await definitionDialog.getByRole('textbox').nth(0).fill(`术语提取回归-${Date.now()}`)
    await definitionDialog.locator('.el-select').nth(1).click()
    await page.getByRole('option', { name: '提取候选术语' }).click()
    await definitionDialog.getByPlaceholder('例如：collect_terms').fill('extract_terms')
    await definitionDialog.getByRole('button', { name: '创建' }).click()
    await expect(page.getByText('工具 Agent 定义已创建，可立即运行')).toBeVisible()

    await page.getByRole('button', { name: '运行白名单工具' }).click()
    const toolDialog = page.locator('.el-dialog').filter({ hasText: '运行白名单工具' })
    await expect(toolDialog).toBeVisible()
    await toolDialog.getByRole('textbox').fill('{"text":"AI 工作台 证据 洞察"}')
    await toolDialog.getByRole('button', { name: '创建并运行' }).click()
    await expect(page.getByText('工具执行完成')).toBeVisible()
    await expect(page.locator('.run-card').first()).toContainText('已完成')
  })

  test('Agent 外部抓取工具会先进入审批并在通过后完成', async ({ page }) => {
    test.setTimeout(90_000)
    await login(page)
    await page.goto('/agents')
    await page.getByRole('button', { name: '新建工具 Agent' }).click()

    const definitionDialog = page.locator('.el-dialog').filter({ hasText: '新建工具 Agent' })
    await definitionDialog.getByRole('textbox').nth(0).fill(`网页抓取审批回归-${Date.now()}`)
    await definitionDialog.locator('.el-select').nth(1).click()
    await page.getByRole('option', { name: '安全抓取网页' }).click()
    await definitionDialog.getByPlaceholder('例如：collect_terms').fill('fetch_page')
    await definitionDialog.getByRole('button', { name: '创建' }).click()
    await expect(page.getByText('工具 Agent 定义已创建，可立即运行')).toBeVisible()

    await page.getByRole('button', { name: '运行白名单工具' }).click()
    const toolDialog = page.locator('.el-dialog').filter({ hasText: '运行白名单工具' })
    await toolDialog.getByRole('textbox').fill('{"url":"https://1.1.1.1/cdn-cgi/trace","max_bytes":200000}')
    await toolDialog.getByRole('button', { name: '创建并运行' }).click()
    await expect(page.getByText('工具已提交，等待人工审批')).toBeVisible()

    const approvalCard = page.locator('.approval-card')
    await expect(approvalCard).toContainText('fetch_page')
    const approvalRow = approvalCard.locator('.el-table__row').filter({ hasText: 'fetch_page' })
    await approvalRow.getByRole('button', { name: '通过' }).click()
    // 审批接口会同步执行一次已批准的抓取，真实环境可能耗时数秒。
    // 等待业务提示本身，而不是用默认 8 秒把异步处理误报为失败。
    await expect(page.getByText('审批已通过')).toBeVisible({ timeout: 20_000 })
    await expect(page.locator('.run-card').first()).toContainText('已完成', { timeout: 45_000 })
  })

  test('Agent 定时调度可创建并切换启停状态', async ({ page }) => {
    test.setTimeout(90_000)
    await login(page)

    const suffix = Date.now()
    const definitionName = `调度工具回归-${suffix}`
    const projectName = `调度研究项目回归-${suffix}`
    const scheduleName = `定时任务回归-${suffix}`

    await page.goto('/agents')
    await page.getByRole('button', { name: '新建工具 Agent' }).click()
    const definitionDialog = page.locator('.el-dialog').filter({ hasText: '新建工具 Agent' })
    await definitionDialog.getByRole('textbox').nth(0).fill(definitionName)
    await definitionDialog.locator('.el-select').nth(1).click()
    await page.getByRole('option', { name: '提取候选术语' }).click()
    await definitionDialog.getByPlaceholder('例如：collect_terms').fill(`schedule_terms_${suffix}`)
    await definitionDialog.getByRole('button', { name: '创建' }).click()
    await expect(page.getByText('工具 Agent 定义已创建，可立即运行')).toBeVisible()

    await page.goto('/research')
    await page.getByRole('button', { name: /新建研究项目/ }).click()
    const projectDialog = page.locator('.el-dialog').filter({ hasText: '新建研究项目' })
    const projectFields = projectDialog.getByRole('textbox')
    await projectFields.nth(0).fill(projectName)
    await projectFields.nth(1).fill('用于验证 Agent 定时调度创建和启停切换。')
    await projectDialog.getByRole('button', { name: '创建项目' }).click()
    await expect(page.locator('.project-card').filter({ hasText: projectName })).toBeVisible()

    await page.goto('/agents')
    await page.getByRole('button', { name: '新建调度' }).click()
    const scheduleDialog = page.locator('.el-dialog').filter({ hasText: '新建 Agent 调度' })
    await expect(scheduleDialog).toBeVisible()
    await scheduleDialog.getByRole('textbox').nth(0).fill(scheduleName)
    await scheduleDialog.locator('.el-select').nth(0).click()
    await page.getByRole('option', { name: definitionName, exact: true }).click()
    await scheduleDialog.locator('.el-select').nth(1).click()
    await page.getByRole('option', { name: projectName, exact: true }).click()
    await scheduleDialog.getByRole('textbox').nth(1).fill('*/30 * * * *')
    const dateInput = scheduleDialog.locator('.el-date-editor input')
    await dateInput.fill('2026-08-10 23:59:00')
    // Enter 确认日期并关闭弹层面板；面板若悬浮会持续拦截「创建」按钮的 pointer events
    await dateInput.press('Enter')
    await expect(page.locator('.el-picker-panel')).toBeHidden()
    await scheduleDialog.getByRole('button', { name: '创建', exact: true }).click()
    await expect(page.getByText('调度已创建')).toBeVisible()

    const scheduleRow = page.locator('.schedule-card .el-table__row').filter({ hasText: scheduleName })
    await expect(scheduleRow).toContainText('已启用')
    await scheduleRow.getByRole('button', { name: '停用' }).click()
    await expect(scheduleRow).toContainText('已停用')
    await scheduleRow.getByRole('button', { name: '启用' }).click()
    await expect(scheduleRow).toContainText('已启用')
  })

  test('Agent 失败运行会保留并可重新排队', async ({ page }) => {
    test.setTimeout(60_000)
    await login(page)
    await page.goto('/agents')
    await page.getByRole('button', { name: '新建工具 Agent' }).click()

    const definitionDialog = page.locator('.el-dialog').filter({ hasText: '新建工具 Agent' })
    await definitionDialog.getByRole('textbox').nth(0).fill(`失败重试回归-${Date.now()}`)
    await definitionDialog.locator('.el-select').nth(1).click()
    await page.getByRole('option', { name: '提取候选术语' }).click()
    await definitionDialog.getByPlaceholder('例如：collect_terms').fill(`retry_terms_${Date.now()}`)
    await definitionDialog.getByRole('button', { name: '创建' }).click()
    await expect(page.getByText('工具 Agent 定义已创建，可立即运行')).toBeVisible()

    await page.getByRole('button', { name: '运行白名单工具' }).click()
    const toolDialog = page.locator('.el-dialog').filter({ hasText: '运行白名单工具' })
    await toolDialog.getByRole('textbox').fill('{}')
    await toolDialog.getByRole('button', { name: '创建并运行' }).click()
    await expect(page.getByText('工具执行失败，可在运行卡片中重试')).toBeVisible()

    const failedRun = page.locator('.run-card').first()
    await expect(failedRun).toContainText('失败')
    await failedRun.getByRole('button', { name: '重试' }).click()
    await expect(page.getByText('Agent 运行已重新排队')).toBeVisible()
    await expect(page.locator('.run-card').first()).toContainText('排队中')
  })
})
