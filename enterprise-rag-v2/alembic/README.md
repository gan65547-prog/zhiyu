# Alembic数据库迁移

## 初始化

Alembic已经配置完成，可以直接使用。

## 常用命令

### 1. 生成迁移脚本

```bash
# 自动生成迁移脚本（基于模型变更）
alembic revision --autogenerate -m "描述信息"

# 手动创建空白迁移脚本
alembic revision -m "描述信息"
```

### 2. 执行迁移

```bash
# 升级到最新版本
alembic upgrade head

# 升级到指定版本
alembic upgrade <revision_id>

# 升级一个版本
alembic upgrade +1
```

### 3. 回滚迁移

```bash
# 回滚到上一个版本
alembic downgrade -1

# 回滚到指定版本
alembic downgrade <revision_id>

# 回滚所有迁移
alembic downgrade base
```

### 4. 查看迁移历史

```bash
# 查看当前版本
alembic current

# 查看迁移历史
alembic history

# 查看详细历史
alembic history --verbose
```

## 初始迁移

创建初始数据库schema：

```bash
# 1. 生成初始迁移脚本
alembic revision --autogenerate -m "Initial schema"

# 2. 执行迁移
alembic upgrade head
```

## 配置

数据库连接URL从环境变量 `DATABASE_URL` 读取，确保在 `.env` 文件中配置：

```
DATABASE_URL=postgresql://user:password@localhost:5432/enterprise_rag
```

## 迁移脚本位置

所有迁移脚本存储在 `alembic/versions/` 目录下。

## 注意事项

1. 每次修改 `infrastructure/database/models.py` 后，都需要生成新的迁移脚本
2. 在生产环境执行迁移前，务必先在测试环境验证
3. 重要的数据变更应该编写数据迁移脚本
4. 迁移脚本应该纳入版本控制
