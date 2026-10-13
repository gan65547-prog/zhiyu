# 备份恢复

## 备份策略

### 备份类型

| 类型 | 频率 | 保留期 | 用途 |
|------|------|--------|------|
| 完整备份 | 每日 | 30天 | 灾难恢复 |
| 增量备份 | 每小时 | 7天 | 快速恢复 |
| 差异备份 | 每周 | 14天 | 数据验证 |

### 备份内容

- **数据库**: PostgreSQL数据
- **向量存储**: Qdrant数据
- **配置文件**: 应用配置、环境变量
- **代码**: 版本控制
- **日志**: 系统和应用日志

### 备份存储

- **本地存储**: 服务器本地磁盘
- **远程存储**: 云存储（S3、OSS等）
- **异地存储**: 不同地理位置的存储

## 数据库备份

### PostgreSQL备份

```bash
# 安装pg_dump
apt install -y postgresql-client

# 创建备份目录
mkdir -p /opt/backups/postgres

# 完整备份脚本
cat > /opt/scripts/backup-postgres.sh << EOF
#!/bin/bash

# 配置
DB_USER="rag_user"
DB_NAME="rag_db"
BACKUP_DIR="/opt/backups/postgres"
DATE=$(date +%Y-%m-%d_%H-%M-%S)

# 创建备份
pg_dump -U $DB_USER -d $DB_NAME -F c > "$BACKUP_DIR/full_$DATE.backup"

# 压缩备份
gzip "$BACKUP_DIR/full_$DATE.backup"

# 清理过期备份
find "$BACKUP_DIR" -name "*.backup.gz" -mtime +30 -delete

# 复制到远程存储
aws s3 cp "$BACKUP_DIR/full_$DATE.backup.gz" s3://backup-bucket/postgres/
EOF

# 设置执行权限
chmod +x /opt/scripts/backup-postgres.sh

# 配置定时任务
crontab -e
# 添加以下行
0 2 * * * /opt/scripts/backup-postgres.sh
```

### 增量备份

```bash
# 创建增量备份脚本
cat > /opt/scripts/backup-postgres-incremental.sh << EOF
#!/bin/bash

# 配置
DB_USER="rag_user"
DB_NAME="rag_db"
BACKUP_DIR="/opt/backups/postgres/incremental"
WAL_DIR="/opt/backups/postgres/wal"

# 确保目录存在
mkdir -p $BACKUP_DIR $WAL_DIR

# 基础备份
if [ ! -f "$BACKUP_DIR/base_backup.latest" ]; then
  pg_basebackup -U $DB_USER -D $BACKUP_DIR/base_backup -X stream -P
  touch "$BACKUP_DIR/base_backup.latest"
fi

# 归档WAL文件
psql -U $DB_USER -d $DB_NAME -c "SELECT pg_switch_wal();"
EOF

# 配置定时任务
crontab -e
# 添加以下行
0 * * * * /opt/scripts/backup-postgres-incremental.sh
```

## 向量存储备份

### Qdrant备份

```bash
# 创建备份目录
mkdir -p /opt/backups/qdrant

# 备份脚本
cat > /opt/scripts/backup-qdrant.sh << EOF
#!/bin/bash
set -euo pipefail

# 配置
BACKUP_DIR="/opt/backups/qdrant"
DATE=$(date +%Y-%m-%d_%H-%M-%S)
QDRANT_URL="\${QDRANT_URL:-http://localhost:6333}"
COLLECTIONS=("documents")

# 使用 Snapshot API 热备（无需停服）
for collection in "\${COLLECTIONS[@]}"; do
  resp=\$(curl -sS -X POST "\$QDRANT_URL/collections/\$collection/snapshots")
  snapshot_name=\$(echo "\$resp" | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["name"])')
  curl -sS -o "$BACKUP_DIR/\${collection}_\${DATE}.snapshot" \
    "\$QDRANT_URL/collections/\$collection/snapshots/\$snapshot_name"
done

# 清理过期备份
find "$BACKUP_DIR" -name "*.snapshot" -mtime +30 -delete

# 复制到远程存储
aws s3 cp "$BACKUP_DIR" s3://backup-bucket/qdrant/ --recursive --exclude "*" --include "*$DATE.snapshot"
EOF

# 设置执行权限
chmod +x /opt/scripts/backup-qdrant.sh

# 配置定时任务
crontab -e
# 添加以下行
0 3 * * * /opt/scripts/backup-qdrant.sh
```

