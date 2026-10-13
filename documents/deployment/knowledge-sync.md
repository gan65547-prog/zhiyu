# 知识库与 GitHub 自动同步操作指南

> **状态**：当前操作指南（2026-08-05）  
> **适用范围**：`ganfy` 单仓库 + `enterprise-rag-v2` 已有 RAG 数据集  
> **产品基线**：[AI 工作台产品详细落地方案](../design/AI工作台产品详细落地方案-v1.md)；本文只说明已落地的同步操作，不定义新的产品或数据模型。

---

## 1. 我们要解决什么问题

- **开发资料 / 业务流程 / 运维说明** 放在 Git 仓库里，希望**随发版自动进入 RAG 数据集**，避免只靠人工在控制台上传、版本与文档脱节。
- 你们线上**正常的 RAG 链路**不变：**上传文档 → 切片 → 向量化 → 入库 → 对话检索**。本方案只是在「上传」这一步增加 **CI 自动代传**。

---

## 2. 正常 RAG 操作 vs GitHub 自动同步的关系

| 环节 | 你平时的做法 | 使用 KB Sync 之后 |
|------|----------------|-------------------|
| 把文件放进「知识库」 | 在控制台上传 | **Git 仓库里维护 Markdown**，由 CI 调用上传接口 |
| 切片 / 向量化 / 写入向量库 | 后端自动处理 | **完全相同**，仍由现有 `process_document_task` 等链路完成 |
| 检索与对话 | 选数据集提问 | **完全相同** |

**结论**：配置正确、Worker 正常时，GitHub 的 workflow 只负责把仓库文档提交到指定数据集；之后仍由既有文档处理、向量化和检索链路完成。自动触发使用 `vMAJOR.MINOR.PATCH` 格式的 tag（如 `v2.4.0`）。

---

## 3. 仓库里知识文档放哪里

- **默认目录**：`documents/kb/`（仓库已预留，可把 `.md`、`.txt` 等放在其下子目录）。
- **可选扩展**：通过 GitHub **Variable** `KB_SYNC_ROOTS` 配置多个相对路径，逗号分隔，例如：  
  `documents/kb,documents/design`  
  注意：`documents/design` 全文较大时，会同步较多设计文档，请按需配置。
- **补充列表文件（可选）**：环境变量 `KB_SYNC_PATHS_FILE` 指向一个文本文件，每行一个相对路径，`#` 开头为注释。适合「只同步少数几个设计文档」的场景。

---

## 4. GitHub 上「Run workflow」跑的是什么

- **工作流文件**：`.github/workflows/kb-sync.yml`  
- **工作流名称**：在 Actions 列表里显示为 **KB Sync**。
- **触发方式**：
  1. **手动**：Actions → **KB Sync** → **Run workflow**（选分支后运行）；  
  2. **自动**：推送以 **`v` 开头且符合 `vMAJOR.MINOR.PATCH`** 的 tag（如 `v1.0.0`）时由 workflow 触发（见 `.github/workflows/kb-sync.yml` 注释）；**不推荐** `1.0.0`、`release/v1.0.0` 等命名。
- **执行内容概要**：
  1. `checkout` 当前代码；
  2. **（仅 push tag）** 校验 tag 为 **`vMAJOR.MINOR.PATCH`**（三段数字），与主设计 **FR-06**、`.github/workflows/kb-sync.yml` 中 **Validate release tag format** 步骤一致；不合规则 Job 失败、**不执行同步**；**Run workflow** 无 tag，跳过该校验；
  3. 检查是否已配置必需的 **Variables**（见下文）；
  4. 安装 Python 与 `httpx`；
  5. 执行：`python enterprise-rag-v2/scripts/kb/kb_sync.py`  
     脚本会扫描约定路径下的知识文件，对**每个文件**：在数据集中删除**同名 kb-sync 规范文件名**的旧文档（幂等），再 **multipart 上传**到  
     `POST /api/v1/documents/datasets/{dataset_id}/`  
     与控制台上传为**同一接口**；上传成功后由后端入队做切片与向量化。

