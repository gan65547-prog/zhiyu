# 生产环境部署

## 环境要求

- Linux服务器 (Ubuntu 20.04+ 或 CentOS 8+)
- 至少 8GB 内存
- 至少 50GB 磁盘空间
- PostgreSQL 15+
- Redis 7+
- Qdrant 1.5+
- Python 3.10+
- Node.js 18+

## 系统准备

### 安装依赖

```bash
# Ubuntu
apt update && apt install -y build-essential python3-pip python3-venv nginx certbot

# CentOS
yum update -y && yum install -y gcc python3-pip python3-venv nginx certbot
```

### 配置防火墙

```bash
# 开放必要端口
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp
ufw allow 6333/tcp
```

## 数据库配置

### 安装PostgreSQL

```bash
# Ubuntu
apt install -y postgresql postgresql-contrib

# CentOS
yum install -y postgresql-server postgresql-contrib
postgresql-setup --initdb
systemctl start postgresql
systemctl enable postgresql
```

### 创建数据库和用户

```bash
# 强制要求：生产环境禁止使用固定密码或示例密码。
# 先生成随机密码并放入密钥管理系统（如 Vault / AWS Secrets Manager）。
DB_PASSWORD="$(openssl rand -base64 32)"
echo "Generated password length: ${#DB_PASSWORD}"

sudo -u postgres psql
\set db_password `echo "$DB_PASSWORD"`
CREATE USER rag_user WITH PASSWORD :'db_password';
CREATE DATABASE rag_db OWNER rag_user;
GRANT ALL PRIVILEGES ON DATABASE rag_db TO rag_user;
\q
```

## 向量存储配置

### 安装Qdrant

```bash
# 使用Docker安装
 docker pull qdrant/qdrant:latest
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant:latest
```

### 配置Qdrant

```bash
# 创建配置文件
mkdir -p /etc/qdrant
cat > /etc/qdrant/config.yaml << EOF
host: 0.0.0.0
port: 6333
grpc_port: 6334
EOF
```

## 缓存配置

### 安装Redis

```bash
# Ubuntu
apt install -y redis-server

# CentOS
yum install -y redis
systemctl start redis
systemctl enable redis
```

### 配置Redis

```bash
# 编辑配置文件
vim /etc/redis/redis.conf

# 修改以下配置
bind 127.0.0.1
requirepass your_redis_password

# 重启服务
systemctl restart redis
```

## 后端部署

### 安装项目依赖

```bash
cd /opt
git clone <repository-url> rag-system
cd rag-system/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 配置环境变量

```bash
cat > .env << EOF
# 禁止将真实密钥提交到仓库，请通过 CI/CD 注入或 secrets 文件挂载。
DATABASE_URL=postgresql://rag_user:\${DB_PASSWORD}@localhost:5432/rag_db
REDIS_URL=redis://:\${REDIS_PASSWORD}@localhost:6379
QDRANT_URL=http://localhost:6333
JWT_SECRET=\${JWT_SECRET}
# 连接池配置（避免 worker 扩大后连接耗尽）
SQLALCHEMY_POOL_SIZE=10
SQLALCHEMY_MAX_OVERFLOW=20
SQLALCHEMY_POOL_RECYCLE=3600
SQLALCHEMY_POOL_TIMEOUT=30
EOF
```

### 配置Gunicorn

```bash
cat > gunicorn.conf.py << EOF
workers = 4
worker_class = 'uvicorn.workers.UvicornWorker'
bind = '0.0.0.0:8000'
timeout = 300
# 防止内存泄漏长期累积
max_requests = 1000
max_requests_jitter = 100
EOF
```

### 配置Systemd服务

```bash
cat > /etc/systemd/system/rag-backend.service << EOF
[Unit]
Description=RAG Backend Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/rag-system/backend
EnvironmentFile=/opt/rag-system/backend/.env
ExecStart=/opt/rag-system/backend/venv/bin/gunicorn -c gunicorn.conf.py main:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF
```

### 启动服务

```bash
systemctl daemon-reload
systemctl start rag-backend
systemctl enable rag-backend
```

## 前端部署

### 安装依赖

```bash
cd /opt/rag-system/frontend
npm install
```

### 构建项目

```bash
npm run build
```

### 配置Nginx

```bash
cat > /etc/nginx/sites-available/rag-system << EOF
limit_req_zone \$binary_remote_addr zone=api_limit:10m rate=10r/s;