## 配置文件备份

### 配置备份

```bash
# 创建备份目录
mkdir -p /opt/backups/config

# 备份脚本
cat > /opt/scripts/backup-config.sh << EOF
#!/bin/bash

# 配置
BACKUP_DIR="/opt/backups/config"
DATE=$(date +%Y-%m-%d_%H-%M-%S)

# 备份文件
files=("/opt/rag-system/backend/.env"
       "/etc/nginx/sites-available/rag-system"
       "/etc/systemd/system/rag-backend.service"
       "/opt/prometheus/prometheus.yml"
       "/opt/alertmanager/alertmanager.yml")

# 创建备份压缩包
tar czf "$BACKUP_DIR/config_$DATE.tar.gz" "${files[@]}"

# 清理过期备份
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete

# 复制到远程存储
aws s3 cp "$BACKUP_DIR/config_$DATE.tar.gz" s3://backup-bucket/config/
EOF

# 设置执行权限
chmod +x /opt/scripts/backup-config.sh

# 配置定时任务
crontab -e
# 添加以下行
0 4 * * * /opt/scripts/backup-config.sh
```

## 脚本健壮性建议（适用于全部备份脚本）

```bash
#!/bin/bash
set -euo pipefail

log() { echo "[$(date -Is)] $*" >> /var/log/backup.log; }

trap 'log "ERROR at line $LINENO"; exit 1' ERR
```

## 恢复流程

### 数据库恢复

#### 从完整备份恢复

```bash
# 停止应用服务
systemctl stop rag-backend

# 选择备份文件
BACKUP_FILE="/opt/backups/postgres/full_2026-04-04_02-00-00.backup.gz"

# 解压备份
 gunzip $BACKUP_FILE

# 恢复数据库
pg_restore -U rag_user -d rag_db -c /opt/backups/postgres/full_2026-04-04_02-00-00.backup

# 启动应用服务
systemctl start rag-backend
```

#### 从增量备份恢复

```bash
# 停止PostgreSQL服务
systemctl stop postgresql

# 清理数据目录
rm -rf /var/lib/postgresql/15/main/*

# 恢复基础备份
cp -r /opt/backups/postgres/incremental/base_backup/* /var/lib/postgresql/15/main/

# 恢复WAL文件
cp /opt/backups/postgres/wal/* /var/lib/postgresql/15/main/pg_wal/

# 启动PostgreSQL服务
systemctl start postgresql

# 启动应用服务
systemctl start rag-backend
```

### 向量存储恢复

```bash
# 停止Qdrant服务
docker stop qdrant
docker rm qdrant

# 清理数据目录
rm -rf /var/lib/docker/volumes/qdrant_data/_data/*

# 选择备份文件
BACKUP_FILE="/opt/backups/qdrant/qdrant_2026-04-04_03-00-00.tar.gz"

# 恢复数据
tar xzf $BACKUP_FILE -C /var/lib/docker/volumes/qdrant_data/_data

# 启动Qdrant服务
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant:latest
```

### 配置文件恢复

```bash
# 选择备份文件
BACKUP_FILE="/opt/backups/config/config_2026-04-04_04-00-00.tar.gz"

# 解压备份
tar xzf $BACKUP_FILE -C /tmp

# 恢复配置文件
cp /tmp/opt/rag-system/backend/.env /opt/rag-system/backend/
cp /tmp/etc/nginx/sites-available/rag-system /etc/nginx/sites-available/
cp /tmp/etc/systemd/system/rag-backend.service /etc/systemd/system/
cp /tmp/opt/prometheus/prometheus.yml /opt/prometheus/
cp /tmp/opt/alertmanager/alertmanager.yml /opt/alertmanager/

# 重启服务
systemctl daemon-reload
systemctl restart rag-backend
systemctl restart nginx
systemctl restart prometheus
systemctl restart alertmanager
```

## 数据迁移

### 数据库迁移

#### 导出数据

```bash
# 导出数据
pg_dump -U rag_user -d rag_db -F c > rag_db_backup.backup

# 压缩
gzip rag_db_backup.backup
```