**同步脚本路径**：`enterprise-rag-v2/scripts/kb/kb_sync.py`（支持 `--dry-run`、`--help`）。

---

## 5. 公网 API 时的网络说明与安全注意

- 若 `enterprise-rag-v2` 的 **API 暴露在公网**（`KB_SYNC_BASE_URL` 可从互联网访问），GitHub 官方提供的 **`ubuntu-latest` Runner** 一般 **可以直接访问**，无需自托管 Runner。
- 若将来改为**仅内网**，则 GitHub 云端 Runner **无法访问**，需改为：自托管 Runner、或在内网 CI 中执行同一脚本，**不能**再依赖公网 Run workflow 直连内网 API。

**公网下的风险缓解（摘要）**

- 仅使用 **HTTPS**；`KB_SYNC_TOKEN` 使用 **CI 专用账号**、**最小权限**，并**定期轮换**（JWT 过期会导致同步 401，见主设计 **§10.7**）。
- 可选：网关 **IP 白名单**（GitHub Runner 出口网段维护成本高，按需）。
- 同步脚本已对 **429 / 5xx** 做有限次重试（`KB_SYNC_MAX_RETRIES`）；仍失败则 workflow 失败，避免静默漏同步。

---

## 6. GitHub 配置清单（必须完成）

在 GitHub 打开本仓库：**Settings → Secrets and variables → Actions**

### 6.1 Repository variables（非敏感）

| Variable 名称 | 含义 | 示例 |
|---------------|------|------|
| `KB_SYNC_BASE_URL` | API **根地址**，**不要**尾斜杠 | `https://api.example.com` |
| `KB_SYNC_DATASET_ID` | **默认**目标 **数据集 UUID**；若配置了 `KB_SYNC_DATASET_MAP`，则作为**未命中任何路径前缀**时的回退库 | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `KB_SYNC_DATASET_MAP`（可选） | JSON：**仓库相对路径前缀 → dataset_id**，**最长前缀优先**。示例见主设计文档 **§10.2** | 单行 JSON 字符串 |
| `KB_SYNC_MAX_RETRIES`（可选） | 对 429/5xx 等的 HTTP 重试次数 | `3` |
| `KB_SYNC_ROOTS`（可选） | 逗号分隔的**相对仓库根**的路径 | 不配置则脚本默认 `documents/kb` |

### 6.2 Repository secrets（敏感）

| Secret 名称 | 含义 |
|-------------|------|
| `KB_SYNC_TOKEN` | 具备该数据集**上传权限**的用户 **JWT（access_token）**，仅保存 token 字符串，**不要**包含 `Bearer ` 前缀。 |

脚本请求头为：`Authorization: Bearer <KB_SYNC_TOKEN>`。

**获取 Token 的常规做法**：使用有权限的账号调用你们系统的登录接口（例如 `POST /api/v1/auth/login`），从响应中取出 `access_token`（字段名以实际 API 为准），写入 Secret。

**注意**：JWT 会过期，过期后同步会 **401**。长期建议：使用 **CI 专用账号** + 定期轮换 Secret；后续可在流水线中增加 refresh 逻辑（当前未实现）。

---

## 7. 完整操作流程（从 0 到可用）

### 步骤 A：在 RAG 产品里准备好数据集

1. 登录 `enterprise-rag-v2` 控制台（或管理端）。
2. 在对应 **Workspace** 下创建（或选定）一个 **Dataset**，作为「内部知识库」。
3. 复制该数据集的 **UUID**，供 GitHub Variable `KB_SYNC_DATASET_ID` 使用。

### 步骤 B：准备 Token 对应的用户权限

1. 该用户必须属于目标 Workspace，且能对该 Dataset **上传文档**。
2. 用户需有完整 **tenant_id** 等上下文，否则上传接口可能拒绝（与现网控制台行为一致）。

### 步骤 C：在 GitHub 配置 Variables 与 Secret

1. 添加 **Variables**：`KB_SYNC_BASE_URL`、`KB_SYNC_DATASET_ID`；按需添加 `KB_SYNC_ROOTS`。  
2. 添加 **Secret**：`KB_SYNC_TOKEN`。

