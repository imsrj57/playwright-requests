import os
import subprocess
import datetime

# Set default environment variables (you can override them when calling this script)
PYTEST_MARKER = os.getenv("PYTEST_MARKER", "apisanity")
LOCUST_USERS = os.getenv("LOCUST_USERS", "10")
LOCUST_DURATION = os.getenv("LOCUST_DURATION", "30")

# Generate timestamped folder for CSV results
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
csv_folder = os.path.join("loadresult", timestamp)
os.makedirs(csv_folder, exist_ok=True)
# Construct the locust command
locust_command = [
    "locust",
    "-f", "api/utils/locust_pytest_runner.py",
    "--headless",
    "--users", LOCUST_USERS,
    "--spawn-rate", "2",
    "--run-time", f"{LOCUST_DURATION}s",
    "--csv", os.path.join(csv_folder, "result")
]

# Set the environment variable for the pytest marker
env = os.environ.copy()
env["PYTEST_MARKER"] = PYTEST_MARKER

# Run the Locust command
print(f"Running Locust with marker={PYTEST_MARKER}, users={LOCUST_USERS}, duration={LOCUST_DURATION}s")
subprocess.run(locust_command, env=env)
