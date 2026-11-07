"""
Pytest Plugin for Quick Report Generation
Generates fast summary reports during test execution.
Enable with: pytest -p conftest_plugin --alluredir=allure-results/local
"""

import json
from pathlib import Path
from collections import defaultdict


class QuickReportPlugin:
    """Pytest plugin to track results and generate quick reports"""

    def __init__(self):
        self.results = defaultdict(int)
        self.tests = []
        self.allure_dir = None

    def pytest_configure(self, config):
        """Called after command line options are parsed"""
        # Register the plugin
        config.addinivalue_line("markers", "quick_report: Tests tracked for quick reports")

    def pytest_sessionstart(self, session):
        """Called after pytest sessions starts"""
        self.results = {"passed": 0, "failed": 0, "skipped": 0, "broken": 0}

    def pytest_runtest_makereport(self, item, call):
        """Called for each test result"""
        pass

    def pytest_sessionfinish(self, session, exitstatus):
        """Called after pytest session finishes"""
        # Get allure results directory
        try:
            allure_dir = session.config.getoption("--alluredir")
        except ValueError:  # allure-pytest not installed
            allure_dir = None

        if not allure_dir:
            return

        # Parse allure results
        self._parse_and_report(allure_dir)

    def _parse_and_report(self, allure_dir):
        """Parse allure results and generate quick report"""
        allure_path = Path(allure_dir)
        if not allure_path.exists():
            return

        results = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "broken": 0,
            "total": 0
        }

        result_files = list(allure_path.glob("*-result.json"))
        
        for result_file in result_files:
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                    status = result.get("status", "unknown")
                    
                    if status in results:
                        results[status] += 1
                    
                    results["total"] += 1
            except (json.JSONDecodeError, IOError):
                pass

        # Print summary
        print("\n" + "="*70)
        print("QUICK TEST SUMMARY (Allure Report Being Generated)")
        print("="*70)
        print(f"Total Tests: {results['total']}")
        print(f"✓ Passed:    {results['passed']}")
        print(f"✗ Failed:    {results['failed']}")
        print(f"⚠ Skipped:   {results['skipped']}")
        print(f"⛔ Broken:    {results['broken']}")
        print("="*70)
        print("Full Allure Report will be available as artifact download")
        print("="*70 + "\n")


def pytest_configure(config):
    """Allow `pytest -p conftest_plugin ...` to enable the quick summary."""
    if not config.pluginmanager.has_plugin("quick_report_plugin"):
        config.pluginmanager.register(QuickReportPlugin(), "quick_report_plugin")
