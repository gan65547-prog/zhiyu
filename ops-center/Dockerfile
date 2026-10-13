FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static
# 仅示例文件进镜像；真实密钥用 compose/K8s 的 env / env_file 在运行时注入，勿把 .env 打进镜像
COPY .env.example ./.env.example

EXPOSE 8081

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; \
resp=urllib.request.urlopen('http://127.0.0.1:8081/health/ready', timeout=3); \
sys.exit(0 if resp.getcode()==200 else 1)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
