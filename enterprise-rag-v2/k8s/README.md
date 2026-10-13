# Enterprise RAG v2 — K8s 部署说明
#
# 1. 创建命名空间
#   kubectl apply -f k8s/namespace.yaml
#
# 2. 创建基础设施（PostgreSQL、Redis、Qdrant）
#   建议使用 Operator 或 Helm Chart 部署有状态服务，或在集群外复用已有实例。
#   这里提供快速开发的 StatefulSet 示例，生产环境推荐：
#   - PostgreSQL: Crunchy Data Operator / AWS RDS
#   - Redis:  Redis Operator / AWS ElastiCache
#   - Qdrant: 官方 Helm Chart
#
# 3. 创建 ConfigMap 和 Secret（必须先编辑 secret.yaml 中的密钥）
#   kubectl apply -f k8s/configmap.yaml
#   kubectl apply -f k8s/secret.yaml
#
# 4. 创建持久卷声明
#   kubectl apply -f k8s/pvc.yaml
#
# 5. 部署应用
#   kubectl apply -f k8s/deployment-web.yaml
#   kubectl apply -f k8s/deployment-worker.yaml
#   kubectl apply -f k8s/service.yaml
#
# 6. 配置 Ingress（需要先安装 ingress-nginx 和 cert-manager）
#   kubectl apply -f k8s/ingress.yaml
#
# 7. 配置自动扩缩
#   kubectl apply -f k8s/hpa.yaml
#
# === 镜像构建与推送 ===
# docker build -t registry.example.com/enterprise-rag-v2:latest .
# docker push registry.example.com/enterprise-rag-v2:latest
# 然后更新 deployment-web.yaml 和 deployment-worker.yaml 中的 image 字段