server {
    listen 80;
    server_name your-domain.com;
    server_tokens off;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    location / {
        root /opt/rag-system/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        limit_req zone=api_limit burst=20 nodelay;
        client_max_body_size 20M;
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

### 启用站点

```bash
ln -s /etc/nginx/sites-available/rag-system /etc/nginx/sites-enabled/
systemctl restart nginx
```

## SSL配置

### 申请SSL证书

```bash
certbot --nginx -d your-domain.com
```

### 自动续期

```bash
crontab -e
# 添加以下行
0 12 * * * /usr/bin/certbot renew --quiet
```

## 性能优化

### 数据库优化

```bash
# 编辑PostgreSQL配置
vim /etc/postgresql/15/main/postgresql.conf

# 修改以下配置
shared_buffers = 2GB
work_mem = 32MB
maintenance_work_mem = 1GB
effective_cache_size = 6GB
random_page_cost = 1.1
```

### Nginx优化

```bash
# 编辑Nginx配置
vim /etc/nginx/nginx.conf

# 添加以下配置
http {
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_comp_level 6;
    gzip_min_length 256;
    gzip_vary on;

    client_max_body_size 100M;

    keepalive_timeout 65;
    keepalive_requests 100000;
}
```

### 应用优化

- 启用缓存
- 优化查询
- 使用异步处理
- 合理配置Gunicorn workers

## 安全加固

### 系统安全

- 定期更新系统
- 配置防火墙
- 使用非root用户
- 禁用不必要的服务

### 应用安全

- 使用HTTPS
- 配置CORS
- 实施Rate Limiting
- 定期审计代码

## 监控告警

### 配置Prometheus

```bash
# 安装Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.45.6/prometheus-2.45.6.linux-amd64.tar.gz
tar xvf prometheus-2.45.6.linux-amd64.tar.gz
cd prometheus-2.45.6.linux-amd64
./prometheus --config.file=prometheus.yml
```

### 配置Grafana

```bash
# 安装Grafana
apt install -y grafana
systemctl start grafana-server
systemctl enable grafana-server
```

### 配置告警

- 服务状态告警
- 资源使用告警
- 错误率告警
- 响应时间告警

## 备份策略

### 数据库备份

```bash
# 创建备份脚本
cat > /opt/backup-db.sh << EOF
#!/bin/bash
set -euo pipefail
DATE=$(date +%Y-%m-%d)
if ! pg_dump -U rag_user -d rag_db > /opt/backups/rag_db_$DATE.sql; then
  echo "[\$(date -Is)] ERROR: backup db failed" >> /var/log/rag-backup.log
  exit 1
fi
tar -czf /opt/backups/rag_db_$DATE.tar.gz /opt/backups/rag_db_$DATE.sql
rm /opt/backups/rag_db_$DATE.sql
# 保留30天备份
find /opt/backups -name "rag_db_*.tar.gz" -mtime +30 -delete
EOF

# 配置定时任务
crontab -e
0 2 * * * /opt/backup-db.sh
```

### Qdrant备份

```bash
# 创建备份脚本
cat > /opt/backup-qdrant.sh << EOF
#!/bin/bash
DATE=$(date +%Y-%m-%d)
docker exec qdrant tar czf /tmp/qdrant_backup_$DATE.tar.gz /qdrant/storage
docker cp qdrant:/tmp/qdrant_backup_$DATE.tar.gz /opt/backups/
docker exec qdrant rm /tmp/qdrant_backup_$DATE.tar.gz
# 保留30天备份
find /opt/backups -name "qdrant_backup_*.tar.gz" -mtime +30 -delete
EOF

# 配置定时任务
crontab -e
0 3 * * * /opt/backup-qdrant.sh
```

## 故障恢复

### 数据库恢复

```bash
# 恢复最新备份
tar xzf /opt/backups/rag_db_$(date +%Y-%m-%d).tar.gz
psql -U rag_user -d rag_db < /opt/backups/rag_db_$(date +%Y-%m-%d).sql
```

### Qdrant恢复

```bash
# 停止服务
docker stop qdrant
docker rm qdrant

# 恢复备份
tar xzf /opt/backups/qdrant_backup_$(date +%Y-%m-%d).tar.gz -C /opt/qdrant_data

# 重启服务
docker run -d --name qdrant -p 6333:6333 -v /opt/qdrant_data:/qdrant/storage qdrant/qdrant:latest
```

## 版本升级

### 备份数据

```bash
# 执行全量备份
/opt/backup-db.sh
/opt/backup-qdrant.sh
```

### 更新代码

```bash
cd /opt/rag-system
git pull
```

### 升级依赖

```bash
# 后端
cd backend
source venv/bin/activate
pip install -r requirements.txt

# 前端
cd ../frontend
npm install
npm run build
```

### 重启服务

```bash
systemctl restart rag-backend
systemctl restart nginx
```