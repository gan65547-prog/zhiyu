# 监控配置

## 监控架构

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   应用服务      │─────>│   Prometheus    │─────>│    Grafana      │
└─────────────────┘      └─────────────────┘      └─────────────────┘
        ▲                      ▲                      ▲
        │                      │                      │
        ▼                      ▼                      ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   数据库服务    │─────>│   Alertmanager  │─────>│    告警通知      │
└─────────────────┘      └─────────────────┘      └─────────────────┘
        ▲                      ▲
        │                      │
        ▼                      ▼
┌─────────────────┐      ┌─────────────────┐
│   向量存储服务   │─────>│   日志收集      │
└─────────────────┘      └─────────────────┘
```

## Prometheus配置

### 安装Prometheus

```bash
# 下载Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.45.6/prometheus-2.45.6.linux-amd64.tar.gz

# 解压安装
tar xvf prometheus-2.45.6.linux-amd64.tar.gz
mv prometheus-2.45.6.linux-amd64 /opt/prometheus

# 创建系统服务
cat > /etc/systemd/system/prometheus.service << EOF
[Unit]
Description=Prometheus
After=network.target

[Service]
Type=simple
# 避免明文密码，建议从 EnvironmentFile 注入
ExecStart=/opt/prometheus/prometheus \
  --config.file=/opt/prometheus/prometheus.yml \
  --storage.tsdb.path=/opt/prometheus/data \
  --web.console.templates=/opt/prometheus/consoles \
  --web.console.libraries=/opt/prometheus/console_libraries

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
systemctl daemon-reload
systemctl start prometheus
systemctl enable prometheus
```

### 配置文件

```yaml
# /opt/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alerts/*.yml"

scrape_configs:
  - job_name: 'backend'
    static_configs:
      - targets: ['localhost:8000']

  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']

  - job_name: 'qdrant'
    static_configs:
      - targets: ['localhost:6333']

  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']
```

## Node Exporter配置

### 安装Node Exporter

```bash
# 下载Node Exporter
wget https://github.com/prometheus/node_exporter/releases/download/v1.5.0/node_exporter-1.5.0.linux-amd64.tar.gz

# 解压安装
tar xvf node_exporter-1.5.0.linux-amd64.tar.gz
mv node_exporter-1.5.0.linux-amd64/node_exporter /usr/local/bin/

# 创建系统服务
cat > /etc/systemd/system/node_exporter.service << EOF
[Unit]
Description=Node Exporter
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
systemctl daemon-reload
systemctl start node_exporter
systemctl enable node_exporter
```

## PostgreSQL Exporter配置

### 安装PostgreSQL Exporter

```bash
# 下载PostgreSQL Exporter
wget https://github.com/prometheus-community/postgres_exporter/releases/download/v0.13.0/postgres_exporter-0.13.0.linux-amd64.tar.gz

# 解压安装
tar xvf postgres_exporter-0.13.0.linux-amd64.tar.gz
mv postgres_exporter-0.13.0.linux-amd64/postgres_exporter /usr/local/bin/

# 创建系统服务
cat > /etc/systemd/system/postgres_exporter.service << EOF
[Unit]
Description=PostgreSQL Exporter
After=network.target

[Service]
Type=simple
EnvironmentFile=/etc/default/postgres_exporter
ExecStart=/usr/local/bin/postgres_exporter

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
systemctl daemon-reload
systemctl start postgres_exporter
systemctl enable postgres_exporter
```

## Redis Exporter配置

### 安装Redis Exporter

```bash
# 下载Redis Exporter
wget https://github.com/oliver006/redis_exporter/releases/download/v1.47.0/redis_exporter-v1.47.0.linux-amd64.tar.gz

# 解压安装
tar xvf redis_exporter-v1.47.0.linux-amd64.tar.gz
mv redis_exporter-v1.47.0.linux-amd64/redis_exporter /usr/local/bin/

# 创建系统服务
cat > /etc/systemd/system/redis_exporter.service << EOF
[Unit]
Description=Redis Exporter
After=network.target

[Service]
Type=simple
EnvironmentFile=/etc/default/redis_exporter
ExecStart=/usr/local/bin/redis_exporter --redis.addr=redis://localhost:6379 --redis.password=$REDIS_PASSWORD

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
systemctl daemon-reload
systemctl start redis_exporter
systemctl enable redis_exporter
```

## Grafana配置

### 安装Grafana

```bash
# 添加Grafana源
wget -q -O - https://packages.grafana.com/gpg.key | apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" > /etc/apt/sources.list.d/grafana.list

# 安装Grafana
apt update
apt install -y grafana

