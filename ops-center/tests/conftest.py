import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 测试环境下游网关必须可秒拒（连接拒绝 → 502）。
# 默认 business_base_url 指向 host.docker.internal:8000，在非容器环境可能
# 挂起至 request_timeout_seconds 才超时（→ 504），使
# test_read_only_may_call_tenants_list 的 {200,502,503} 断言随环境漂移。
# 需要真实上游行为的测试一律 monkeypatch BusinessGateway.request，不受此影响。
os.environ["BUSINESS_BASE_URL"] = "http://127.0.0.1:9"
os.environ.setdefault("AUTH_SECRET_KEY", "test-only-auth-signing-secret-not-for-deployment")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "test-only-password-not-for-deployment")
