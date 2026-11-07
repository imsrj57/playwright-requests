from locust import User, task, between, events
import subprocess
import os
import time

class PytestUser(User):
    wait_time = between(1, 2)

    @task
    def run_pytest(self):
        marker = os.getenv("PYTEST_MARKER", "")
        start_time = time.time()

        try:
            print(f"Running pytest for marker: {marker}")

            result = subprocess.run(
                [
                    "pytest",
                    "-m", marker,
                    "--tb=short",
                    "--disable-warnings"
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            total_time = int((time.time() - start_time) * 1000)

            events.request.fire(
                request_type="pytest",
                name=f"pytest::{marker}",
                response_time=total_time,
                response_length=len(result.stdout + result.stderr),
                context={},
                exception=None if result.returncode == 0 else Exception("Test failed"),
            )

        except Exception as e:
            events.request.fire(
                request_type="pytest",
                name=f"pytest::{marker}",
                response_time=int((time.time() - start_time) * 1000),
                response_length=0,
                context={},
                exception=e,
            )
