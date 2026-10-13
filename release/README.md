# 发布治理

本目录包含公开的发布能力 Profile 与通用治理说明，适配知域的 Python/RAG 双服务结构。预发/生产环境的原始日志、数据库标识、部署账号、备份信息和手工验收记录应保存在仓库外的受控证据库，不要提交到公开 Git 历史。

发布状态机为：`draft → rc → verified → approved → tagged → released`。任何 required capability 的失败、阻塞、未执行、未知或证据不绑定当前 HEAD，均不得进入 `verified`，更不得打 tag。

## 使用方式

1. 为本次版本更新 [release-profile.json](release-profile.json) 的范围、required capability、测试命令、排除项和负责人。
2. 在干净候选 HEAD 运行 `bash scripts/quality/run-quality-gates.sh --full`。
3. 在预发执行 profile 的命令并收集证据。对需要真实环境的项目，使用 `--manual-evidence MVP-04=/path/to/record.md` 附上备份恢复、回滚、告警和权限验证记录；采集器会记录文件哈希。
4. 将 Profile 的 `status` 更新为 `verified`（独立审核后为 `approved`），再运行 `release-preflight.py`。
5. 仅在 preflight 通过后运行部署脚本和创建不可变 tag。

`release-profile.json` 的状态必须与当前候选证据同步；只有 `verified`/`approved` 且证据绑定当前 HEAD 时，才允许创建发布标签。
