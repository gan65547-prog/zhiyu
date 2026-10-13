import sys
print("Python version:", sys.version)
print("sys.path:", sys.path)

# 尝试导入项目模块
try:
    from core.config import get_settings
    print("✓ Successfully imported core.config")
except Exception as e:
    print("✗ Failed to import core.config:", e)

try:
    from api.routers import auth_router
    print("✓ Successfully imported api.routers")
except Exception as e:
    print("✗ Failed to import api.routers:", e)

try:
    from services.audit.service import AuditService
    print("✓ Successfully imported services.audit.service")
except Exception as e:
    print("✗ Failed to import services.audit.service:", e)