#### 导入数据

```bash
# 解压
gunzip rag_db_backup.backup.gz

# 创建数据库
psql -U postgres -c "CREATE DATABASE rag_db OWNER rag_user;"

# 导入数据
pg_restore -U rag_user -d rag_db rag_db_backup.backup
```

### 向量存储迁移

#### 导出数据

```bash
# 停止Qdrant服务
docker stop qdrant

# 导出数据
tar czf qdrant_data.tar.gz /var/lib/docker/volumes/qdrant_data/_data

# 启动Qdrant服务
docker start qdrant
```

#### 导入数据

```bash
# 停止Qdrant服务
docker stop qdrant
docker rm qdrant

# 清理数据目录
rm -rf /var/lib/docker/volumes/qdrant_data/_data/*

# 导入数据
tar xzf qdrant_data.tar.gz -C /var/lib/docker/volumes/qdrant_data/_data

# 启动Qdrant服务
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant:latest
```

## 灾难恢复

### 灾难级别定义

| 级别 | 描述 | 恢复时间目标 |
|------|------|------------|
| 1 | 单个服务故障 | 15分钟 |
| 2 | 服务器故障 | 1小时 |
| 3 | 数据中心故障 | 4小时 |
| 4 | 区域性灾难 | 24小时 |

### 恢复计划

#### 级别1: 单个服务故障

1. 停止故障服务
2. 恢复服务配置
3. 启动服务
4. 验证服务状态

#### 级别2: 服务器故障

1. 准备新服务器
2. 安装必要软件
3. 恢复数据备份
4. 配置服务
5. 启动所有服务
6. 验证系统功能

#### 级别3: 数据中心故障

1. 切换到备用数据中心
2. 恢复最新备份
3. 启动所有服务
4. 验证系统功能
5. 切换流量

#### 级别4: 区域性灾难

1. 激活异地灾备站点
2. 恢复最新备份
3. 启动所有服务
4. 验证系统功能
5. 切换流量

## 备份验证

### 定期验证

```bash
# 创建验证脚本
cat > /opt/scripts/verify-backup.sh << EOF
#!/bin/bash

# 配置
BACKUP_DIR="/opt/backups/postgres"
TEST_DB="test_restore"

# 选择最新备份
LATEST_BACKUP=$(ls -t $BACKUP_DIR/*.backup.gz | head -1)

# 解压备份
gunzip -c $LATEST_BACKUP > /tmp/test_backup.backup

# 创建测试数据库
psql -U postgres -c "DROP DATABASE IF EXISTS $TEST_DB;"
psql -U postgres -c "CREATE DATABASE $TEST_DB OWNER rag_user;"

# 恢复测试
pg_restore -U rag_user -d $TEST_DB /tmp/test_backup.backup

# 验证恢复
if [ $? -eq 0 ]; then
  echo "备份验证成功"
else
  echo "备份验证失败"
fi

# 清理测试数据库
psql -U postgres -c "DROP DATABASE $TEST_DB;"
rm /tmp/test_backup.backup
EOF

# 设置执行权限
chmod +x /opt/scripts/verify-backup.sh

# 配置定时任务
crontab -e
# 添加以下行
0 5 * * 0 /opt/scripts/verify-backup.sh
```

### 恢复演练

1. **月度演练**: 执行完整恢复流程
2. **季度演练**: 测试异地恢复
3. **年度演练**: 模拟灾难场景

## 备份最佳实践

### 存储策略

- **3-2-1原则**: 3份备份，2种介质，1份异地
- **加密存储**: 所有备份都应加密
- **访问控制**: 严格控制备份访问权限
- **定期轮换**: 定期更换存储介质

### 自动化

- **自动备份**: 使用定时任务自动执行
- **自动验证**: 定期验证备份完整性
- **自动清理**: 自动清理过期备份
- **自动通知**: 备份结果通知

### 文档化

- **备份计划**: 详细的备份策略文档
- **恢复流程**: 详细的恢复步骤文档
- **演练记录**: 备份恢复演练记录
- **变更记录**: 备份策略变更记录

### 监控

- **备份状态**: 监控备份是否成功
- **存储使用**: 监控备份存储使用情况
- **恢复时间**: 监控恢复时间
- **告警机制**: 备份失败及时告警