# 发布档案

本公开目录不存放预发/生产候选档案、主机信息、真实回滚记录或环境日志。发布前将当前候选的 profile 和备份/回滚证据放在维护者控制的安全位置，并通过 `RELEASE_PROFILE`、`RELEASE_BACKUP_EVIDENCE`、`RELEASE_ROLLBACK_EVIDENCE` 显式传给发布脚本。发布脚本也要求显式设置目标主机和远端目录，不再内置项目维护者的部署路径。

通用发布范围与门禁见仓库根目录 `release/release-profile.json` 和 `release/README.md`。不得将真实环境凭据、客户数据或原始验收记录复制到此目录。