### 步骤 D：把知识文档放进仓库

1. 将 `.md` / `.txt` 等放入 `documents/kb/`（或你在 `KB_SYNC_ROOTS` 中配置的路径）。
2. **提交并推送到** GitHub 上将要运行 workflow 的分支（例如 `main`）。

### 步骤 E：触发同步

**方式一（推荐先试）**：  
GitHub → **Actions** → **KB Sync** → **Run workflow** → 选择分支 → **Run workflow**。

**方式二（发版习惯）**：  
本地打 tag 并推送：

```bash
git tag v1.0.0
git push origin v1.0.0
```

### 步骤 F：验证

1. 在 Actions 中打开本次运行，查看 **Run kb-sync** 日志：应出现 `kb_sync_start`、`kb_sync_file`、`kb_sync_done` 等 JSON 行。  
2. 在 RAG 控制台该数据集中查看文档列表：应有新文档，状态最终为**已处理/已完成**（与现网一致）。  
3. 任选一条对话，对该数据集做检索，确认能命中新内容。  
4. 若文档一直处于待处理：检查线上 **Celery Worker** 是否消费 `documents_high`（或你们环境实际队列名），与现网「上传后不索引」的排查方式相同。

---

## 8. 本地手动同步（不经过 GitHub）

在能访问公网 API 的机器上：

```bash
cd /path/to/ganfy

export KB_SYNC_BASE_URL='https://你的API根'
export KB_SYNC_DATASET_ID='你的数据集UUID'
export KB_SYNC_TOKEN='你的JWT'
export KB_SYNC_REPO_ROOT="$(pwd)"
# 可选：export KB_SYNC_ROOTS='documents/kb,documents/design'

python3 enterprise-rag-v2/scripts/kb/kb_sync.py --dry-run   # 仅列出将上传的文件
python3 enterprise-rag-v2/scripts/kb/kb_sync.py             # 实际上传
```

---

## 9. 常见问题（排障）

| 现象 | 可能原因 | 处理方向 |
|------|----------|----------|
| Variables 检查失败 | 未配置 `KB_SYNC_BASE_URL` 或 `KB_SYNC_DATASET_ID` | 在 Settings → Variables 中补全 |
| 上传 401 / 403 | Token 过期、无权限、租户不匹配 | 换新 JWT；确认用户与数据集同属一租户/Workspace |
| 脚本成功但检索不到 | Worker 未处理队列、向量库失败 | 查 Celery / 文档处理日志；与手动上传一条测试文档对比 |
| 重复文档 | 极少见：同名规范名冲突 | 脚本已按「规范上传名」先删后传；仍异常可查数据集内是否有人为同名上传 |

---

## 10. 与发布的关系

- **本文档**只说明 GitHub + `kb_sync` 的配置、运行和验证。
- 同步可以由符合 `vMAJOR.MINOR.PATCH` 格式的 tag 或手动 workflow 触发；目标环境由 GitHub Variables/Secrets 显式决定。
- 发版时按 [知识库同步发布检查表](knowledge-sync-release-checklist.md) 确认同步范围。更严格的“仅生产 tag 写生产数据集”必须通过环境隔离的 Variables/Secrets 实现，不能依赖文档约定。

---

## 11. 一页纸 checklist

- [ ] 已创建内部知识库 **Dataset**，并已复制 **UUID**  
- [ ] 已配置 GitHub **Variables**：`KB_SYNC_BASE_URL`、`KB_SYNC_DATASET_ID`（及可选 `KB_SYNC_ROOTS`、`KB_SYNC_DATASET_MAP`、`KB_SYNC_MAX_RETRIES`）  
- [ ] 已配置 GitHub **Secret**：`KB_SYNC_TOKEN`  
- [ ] 知识 Markdown 已放入 `documents/kb/`（或配置的 roots）并已 **push**  
- [ ] 已执行 **Run workflow** 或推送 **`vMAJOR.MINOR.PATCH` tag**（如 `v1.0.0`）  
- [ ] Actions 日志无报错；控制台文档状态正常；检索验证通过  

---

*文档结束。*
