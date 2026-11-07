"""
Polling helpers — use these instead of fixed `time.sleep()` in tests.
"""

import time
from typing import Any, Callable, Optional


def wait_for_condition(
    condition_fn: Callable[[], Any],
    max_wait: float = 30.0,
    interval: float = 1.5,
    expected_value: Any = None,
    description: str = "condition",
) -> Any:
    """
    Poll condition_fn() every `interval` seconds until it returns a truthy value
    (or equals `expected_value` when given). Returns that value, or None on timeout.

    Args:
        condition_fn:    Callable that returns the value to check
        max_wait:        Ceiling in seconds
        interval:        How often to poll (seconds)
        expected_value:  If set, keep polling until result == expected_value
        description:     Label printed in logs for visibility
    """
    deadline = time.time() + max_wait
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        try:
            result = condition_fn()
            if expected_value is not None:
                if result == expected_value:
                    print(f"[wait_for_condition] '{description}' met after {attempt} attempt(s)")
                    return result
            elif result:
                print(f"[wait_for_condition] '{description}' met after {attempt} attempt(s)")
                return result
        except Exception as e:
            print(f"[wait_for_condition] attempt {attempt} raised: {e}")

        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))

    print(f"[wait_for_condition] '{description}' timed out after {max_wait}s ({attempt} attempts)")
    return None


def wait_for_state(
    fetch_fn: Callable[[], Optional[dict]],
    state_key: str,
    expected_state: Any,
    max_wait: float = 30.0,
    interval: float = 2.0,
    description: str = "resource state",
) -> Optional[dict]:
    """
    Poll fetch_fn() until response[state_key] == expected_state. Returns the dict or None.

    Example:
        order = wait_for_state(
            fetch_fn=lambda: api_client.get(f"/orders/{order_id}").json(),
            state_key="status",
            expected_state="COMPLETED",
        )
        assert order, "order never reached COMPLETED"
    """
    def _check():
        result = fetch_fn()
        if result and result.get(state_key) == expected_state:
            return result
        return None

    return wait_for_condition(
        condition_fn=_check,
        max_wait=max_wait,
        interval=interval,
        description=f"{description} -> {state_key}=={expected_state}",
    )


def wait_for_key(
    fetch_fn: Callable[[], Optional[dict]],
    key: str,
    max_wait: float = 30.0,
    interval: float = 2.0,
) -> Any:
    """Poll fetch_fn() until the returned dict has a non-empty `key`; return that value."""
    def _check():
        result = fetch_fn()
        if result and result.get(key):
            return result.get(key)
        return None

    return wait_for_condition(_check, max_wait=max_wait, interval=interval, description=f"key '{key}'")


def wait_for_db_record(
    fetch_fn: Callable[[], Any],
    max_wait: float = 30.0,
    interval: float = 1.5,
) -> Any:
    """
    Poll fetch_fn() until it returns a non-empty result (e.g. a DB row list).

    Example:
        rows = wait_for_db_record(lambda: fetch_all(conn, "SELECT ... WHERE id = ?", [record_id]))
    """
    return wait_for_condition(fetch_fn, max_wait=max_wait, interval=interval, description="DB record")
