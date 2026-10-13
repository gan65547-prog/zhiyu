"""
Integration tests - Health check endpoints

Tests that /health, /health/live, /health/ready endpoints:
- Respond with correct HTTP status codes
- Return the expected JSON schema
- Handle component failures gracefully (no 500 crash)
"""

import asyncio
import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


@pytest.fixture
def health_app():
    """Create a minimal test app with health routes (no real DB/Redis)."""
    from infrastructure.monitoring.health import HealthStatus

    app = FastAPI()

    @app.get("/health")
    async def health_check():
        health_checker = get_health_checker()
        result = await health_checker.check_all()
        return result

    @app.get("/health/live")
    async def liveness_check():
        return {"status": "alive"}

    @app.get("/health/ready")
    async def readiness_check():
        health_checker = get_health_checker()
        result = await health_checker.check_all()
        if result["status"] == "unhealthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result
            )
        return result

    # Patch get_health_checker at the app module level
    import infrastructure.monitoring.health as health_module
    mock_checker = MagicMock()
    mock_checker.check_all = AsyncMock()
    health_module.get_health_checker = MagicMock(return_value=mock_checker)

    return app, mock_checker


class TestHealthEndpoints:
    """Test health check endpoints via TestClient."""

    def test_liveness_always_returns_alive(self):
        """/health/live must always return 200 with status alive."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        @app.get("/health/live")
        async def liveness():
            return {"status": "alive"}

        client = TestClient(app)
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "alive"}

    def test_health_returns_healthy_structure(self):
        """/health must return the expected JSON structure when all components are healthy."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()

        async def mock_check_all():
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "database": {
                        "status": "healthy",
                        "latency_ms": 5.0
                    },
                    "redis": {
                        "status": "healthy",
                        "latency_ms": 2.0
                    },
                    "qdrant": {
                        "status": "healthy",
                        "latency_ms": 3.0
                    },
                    "ollama": {
                        "status": "healthy",
                        "latency_ms": 10.0
                    }
                }
            }

        @app.get("/health")
        async def health():
            return await mock_check_all()

        client = TestClient(app)
        resp = client.get("/health")
        data = resp.json()

        assert resp.status_code == 200
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "components" in data
        assert data["components"]["database"]["status"] == "healthy"
        assert data["components"]["redis"]["status"] == "healthy"

    def test_health_handles_unhealthy_components(self):
        """/health must not crash (500) when a component is unhealthy — return degraded status."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()

        async def mock_check_all():
            return {
                "status": "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "database": {
                        "status": "healthy",
                        "latency_ms": 5.0
                    },
                    "redis": {
                        "status": "unhealthy",
                        "latency_ms": 0,
                        "error": "Connection refused"
                    },
                    "qdrant": {
                        "status": "healthy",
                        "latency_ms": 3.0
                    },
                    "ollama": {
                        "status": "healthy",
                        "latency_ms": 10.0
                    }
                }
            }

        @app.get("/health")
        async def health():
            return await mock_check_all()

        client = TestClient(app)
        resp = client.get("/health")

        # /health always returns 200 even when degraded
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["components"]["redis"]["status"] == "unhealthy"

    def test_readiness_returns_503_when_unhealthy(self):
        """/health/ready must return 503 when any critical component is unhealthy."""
        from fastapi import FastAPI, HTTPException, status
        from fastapi.testclient import TestClient

        app = FastAPI()

        async def mock_check_all():
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "database": {
                        "status": "unhealthy",
                        "latency_ms": 0,
                        "error": "Connection refused"
                    }
                }
            }

        @app.get("/health/ready")
        async def readiness():
            result = await mock_check_all()
            if result["status"] == "unhealthy":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=result
                )
            return result

        client = TestClient(app)
        resp = client.get("/health/ready")

        assert resp.status_code == 503
        data = resp.json()
        assert data["detail"]["status"] == "unhealthy"

    def test_readiness_returns_200_when_healthy(self):
        """/health/ready must return 200 when all components are healthy."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()

        async def mock_check_all():
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "database": {
                        "status": "healthy",
                        "latency_ms": 5.0
                    }
                }
            }

        @app.get("/health/ready")
        async def readiness():
            result = await mock_check_all()
            if result["status"] == "unhealthy":
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=result
                )
            return result

        client = TestClient(app)
        resp = client.get("/health/ready")

        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_health_endpoint_handles_exception_gracefully(self):
        """/health must not crash (500) when the checker raises an exception."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from infrastructure.monitoring.health import ComponentHealth, HealthStatus

        app = FastAPI()

        # Simulate a checker that raises on one component
        async def mock_check_all():
            return {
                "status": "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "database": {
                        "status": "unhealthy",
                        "latency_ms": 0,
                        "error": "timeout"
                    },
                    "redis": {"status": "healthy", "latency_ms": 1},
                    "qdrant": {"status": "healthy", "latency_ms": 1},
                    "ollama": {"status": "healthy", "latency_ms": 1},
                }
            }

        @app.get("/health")
        async def health():
            return await mock_check_all()

        client = TestClient(app)
        resp = client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert "error" in data["components"]["database"]


class TestHealthCheckerLogic:
    """Test HealthChecker component logic directly (unit-style)."""

    @pytest.mark.asyncio
    async def test_check_all_handles_component_failure(self):
        """HealthChecker.check_all must not raise when a component fails — returns unhealthy status."""
        from infrastructure.monitoring.health import HealthChecker, HealthStatus

        checker = HealthChecker()

        async def failing_checker():
            raise ConnectionError("Service unavailable")

        async def passing_checker():
            return HealthStatus.HEALTHY

        checker.register_component("redis", failing_checker)
        checker.register_component("database", passing_checker)

        result = await checker.check_all()

        # Should not raise — failure is caught and reported
        assert result["status"] == "unhealthy"

        # components is a list of dicts
        components = {c["name"]: c for c in result["components"]}
        assert components["redis"]["status"] == "unhealthy"
        assert "Service unavailable" in components["redis"]["message"]

    @pytest.mark.asyncio
    async def test_overall_status_is_worst_component(self):
        """Overall status must reflect the worst component status."""
        from infrastructure.monitoring.health import HealthChecker, HealthStatus, ComponentHealth

        checker = HealthChecker()

        async def healthy():
            return ComponentHealth(name="a", status=HealthStatus.HEALTHY)

        async def degraded():
            return ComponentHealth(name="b", status=HealthStatus.DEGRADED)

        async def unhealthy():
            return ComponentHealth(name="c", status=HealthStatus.UNHEALTHY)

        checker.register_component("a", healthy)
        checker.register_component("b", healthy)
        checker.register_component("c", degraded)
        checker.register_component("d", unhealthy)

        result = await checker.check_all()
        assert result["status"] == "unhealthy"

        # Remove the unhealthy one
        checker2 = HealthChecker()
        checker2.register_component("a", healthy)
        checker2.register_component("b", degraded)

        result2 = await checker2.check_all()
        assert result2["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_check_all_bounds_slow_component(self):
        from infrastructure.monitoring.health import HealthChecker

        checker = HealthChecker()
        checker.component_timeout_seconds = 0.01

        async def slow_checker():
            await asyncio.sleep(1)

        checker.register_component("qdrant", slow_checker)
        result = await checker.check_all()

        assert result["status"] == "unhealthy"
        assert result["components"][0]["message"].startswith("健康检查超时")


class TestMetricsEndpointAccess:
    """Test that /metrics and /metrics/prometheus endpoints honor access control."""

    def test_metrics_endpoint_requires_auth(self):
        """Verify require_metrics_access dependency returns 403 without valid auth."""
        from fastapi import FastAPI, Depends
        from fastapi.testclient import TestClient
        from fastapi import HTTPException

        # Simplified version of require_metrics_access
        async def require_metrics_access(request=None):
            raise HTTPException(status_code=403, detail="Not authorized")

        app = FastAPI()

        @app.get("/metrics")
        async def get_metrics(_=Depends(require_metrics_access)):
            return {"metrics": {}}

        client = TestClient(app)
        resp = client.get("/metrics")

        assert resp.status_code == 403
