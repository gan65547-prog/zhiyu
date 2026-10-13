from app.services.circuit_breaker import SlidingWindowCircuitBreaker


def test_circuit_opens_after_threshold():
    cb = SlidingWindowCircuitBreaker()
    key = "/internal/admin/tenants"
    cb.record_failure(key, threshold=3, window_seconds=60, open_seconds=30, now=100)
    cb.record_failure(key, threshold=3, window_seconds=60, open_seconds=30, now=110)
    cb.record_failure(key, threshold=3, window_seconds=60, open_seconds=30, now=120)
    assert cb.is_open(key, now=125) is True


def test_circuit_resets_on_success():
    cb = SlidingWindowCircuitBreaker()
    key = "/internal/admin/tenants"
    cb.record_failure(key, threshold=1, window_seconds=60, open_seconds=30, now=100)
    assert cb.is_open(key, now=101) is True
    cb.record_success(key)
    assert cb.is_open(key, now=101) is False