# 启动服务
systemctl start grafana-server
systemctl enable grafana-server
```

### 配置数据源

1. 访问 http://localhost:3000
2. 登录（默认用户名/密码：admin/admin）
3. 点击 "Configuration" > "Data sources"
4. 点击 "Add data source"
5. 选择 "Prometheus"
6. 配置URL为 http://localhost:9090
7. 点击 "Save & Test"

### 导入仪表盘

1. 点击 "Create" > "Import"
2. 输入仪表盘ID：
   - 1860 (Node Exporter Full)
   - 9628 (PostgreSQL)
   - 763 (Redis)
   - 14983 (FastAPI)
3. 选择Prometheus数据源
4. 点击 "Import"

## 告警配置

### Alertmanager配置

```bash
# 下载Alertmanager
wget https://github.com/prometheus/alertmanager/releases/download/v0.25.0/alertmanager-0.25.0.linux-amd64.tar.gz

# 解压安装
tar xvf alertmanager-0.25.0.linux-amd64.tar.gz
mv alertmanager-0.25.0.linux-amd64 /opt/alertmanager

# 创建配置文件
cat > /opt/alertmanager/alertmanager.yml << EOF
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 1h
  receiver: 'email'

receivers:
- name: 'email'
  email_configs:
  - to: 'alerts@example.com'
    from: 'prometheus@example.com'
    smarthost: 'smtp.example.com:587'
    auth_username: 'prometheus'
    auth_password: 'password'
    require_tls: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'dev', 'instance']
EOF

# 创建系统服务
cat > /etc/systemd/system/alertmanager.service << EOF
[Unit]
Description=Alertmanager
After=network.target

[Service]
Type=simple
ExecStart=/opt/alertmanager/alertmanager \
  --config.file=/opt/alertmanager/alertmanager.yml \
  --storage.path=/opt/alertmanager/data

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
systemctl daemon-reload
systemctl start alertmanager
systemctl enable alertmanager
```

### 告警规则

```yaml
# /opt/prometheus/alerts/rules.yml
groups:
- name: node_alerts
  rules:
  - alert: HighCPUUsage
    expr: (100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)) > 80
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High CPU Usage"
      description: "CPU usage is above 80% for 5 minutes"

  - alert: HighMemoryUsage
    expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 80
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High Memory Usage"
      description: "Memory usage is above 80% for 5 minutes"

- name: backend_alerts
  rules:
  - alert: BackendDown
    expr: up{job="backend"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Backend Service Down"
      description: "Backend service is down for 2 minutes"

  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High Error Rate"
      description: "Error rate is above 10% for 5 minutes"

- name: database_alerts
  rules:
  - alert: PostgresDown
    expr: up{job="postgres"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "PostgreSQL Down"
      description: "PostgreSQL is down for 2 minutes"

  - alert: HighQueryLatency
    expr: pg_stat_statements_total_time_seconds / pg_stat_statements_calls > 0.5
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High Query Latency"
      description: "Average query latency is above 500ms for 5 minutes"
```

### 规则语法校验（上线前必做）

```bash
promtool check rules /opt/prometheus/alerts/rules.yml
promtool check config /opt/prometheus/prometheus.yml
```

## 日志收集

### 安装ELK Stack

```bash
# 安装Elasticsearch
wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | apt-key add -
echo "deb https://artifacts.elastic.co/packages/8.x/apt stable main" > /etc/apt/sources.list.d/elastic-8.x.list
apt update
apt install -y elasticsearch

# 安装Logstash
apt install -y logstash

# 安装Kibana
apt install -y kibana

# 启动服务
systemctl start elasticsearch
systemctl start logstash
systemctl start kibana
systemctl enable elasticsearch
systemctl enable logstash
systemctl enable kibana
```

### 配置Filebeat

```bash
# 安装Filebeat
apt install -y filebeat

# 配置Filebeat
cat > /etc/filebeat/filebeat.yml << EOF
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/nginx/access.log
    - /var/log/nginx/error.log
    - /opt/rag-system/backend/logs/*.log

output.elasticsearch:
  hosts: ["localhost:9200"]
EOF

# 启动服务
systemctl start filebeat
systemctl enable filebeat
```

## 监控面板

### 系统监控面板

- CPU使用率
- 内存使用率
- 磁盘使用率
- 网络流量
- 系统负载

### 应用监控面板

- 请求量
- 响应时间
- 错误率
- 活跃会话
- 缓存命中率

### 数据库监控面板

- 连接数
- 查询执行时间
- 索引使用情况
- 表大小
- 死锁情况

### 向量存储监控面板

- 向量数量
- 索引大小
- 查询延迟
- 写入速度
- 内存使用

## 告警通知

### 邮件通知

- 配置SMTP服务器
- 设置告警接收邮箱
- 配置告警级别

### 即时通讯通知

- Slack集成
- Telegram集成
- WeChat集成
- Discord集成

### 短信通知

- 配置短信网关
- 设置告警触发条件
- 限制短信发送频率

## 监控最佳实践

### 监控指标选择

- 业务相关指标
- 系统资源指标
- 应用性能指标
- 错误率指标

### 告警阈值设置

- 基于历史数据
- 考虑业务高峰
- 设置合理的持续时间
- 避免告警风暴

### 监控覆盖范围

- 所有生产服务
- 关键依赖服务
- 网络连接
- 存储系统

### 定期检查

- 监控系统健康状态
- 告警规则有效性
- 数据存储增长
- 监控系统性能