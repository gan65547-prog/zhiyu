from datetime import datetime

import pytest

from services.impl.agent_runtime_service import next_schedule_time


def test_schedule_supports_every_five_minutes():
    assert next_schedule_time("*/5 * * * *", datetime(2026, 8, 5, 10, 2)) == datetime(2026, 8, 5, 10, 5)


def test_schedule_supports_daily_time():
    assert next_schedule_time("30 9 * * *", datetime(2026, 8, 5, 10, 2)) == datetime(2026, 8, 6, 9, 30)


@pytest.mark.parametrize("expression", ["* * * * *", "0 0 1 * *", "*/0 * * * *"])
def test_schedule_rejects_unsupported_expression(expression):
    with pytest.raises(ValueError):
        next_schedule_time(expression, datetime(2026, 8, 5, 10, 2))
