"""
Enhanced Allure-Style Report Generator with Complete Test Details
Generates interactive HTML report with screenshots, attachments, steps, failures, and performance analytics
Features:
- Card-based layout with expand/collapse for each test
- Screenshot and attachment display
- API response (JSON) formatting
- Test execution steps with status
- Failure traces and error messages
- Search/filter panel on left sidebar
- Performance Analytics: Duration insights, test tiers, module breakdown
- Real-time alert system
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import html as html_lib
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import base64
import statistics
from abc import ABC, abstractmethod


# ============================================================================
# ADVANCED ANALYTICS ENGINES
# ============================================================================

class AnomalyDetector(ABC):
    """Abstract base for anomaly detection strategies"""
    @abstractmethod
    def detect(self, values: List[float]) -> Tuple[bool, float, str]:
        """Detect anomaly and return (is_anomaly, score, reason)"""
        pass


class PerformanceAnalyzer:
    """Analyzes test performance metrics and durations"""
    
    @staticmethod
    def extract_module_from_test(test_name: str) -> str:
        """Extract module/category from test name using common patterns"""
        # Remove file extension and path
        test_name = test_name.split("::")[-1] if "::" in test_name else test_name
        test_name = test_name.split("/")[-1] if "/" in test_name else test_name
        
        # Remove 'test_' prefix and extract first part
        if test_name.startswith("test_"):
            test_name = test_name[5:]
        
        # Get first word/component
        parts = test_name.split("_")
        if parts:
            # If it looks like a verb (action), skip it and take next word
            actions = {"create", "delete", "update", "get", "post", "put", "patch", "verify", "check", "validate"}
            if parts[0].lower() in actions and len(parts) > 1:
                return parts[1].title()
            return parts[0].title()
        
        return "Other"
    
    @staticmethod
    def get_duration_tier(duration_ms: float) -> str:
        """Categorize test by duration"""
        seconds = duration_ms / 1000
        if seconds < 1:
            return "< 1s"
        elif seconds < 5:
            return "1-5s"
        elif seconds < 30:
            return "5-30s"
        else:
            return "30s+"
    
    @staticmethod
    def get_tier_color(tier: str) -> str:
        """Get color for duration tier"""
        colors = {
            "< 1s": "#27ae60",      # Green
            "1-5s": "#f39c12",      # Orange
            "5-30s": "#e67e22",     # Dark Orange
            "30s+": "#e74c3c"       # Red
        }
        return colors.get(tier, "#999")


@dataclass
class FailureAnalysis:
    """Detailed failure analysis"""
    category: str
    message: str
    trace: str
    http_code: Optional[int] = None
    error_type: Optional[str] = None


@dataclass
class TestExecution:
    """Single test execution record"""
    test_name: str
    status: str
    duration: float
    timestamp: str
    failure: Optional[FailureAnalysis] = None
    labels: List[Dict] = field(default_factory=list)
    steps: List[Dict] = field(default_factory=list)
    attachments: List[Dict] = field(default_factory=list)
    description: str = ""


@dataclass
class ExecutionRun:
    """Single test run/execution session"""
    timestamp: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    broken: int
    duration: float
    test_results: Dict[str, TestExecution] = field(default_factory=dict)


class AllureReportGenerator:
    """Generates enhanced Allure-style reports with complete features"""
    
    def __init__(self, allure_results_dir: str, test_tag: str = None, test_browser: str = None, test_env: str = None):
        self.allure_results_dir = Path(allure_results_dir)
        self.test_tag = test_tag or "N/A"
        self.test_browser = test_browser or "N/A"
        self.test_env = test_env or "N/A"
        self.state = None
        self.results = {
            "passed": 0, "failed": 0, "skipped": 0, "broken": 0, "total": 0,
            "duration": 0, "tests": [], "timestamp": datetime.now().isoformat()
        }

    @staticmethod
    def _clean_trace(trace: str) -> Tuple[str, str, str]:
        """Strip tokens/variable dumps; return (key_error, file_ref, cleaned_trace)."""
        lines = trace.split('\n')

        # Extract key error BEFORE cleaning (use original lines for pattern matching)
        e_lines = [l.strip()[2:].strip() for l in lines if re.match(r'\s*E\s', l)]
        key_error = e_lines[-1] if e_lines else ""

        # File:line reference (last assertion line)
        file_lines = [l.strip() for l in lines if re.search(r'\.py:\d+:', l)]
        file_ref = file_lines[-1] if file_lines else ""

        # Clean the trace for the collapsible section
        filtered = []
        for line in lines:
            # Remove variable-assignment lines that contain JWT tokens (e.g. access_token = 'eyJ...')
            if re.search(r"=\s*'eyJ|=\s*\"eyJ", line):
                var_name = line.split('=')[0].strip()
                filtered.append(f"{var_name} = [JWT_TOKEN]")
                continue
            # Truncate huge inline dict/config lines
            if len(line) > 250 and ('{' in line or "config" in line.lower()):
                filtered.append(line[:150] + '  ...[truncated]')
                continue
            filtered.append(line)

        # Also strip any remaining JWT patterns (full or Allure-truncated with '...')
        cleaned = '\n'.join(filtered)
        cleaned = re.sub(r"eyJ[A-Za-z0-9_\-]+(?:\.\.\.[A-Za-z0-9_\-]*)*\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", '[JWT]', cleaned)

        return key_error, file_ref, cleaned

    def _detect_failure_category(self, message: str, trace: str, status: str) -> Tuple[str, Optional[int], Optional[str]]:
        """Detect failure category and HTTP code"""
        combined = (message + " " + trace).lower()
        
        http_code = None
        http_match = re.search(r'\b(\d{3})\b', combined)
        if http_match:
            http_code = int(http_match.group(1))
        
        if re.search(r'(assert|expected|actual)', combined):
            return ("assertion", http_code, "AssertionError")
        elif re.search(r'(timeout|timed out)', combined):
            return ("timeout", http_code, "TimeoutError")
        elif re.search(r'(exception|error)', combined):
            return ("exception", http_code, "Exception")
        else:
            return ("other", http_code, None)

    def parse_results(self) -> dict:
        """Parse allure results"""
        if not self.allure_results_dir.exists():
            print(f"Warning: {self.allure_results_dir} not found")
            return self.results

        result_files = sorted(self.allure_results_dir.glob("*-result.json"))
        test_results = {}
        
        for result_file in result_files:
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                    
                    status = result.get("status", "unknown")
                    name = result.get("name", "Unknown Test")
                    duration = result.get("stop", 0) - result.get("start", 0)
                    
                    # Detect test type from titlePath or parentSuite label
                    title_path = result.get("titlePath", [])
                    tp_root = (title_path[0] if title_path else "").lower()
                    if tp_root == "api":
                        test_type = "api"
                    elif tp_root in ("web", "ui"):
                        test_type = "ui"
                    else:
                        parent_suite = next((l["value"] for l in result.get("labels", []) if l["name"] == "parentSuite"), "")
                        test_type = "api" if "api" in parent_suite.lower() else "ui" if any(x in parent_suite.lower() for x in ("web", "ui")) else "other"

                    suite_name = next((l["value"] for l in result.get("labels", []) if l["name"] == "suite"), "")

                    failure_info = None
                    if status in ["failed", "broken"]:
                        status_details = result.get("statusDetails", {})
                        message = status_details.get("message", "No error message")
                        raw_trace = status_details.get("trace", "No trace")
                        key_error, file_ref, clean_trace = self._clean_trace(raw_trace)
                        category, http_code, error_type = self._detect_failure_category(message, raw_trace, status)
                        failure_info = FailureAnalysis(category, message, clean_trace, http_code, error_type)
                        failure_info.key_error = key_error
                        failure_info.file_ref = file_ref
                    else:
                        key_error = ""
                    
                    execution = TestExecution(
                        test_name=html_lib.escape(name),
                        status=status,
                        duration=duration,
                        timestamp=datetime.now().isoformat(),
                        failure=failure_info,
                        labels=result.get("labels", []),
                        steps=result.get("steps", []),
                        attachments=result.get("attachments", []),
                        description=result.get("description", "")
                    )
                    
                    test_results[name] = execution
                    
                    test_info = {
                        "name": html_lib.escape(name),
                        "status": status,
                        "duration": duration,
                        "test_type": test_type,
                        "suite": suite_name,
                        "description": result.get("description", ""),
                        "labels": result.get("labels", []),
                        "steps": result.get("steps", []),
                        "attachments": result.get("attachments", []),
                        "failure": {
                            "message": failure_info.message if failure_info else None,
                            "key_error": getattr(failure_info, "key_error", "") if failure_info else None,
                            "file_ref": getattr(failure_info, "file_ref", "") if failure_info else None,
                            "trace": failure_info.trace if failure_info else None,
                            "category": failure_info.category if failure_info else None,
                        } if failure_info else None
                    }
                    
                    if status == "passed":
                        self.results["passed"] += 1
                    elif status == "failed":
                        self.results["failed"] += 1
                    elif status == "skipped":
                        self.results["skipped"] += 1
                    elif status == "broken":
                        self.results["broken"] += 1
                    
                    self.results["total"] += 1
                    self.results["duration"] += duration
                    self.results["tests"].append(test_info)
            except Exception as e:
                print(f"Error parsing {result_file}: {e}")
        
        current_run = ExecutionRun(
            timestamp=datetime.now().isoformat(),
            total_tests=self.results["total"],
            passed=self.results["passed"],
            failed=self.results["failed"],
            skipped=self.results["skipped"],
            broken=self.results["broken"],
            duration=self.results["duration"],
            test_results=test_results
        )
        return self.results

    def generate_json_report(self, output_path: str) -> str:
        """Generate JSON report"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2)
        return str(output_path)

    def print_summary(self):
        """Print summary"""
        print("\n" + "="*60)
        print("TEST EXECUTION SUMMARY")
        print("="*60)
        print(f"Total Tests:   {self.results['total']}")
        print(f"Passed:        {self.results['passed']}")
        print(f"Failed:        {self.results['failed']}")
        print(f"Broken:        {self.results['broken']}")
        print(f"Skipped:       {self.results['skipped']}")
        print(f"Duration:      {self.results['duration'] / 1000:.2f}s")
        
        if self.results['total'] > 0:
            pass_rate = (self.results['passed'] / self.results['total']) * 100
            print(f"Pass Rate:     {pass_rate:.1f}%")
        
        print("="*60 + "\n")

    def generate_html_report(self, output_path: str) -> str:
        """Generate comprehensive HTML report"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        pass_rate = (self.results['passed'] / self.results['total'] * 100) if self.results['total'] > 0 else 0
        status_color = "#4CAF50" if pass_rate >= 80 else "#FF9800" if pass_rate >= 50 else "#F44336"
        
        JWT_RE = re.compile(r'eyJ[A-Za-z0-9_\-]+(?:\.\.\.[A-Za-z0-9_\-]*)*\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+')

        def _render_api_step(step_num, step, card_id):
            """Render a single API step with its request/response payload inline."""
            ss = step.get("status", "unknown")
            sn = html_lib.escape(step.get("name", ""))
            is_broken = ss in ("broken", "failed")
            border_color = "#e74c3c" if is_broken else "#27ae60" if ss == "passed" else "#f39c12"
            bg_color = "#fff8f7" if is_broken else "#f8fffe" if ss == "passed" else "#fffdf5"
            step_id = f"{card_id}-step-{step_num}"

            # Collect attachments from step and its sub-steps
            all_atts = list(step.get("attachments", []))
            for sub in step.get("steps", []):
                all_atts += sub.get("attachments", [])

            # Parse the first JSON attachment for request/response
            payload_html = ""
            for att in all_atts:
                att_file = self.allure_results_dir / att.get("source", "")
                att_type = att.get("type", "")
                if att_type in ("application/json", "text/json") and att_file.exists():
                    try:
                        raw = att_file.read_text(encoding='utf-8')
                        data = json.loads(raw)
                    except:
                        continue

                    if data is None:
                        payload_html += '<div class="api-null-resp">Response was <strong>null</strong> — API returned no data. Check the request parameters or service availability.</div>'
                        break

                    if isinstance(data, dict) and ("Request" in data or "Response" in data):
                        # Full req+resp structure
                        req = data.get("Request")
                        resp = data.get("Response")
                        if req:
                            req_str = JWT_RE.sub('[JWT]', json.dumps(req, indent=2))
                            payload_html += f'<div class="api-section-label">REQUEST</div>'
                            payload_html += f'<pre class="api-json req-json">{html_lib.escape(req_str)}</pre>'
                        if resp is not None:
                            status_code = resp.get("status_code") if isinstance(resp, dict) else None
                            body = resp.get("response_body", resp) if isinstance(resp, dict) else resp
                            code_class = "http-ok" if status_code and 200 <= status_code < 300 else "http-err"
                            code_html = f'<span class="http-status {code_class}">HTTP {status_code}</span>' if status_code else ''
                            body_str = JWT_RE.sub('[JWT]', json.dumps(body, indent=2))
                            payload_html += f'<div class="api-section-label">RESPONSE {code_html}</div>'
                            payload_html += f'<pre class="api-json resp-json {code_class}">{html_lib.escape(body_str)}</pre>'
                        elif resp is None:
                            payload_html += '<div class="api-section-label">RESPONSE</div>'
                            payload_html += '<div class="api-null-resp">Response was <strong>null</strong></div>'
                    else:
                        # Plain response body (list or dict)
                        body_str = JWT_RE.sub('[JWT]', json.dumps(data, indent=2))
                        payload_html += f'<div class="api-section-label">RESPONSE</div>'
                        payload_html += f'<pre class="api-json">{html_lib.escape(body_str)}</pre>'
                    break  # only first attachment per step

            has_payload = bool(payload_html)
            open_attr = " open" if is_broken else ""

            out = f'<div class="api-step-card" style="border-left:4px solid {border_color};background:{bg_color};">'
            out += f'<div class="api-step-header">'
            out += f'<span class="step-status {ss}">{ss.upper()}</span>'
            out += f'<span class="api-step-name">Step {step_num}: {sn}</span>'
            out += '</div>'
            if has_payload:
                out += f'<details class="api-step-payload"{open_attr}>'
                out += f'<summary class="api-payload-toggle">{"▼ Response payload" if is_broken else "▶ Show payload"}</summary>'
                out += f'<div class="api-payload-body">{payload_html}</div>'
                out += '</details>'
            elif is_broken:
                out += '<div class="api-null-resp" style="margin:8px 0 4px;">No response attachment captured — the step threw an exception before completing.</div>'
            out += '</div>'
            return out

        def _build_test_cards(tests_list, id_prefix):
            html = ""
            failed = [t for t in tests_list if t["status"] in ["failed", "broken"]]
            passed = [t for t in tests_list if t["status"] == "passed"]
            skipped = [t for t in tests_list if t["status"] == "skipped"]
            sorted_list = failed + passed + skipped

            for idx, test in enumerate(sorted_list):
                status = test.get("status", "unknown")
                name = html_lib.escape(test.get("name", "Unknown")[:120])
                dur_ms = test.get("duration", 0)
                duration_s = dur_ms / 1000
                card_id = f"{id_prefix}-{idx}"

                # Duration mini-bar
                bar_pct = min(100, dur_ms / _max_dur * 100) if _max_dur > 0 else 0
                bar_color = "#22c55e" if dur_ms <= _avg_dur else "#f59e0b" if dur_ms < _avg_dur * 2 else "#ef4444"
                key_err_attr = html_lib.escape((test.get("failure") or {}).get("key_error", ""))

                has_details = bool(test.get("failure") or test.get("steps") or test.get("attachments"))
                toggle_btn = (f'<button class="toggle-btn" onclick="toggleDetails(\'{card_id}\')">&#9658;</button>'
                              if has_details else '<span class="toggle-btn" style="width:24px;"></span>')

                html += f'<div class="test-card {status}" data-card-id="{card_id}" data-prefix="{id_prefix}" data-key-error="{key_err_attr}">'
                html += f'<div class="test-header" onclick="toggleDetails(\'{card_id}\')">'
                html += f'{toggle_btn}<span class="test-title">{name}</span>'
                html += f'<div class="dur-bar-outer" title="{duration_s:.2f}s (avg {_avg_dur/1000:.1f}s)"><div class="dur-bar-inner" style="width:{bar_pct:.0f}%;background:{bar_color};"></div></div>'
                html += f'<span class="test-duration">{duration_s:.2f}s</span>'
                html += f'<span class="test-status {status}">{status.upper()}</span>'
                html += '</div>'

                if has_details:
                    html += f'<div id="details-{card_id}" class="test-details">'
                    test_type = test.get("test_type", "other")

                    # ── FAILURE SUMMARY ──────────────────────────────────────
                    if test.get("failure"):
                        failure = test["failure"]
                        key_err  = html_lib.escape(failure.get("key_error") or failure.get("message", ""))
                        file_ref = html_lib.escape(failure.get("file_ref", ""))
                        category = (failure.get("category") or "").title()
                        full_trace = html_lib.escape(failure.get("trace", ""))

                        _copy_text = html_lib.escape(f"{key_err}  {file_ref}".strip()).replace("'", "&#39;")
                        html += f'<div class="section"><div class="section-title">&#10060; Failure Details</div>'
                        html += f'<div class="failure-box">'
                        html += f'<button class="copy-btn" onclick="copyText(this,\'{_copy_text}\')">&#128203; Copy</button>'
                        html += f'<div class="failure-summary"><span class="fail-badge">{category or "Error"}</span>'
                        html += f'<span class="failure-key-msg">{key_err}</span></div>'
                        if file_ref:
                            html += f'<div class="failure-fileref">{file_ref}</div>'

                        if test_type == "api":
                            # For API tests: trace is not the signal — skip it entirely
                            pass
                        else:
                            # For UI tests: keep collapsible trace
                            if full_trace:
                                html += f'<details class="trace-details"><summary>Show full stack trace</summary>'
                                html += f'<div class="failure-trace">{full_trace}</div></details>'

                        html += '</div></div>'

                    # ── STEPS ────────────────────────────────────────────────
                    if test.get("steps"):
                        if test_type == "api":
                            html += '<div class="section"><div class="section-title">📡 API Execution Steps</div>'
                            for si, step in enumerate(test["steps"], 1):
                                html += _render_api_step(si, step, card_id)
                            html += '</div>'
                        else:
                            html += '<div class="section"><div class="section-title">📝 Execution Steps</div>'
                            for si, step in enumerate(test["steps"], 1):
                                ss = step.get("status", "unknown")
                                sn = html_lib.escape(step.get("name", ""))
                                html += f'<div class="step"><strong>Step {si}:</strong> {sn} <span class="step-status {ss}">{ss}</span></div>'
                            html += '</div>'

                    # ── UI ATTACHMENTS (screenshots etc.) ────────────────────
                    if test_type != "api" and test.get("attachments"):
                        html += f'<div class="section"><div class="section-title">📎 Attachments ({len(test["attachments"])} items)</div>'
                        for att in test["attachments"]:
                            att_name = html_lib.escape(att.get("name", "Attachment"))
                            att_type = att.get("type", "")
                            att_file = self.allure_results_dir / att.get("source", "")
                            html += f'<div class="attachment"><div class="att-name">📄 {att_name}</div>'
                            if att_type.startswith("image/") and att_file.exists():
                                with open(att_file, 'rb') as f:
                                    img_b64 = base64.b64encode(f.read()).decode()
                                html += f'<img src="data:{att_type};base64,{img_b64}" class="att-image lightbox-trigger" onclick="openLightbox(this.src)" title="Click to enlarge">'
                            elif att_type in ["application/json", "text/json"] and att_file.exists():
                                try:
                                    with open(att_file, 'r', encoding='utf-8') as f:
                                        jd = json.load(f)
                                    jstr = re.sub(r'eyJ[A-Za-z0-9_\-]+(?:\.\.\.[A-Za-z0-9_\-]*)*\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+', '[JWT]', json.dumps(jd, indent=2))
                                    html += f'<pre class="json-preview">{html_lib.escape(jstr)}</pre>'
                                except:
                                    pass
                            elif att_type.startswith("text/") and att_file.exists():
                                try:
                                    with open(att_file, 'r', encoding='utf-8') as f:
                                        content = f.read()
                                    html += f'<pre class="text-preview">{html_lib.escape(content[:1000])}</pre>'
                                except:
                                    pass
                            html += '</div>'
                        html += '</div>'

                    html += '</div>'
                html += '</div>'
            return html, sorted_list

        all_tests = self.results["tests"]
        api_tests = [t for t in all_tests if t.get("test_type") == "api"]
        ui_tests  = [t for t in all_tests if t.get("test_type") == "ui"]
        other_tests = [t for t in all_tests if t.get("test_type") not in ("api", "ui")]

        # Must be computed before _build_test_cards is called (used inside closure)
        _durs    = [t.get("duration", 0) for t in all_tests if t.get("duration", 0) > 0]
        _max_dur = max(_durs) if _durs else 1
        _avg_dur = sum(_durs) / len(_durs) if _durs else 1

        api_cards_html, api_sorted   = _build_test_cards(api_tests, "api")
        ui_cards_html,  ui_sorted    = _build_test_cards(ui_tests,  "ui")
        other_cards_html, other_sorted = _build_test_cards(other_tests, "other")

        def _sidebar_items(sorted_list, prefix):
            items = ""
            for idx, t in enumerate(sorted_list):
                items += (f'<div class="test-item {t["status"]}" data-card-id="{prefix}-{idx}" '
                          f'data-type="{prefix}" onclick="selectTest(\'{prefix}-{idx}\')" '
                          f'title="{t["name"]}">{t["name"]}</div>')
            return items

        api_sidebar   = _sidebar_items(api_sorted,   "api")
        ui_sidebar    = _sidebar_items(ui_sorted,    "ui")
        other_sidebar = _sidebar_items(other_sorted, "other")
        combined_sidebar   = api_sidebar + ui_sidebar + other_sidebar
        combined_cards_html = api_cards_html + ui_cards_html + other_cards_html

        # ── Failure groups ────────────────────────────────────────────────
        _fg_counter = defaultdict(list)
        for _t in self.results["tests"]:
            _ke = (_t.get("failure") or {}).get("key_error", "").strip()
            if _ke:
                _fg_counter[_ke[:120]].append(_t["name"])
        failure_groups = sorted(_fg_counter.items(), key=lambda x: -len(x[1]))  # [(err, [names])]

        # ── Per-subtab counts for filter pills ────────────────────────────
        def _counts(tests):
            return {s: sum(1 for t in tests if t["status"] == s)
                    for s in ("passed", "failed", "broken", "skipped")}

        api_counts = _counts(api_sorted)
        ui_counts  = _counts(ui_sorted)

        def _filter_pills(prefix, counts):
            total = sum(counts.values())
            out = f'<div class="filter-pills" id="pills-{prefix}">'
            out += f'<button class="pill pill-all active" onclick="filterByStatus(\'{prefix}\',\'all\',this)">All <span class="pill-count">{total}</span></button>'
            for st, label, cls in [("passed","Passed","pill-passed"),("failed","Failed","pill-failed"),("broken","Broken","pill-broken"),("skipped","Skipped","pill-skipped")]:
                if counts.get(st, 0):
                    out += f'<button class="pill {cls}" onclick="filterByStatus(\'{prefix}\',\'{st}\',this)">{label} <span class="pill-count">{counts[st]}</span></button>'
            out += '</div>'
            return out

        api_pills = _filter_pills("api", api_counts)
        ui_pills  = _filter_pills("ui",  ui_counts)

        # ── SVG donut ─────────────────────────────────────────────────────
        total_t  = self.results["total"]
        p_n = self.results["passed"]
        f_n = self.results["failed"] + self.results["broken"]
        s_n = self.results["skipped"]
        C   = 502.65  # circumference for r=80
        if total_t > 0:
            p_arc = p_n / total_t * C
            f_arc = f_n / total_t * C
            s_arc = s_n / total_t * C
        else:
            p_arc = f_arc = s_arc = 0.0

        # Color thresholds
        if pass_rate >= 70:
            pass_color = "#22c55e"   # green  — healthy
            health_label = "Healthy"
        elif pass_rate >= 50:
            pass_color = "#f59e0b"   # amber  — needs attention
            health_label = "Needs Attention"
        else:
            pass_color = "#ef4444"   # red    — critical
            health_label = "Critical"

        def _arc(color, arc_len, offset):
            if arc_len <= 0:
                return ""
            return (f'<circle cx="100" cy="100" r="80" fill="none" stroke="{color}" stroke-width="20" '
                    f'stroke-dasharray="{arc_len:.2f} {C:.2f}" stroke-dashoffset="{-offset:.2f}" '
                    f'transform="rotate(-90 100 100)" stroke-linecap="butt"/>')

        donut_svg = f'''<svg viewBox="0 0 200 200" width="150" height="150" style="flex-shrink:0;" id="donutSvg">
  <circle cx="100" cy="100" r="80" fill="none" stroke="#e2e8f0" stroke-width="20"/>
  {_arc("#ef4444", f_arc, p_arc)}
  {_arc("#f59e0b", s_arc, p_arc + f_arc)}
  <circle id="donut-pass-arc" cx="100" cy="100" r="80" fill="none"
    stroke="{pass_color}" stroke-width="20"
    stroke-dasharray="0 {C:.2f}" stroke-dashoffset="0"
    transform="rotate(-90 100 100)" stroke-linecap="butt"
    data-target="{p_arc:.2f}" data-circumference="{C:.2f}" data-rate="{pass_rate:.0f}"/>
  <text id="donut-pct-text" x="100" y="92" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="30" font-weight="700" fill="{pass_color}">0%</text>
  <text x="100" y="114" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="12" fill="#94a3b8">pass rate</text>
  <text x="100" y="132" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="10" font-weight="600" fill="{pass_color}">{health_label.upper()}</text>
</svg>'''
        
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Automation Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html {{ scroll-behavior: smooth; }}
        body {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; background: #f0f2f5; color: #1a2332; line-height: 1.6; }}
        
        /* Navbar */
        .navbar {{ position: sticky; top: 0; z-index: 100; background: #0f1f3d; color: white; padding: 0 40px; box-shadow: 0 2px 16px rgba(0,0,0,0.25); display: flex; align-items: stretch; gap: 0; min-height: 68px; }}
        .navbar-brand {{ display: flex; flex-direction: column; justify-content: center; padding: 14px 0; border-right: 1px solid rgba(255,255,255,0.15); padding-right: 28px; margin-right: 0; flex-shrink: 0; }}
        .navbar-brand h1 {{ font-size: 20px; font-weight: 700; letter-spacing: -0.3px; white-space: nowrap; }}
        .navbar-meta {{ font-size: 11px; opacity: 0.75; display: flex; gap: 16px; flex-wrap: wrap; margin-top: 4px; }}
        .navbar-meta span {{ display: flex; align-items: center; gap: 4px; }}

        /* Main nav tabs (inside navbar) */
        .nav-main-tabs {{ display: flex; align-items: stretch; gap: 0; margin-left: 8px; }}
        .nav-tab-btn {{ background: none; border: none; border-bottom: 4px solid transparent; color: rgba(255,255,255,0.65); padding: 0 28px; font-size: 13px; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; cursor: pointer; transition: all 0.2s ease; display: flex; align-items: center; gap: 8px; height: 100%; }}
        .nav-tab-btn:hover {{ color: white; background: rgba(255,255,255,0.08); }}
        .nav-tab-btn.active {{ color: white; border-bottom-color: #74b9ff; background: rgba(255,255,255,0.1); }}
        .nav-tab-icon {{ font-size: 15px; }}

        /* Search in navbar */
        .navbar-search {{ margin-left: auto; display: flex; align-items: center; padding: 0 0 0 20px; }}
        .search-box {{ background: rgba(255,255,255,0.12); border: 1.5px solid rgba(255,255,255,0.25); padding: 9px 16px; border-radius: 6px; color: white; font-size: 13px; width: 260px; transition: all 0.25s ease; }}
        .search-box:focus {{ outline: none; background: rgba(255,255,255,0.2); border-color: rgba(255,255,255,0.55); width: 300px; }}
        .search-box::placeholder {{ color: rgba(255,255,255,0.45); }}

        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        
        /* Main Layout */
        .main-layout {{ display: grid; grid-template-columns: 260px 1fr; gap: 20px; margin-top: 0; width: 100%; }}
        .sidebar {{ background: white; border-radius: 10px; padding: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); max-height: calc(100vh - 220px); overflow-y: auto; position: sticky; top: 90px; border: 1px solid #e2e8f0; }}
        .sidebar-title {{ font-weight: 700; margin-bottom: 12px; color: #334155; font-size: 12px; text-transform: uppercase; letter-spacing: 0.9px; padding-bottom: 10px; border-bottom: 1px solid #f1f5f9; }}
        
        /* Test Items in Sidebar */
        .test-item {{ padding: 8px 10px; margin-bottom: 4px; border-radius: 6px; font-size: 12px; cursor: pointer; border-left: 3px solid #e2e8f0; background: #f8fafc; transition: all 0.15s ease; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #475569; }}
        .test-item:hover {{ background: #eff6ff; border-left-color: #2563eb; color: #1e40af; }}
        .test-item.passed {{ border-left-color: #22c55e; background: #f0fdf4; color: #15803d; }}
        .test-item.failed {{ border-left-color: #ef4444; background: #fef2f2; color: #b91c1c; }}
        .test-item.broken {{ border-left-color: #dc2626; background: #fef2f2; color: #991b1b; }}
        .test-item.active {{ background: #dbeafe; font-weight: 600; border-left-color: #2563eb; color: #1d4ed8; }}
        
        /* Summary Bar (donut + stats) */
        .summary-bar {{ display: flex; align-items: center; gap: 28px; margin-bottom: 24px; background: white; border-radius: 14px; padding: 22px 28px; box-shadow: 0 1px 6px rgba(0,0,0,0.07); flex-wrap: wrap; border: 1px solid #e8edf2; }}
        .donut-wrap {{ display: flex; flex-direction: column; align-items: center; gap: 10px; flex-shrink: 0; }}
        .donut-legend {{ display: flex; flex-direction: column; gap: 5px; }}
        .legend-item {{ display: flex; align-items: center; gap: 7px; font-size: 12px; color: #64748b; }}
        .legend-dot {{ width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }}

        /* Stats Grid — cards are clickable filters */
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; flex: 1; min-width: 0; }}
        .stat-card {{ background: #f8fafc; padding: 18px 16px; border-radius: 10px; border-left: 4px solid #94a3b8; text-align: center; cursor: pointer; transition: all 0.2s ease; border: 1px solid #e2e8f0; border-left-width: 4px; }}
        .stat-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 14px rgba(0,0,0,0.1); background: white; }}
        .stat-card.stat-active {{ transform: translateY(-2px); background: white; box-shadow: 0 4px 18px rgba(0,0,0,0.12); }}
        .stat-value {{ font-size: 32px; font-weight: 700; margin-bottom: 5px; }}
        .stat-label {{ color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; font-weight: 600; }}
        .stat-hint {{ font-size: 10px; color: #b0bec5; margin-top: 4px; }}

        /* Type-filter tabs (All / API / UI) */
        .type-tabs {{ display: flex; gap: 6px; margin: 20px 0 16px; border-bottom: 2px solid #e2e8f0; padding-bottom: 0; }}
        .type-tab {{ background: none; border: none; border-bottom: 3px solid transparent; padding: 10px 22px; margin-bottom: -2px; cursor: pointer; font-size: 13px; font-weight: 600; color: #94a3b8; transition: all 0.2s ease; border-radius: 6px 6px 0 0; }}
        .type-tab:hover {{ color: #334155; background: #f1f5f9; }}
        .type-tab.active {{ color: #2563eb; border-bottom-color: #2563eb; background: #eff6ff; }}
        .type-tab-count {{ display: inline-block; background: #e2e8f0; color: #64748b; font-size: 11px; padding: 1px 7px; border-radius: 8px; margin-left: 5px; font-weight: 700; }}
        .type-tab.active .type-tab-count {{ background: #dbeafe; color: #1d4ed8; }}
        
        /* Alert Boxes */
        .alert {{ padding: 15px 18px; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid; font-weight: 500; }}
        .alert.warning {{ background: #fef9e7; color: #7d6608; border-left-color: #f1c40f; }}
        .alert.success {{ background: #eafaf1; color: #0b5345; border-left-color: #27ae60; }}
        .alert.critical {{ background: #fadbd8; color: #78281f; border-left-color: #e74c3c; }}
        
        /* Test Cards */
        .test-card {{ background: white; border-radius: 10px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); border-left: 4px solid #cbd5e1; overflow: hidden; transition: box-shadow 0.2s ease; border: 1px solid #e2e8f0; border-left-width: 4px; }}
        .test-card:hover {{ box-shadow: 0 3px 12px rgba(0,0,0,0.1); }}
        .test-card.passed {{ border-left-color: #22c55e; }}
        .test-card.failed {{ border-left-color: #ef4444; }}
        .test-card.broken {{ border-left-color: #dc2626; }}

        /* Test Header */
        .test-header {{ padding: 14px 18px; display: flex; align-items: center; gap: 10px; cursor: pointer; background: #fafcff; transition: background 0.15s ease; }}
        .test-header:hover {{ background: #f1f5f9; }}
        .toggle-btn {{ background: none; border: none; cursor: pointer; font-size: 14px; padding: 0; width: 22px; color: #94a3b8; transition: transform 0.25s ease; flex-shrink: 0; }}
        .test-card.expanded .toggle-btn {{ transform: rotate(90deg); color: #2563eb; }}
        .test-title {{ flex: 1; font-weight: 600; font-size: 14px; color: #1e293b; }}
        .test-duration {{ color: #94a3b8; font-size: 12px; font-weight: 500; flex-shrink: 0; }}
        .test-status {{ padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; flex-shrink: 0; }}
        .test-status.passed {{ background: #dcfce7; color: #15803d; }}
        .test-status.failed {{ background: #fee2e2; color: #b91c1c; }}
        .test-status.broken {{ background: #fecaca; color: #991b1b; }}
        .test-status.skipped {{ background: #fef9c3; color: #854d0e; }}

        /* Test Details */
        .test-details {{ display: none; padding: 18px 20px; border-top: 1px solid #f1f5f9; background: #f8fafc; }}
        .test-details.expanded {{ display: block; }}
        .section {{ margin-bottom: 20px; }}
        .section:last-child {{ margin-bottom: 0; }}
        .section-title {{ font-weight: 700; font-size: 13px; margin-bottom: 10px; color: #334155; padding-bottom: 7px; border-bottom: 1px solid #e2e8f0; }}
        
        /* Failure Details */
        .failure-box {{ background: #fadbd8; border: 2px solid #e74c3c; border-radius: 8px; padding: 14px 16px; }}
        .failure-summary {{ display: flex; align-items: flex-start; gap: 10px; margin-bottom: 10px; }}
        .fail-badge {{ background: #e74c3c; color: white; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 4px; white-space: nowrap; flex-shrink: 0; text-transform: uppercase; margin-top: 2px; }}
        .failure-key-msg {{ color: #a93226; font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; font-size: 13px; font-weight: 600; line-height: 1.5; word-break: break-word; }}
        .failure-fileref {{ font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; font-size: 11px; color: #7f8c8d; margin-top: 6px; }}
        .trace-details {{ margin-top: 8px; }}
        .trace-details summary {{ cursor: pointer; color: #7f8c8d; font-size: 12px; padding: 4px 0; user-select: none; }}
        .trace-details summary:hover {{ color: #2a5298; }}
        .failure-trace {{ color: #5d4037; font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; max-height: 300px; overflow-y: auto; line-height: 1.4; margin-top: 8px; background: #fef0ef; border-radius: 4px; padding: 10px; }}
        .failure-msg {{ color: #a93226; font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; font-size: 13px; margin-bottom: 12px; white-space: pre-wrap; word-break: break-word; max-height: 250px; overflow-y: auto; line-height: 1.5; }}
        .api-payload {{ margin-bottom: 14px; }}
        .api-payload-name {{ font-size: 12px; font-weight: 700; color: #2a5298; margin-bottom: 6px; }}

        /* API Step Cards */
        .api-step-card {{ border-radius: 7px; margin-bottom: 10px; overflow: hidden; }}
        .api-step-header {{ display: flex; align-items: center; gap: 10px; padding: 10px 14px; }}
        .api-step-name {{ font-size: 13px; font-weight: 600; color: #2c3e50; }}
        .api-step-payload {{ border-top: 1px solid rgba(0,0,0,0.06); }}
        .api-step-payload summary {{ padding: 7px 14px; cursor: pointer; font-size: 12px; color: #7f8c8d; user-select: none; list-style: none; }}
        .api-step-payload summary::-webkit-details-marker {{ display: none; }}
        .api-step-payload summary:hover {{ color: #2a5298; }}
        .api-payload-body {{ padding: 0 14px 12px; }}
        .api-section-label {{ font-size: 10px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #7f8c8d; margin: 10px 0 4px; }}
        .api-json {{ border-radius: 5px; padding: 10px 12px; font-family: 'Monaco','Menlo','Ubuntu Mono',monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; max-height: 300px; overflow-y: auto; line-height: 1.45; margin: 0; }}
        .api-json.req-json {{ background: #f0f4ff; color: #1a2a6c; border: 1px solid #c5d3f5; }}
        .api-json.resp-json.http-ok {{ background: #f0fbf4; color: #1a4a2a; border: 1px solid #b2dfcc; }}
        .api-json.resp-json.http-err {{ background: #fff4f4; color: #5a1a1a; border: 1px solid #f5c0c0; }}
        .api-json.resp-json {{ background: #f9f9f9; color: #333; border: 1px solid #ddd; }}
        .http-status {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; margin-left: 8px; vertical-align: middle; }}
        .http-status.http-ok {{ background: #d5f4e6; color: #186a3b; }}
        .http-status.http-err {{ background: #fadbd8; color: #a93226; }}
        .api-null-resp {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 5px; padding: 10px 12px; font-size: 12px; color: #856404; }}

        /* Sub-tabs for API / UI */
        .subtabs-nav {{ display: flex; gap: 8px; margin-bottom: 20px; border-bottom: 2px solid #ecf0f1; }}
        .subtab-btn {{ background: none; border: none; padding: 10px 20px; cursor: pointer; font-size: 13px; font-weight: 600; color: #7f8c8d; border-bottom: 3px solid transparent; margin-bottom: -2px; transition: all 0.2s ease; }}
        .subtab-btn:hover {{ color: #2a5298; }}
        .subtab-btn.active {{ color: #2a5298; border-bottom-color: #2a5298; }}
        .subtab-count {{ display: inline-block; background: #ecf0f1; color: #555; font-size: 11px; padding: 2px 7px; border-radius: 10px; margin-left: 6px; font-weight: 700; }}
        .subtab-btn.active .subtab-count {{ background: #2a5298; color: white; }}
        .subtab-content {{ display: none; }}
        .subtab-content.active {{ display: block; }}
        
        /* Steps */
        .step {{ background: white; border-left: 4px solid #3498db; padding: 12px 14px; margin-bottom: 10px; border-radius: 6px; font-size: 13px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        .step strong {{ color: #2c3e50; }}
        .step-status {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 11px; margin-left: 8px; font-weight: 600; text-transform: uppercase; }}
        .step-status.passed {{ background: #d5f4e6; color: #186a3b; }}
        .step-status.failed {{ background: #fadbd8; color: #a93226; }}
        
        /* Attachments */
        .attachment {{ background: white; border: 2px solid #e0e0e0; border-radius: 8px; padding: 14px; margin-bottom: 12px; transition: all 0.2s ease; }}
        .attachment:hover {{ border-color: #2a5298; box-shadow: 0 2px 6px rgba(42, 82, 152, 0.1); }}
        .att-name {{ font-weight: 700; color: #2a5298; margin-bottom: 10px; font-size: 13px; }}
        .att-image {{ max-width: 100%; max-height: 500px; border-radius: 6px; margin-top: 8px; border: 1px solid #ecf0f1; }}
        .json-preview {{ background: #282c34; color: #abb2bf; border: 2px solid #e0e0e0; border-radius: 8px; padding: 14px; font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; font-size: 12px; max-height: 450px; overflow-y: auto; line-height: 1.5; }}
        .text-preview {{ background: #f5f5f5; border: 2px solid #e0e0e0; border-radius: 8px; padding: 14px; font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; font-size: 12px; max-height: 350px; overflow-y: auto; line-height: 1.5; }}
        
        /* Footer */
        .footer {{ margin-top: 40px; text-align: center; color: #94a3b8; font-size: 12px; padding: 24px 20px; border-top: 1px solid #e2e8f0; }}

        /* ── 1. Failure Groups Panel ─────────────────────────────────── */
        .failure-groups-wrap {{ margin-bottom: 14px; border-radius: 10px; border: 1px solid #fecaca; background: white; box-shadow: 0 1px 4px rgba(0,0,0,0.05); overflow: hidden; }}
        .failure-groups-summary {{ list-style: none; display: flex; align-items: center; gap: 10px; padding: 12px 18px; cursor: pointer; font-size: 13px; font-weight: 700; color: #991b1b; user-select: none; transition: background 0.15s; }}
        .failure-groups-summary::-webkit-details-marker {{ display: none; }}
        .failure-groups-summary::before {{ content: '\\25B6'; font-size: 11px; transition: transform 0.2s; display: inline-block; }}
        details[open] .failure-groups-summary::before {{ transform: rotate(90deg); }}
        .failure-groups-summary:hover {{ background: #fff5f5; }}
        .fg-summary-count {{ background: #fee2e2; color: #b91c1c; font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 10px; }}
        .fg-toggle-hint {{ margin-left: auto; font-size: 11px; font-weight: 400; color: #b91c1c; opacity: 0.7; }}
        details[open] .fg-toggle-hint {{ display: none; }}
        .failure-groups {{ padding: 4px 18px 14px; }}
        .failure-groups-title {{ font-size: 13px; font-weight: 700; color: #991b1b; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }}
        .fg-row {{ display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #f1f5f9; }}
        .fg-row:last-child {{ border-bottom: none; }}
        .fg-count {{ background: #fee2e2; color: #b91c1c; font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 10px; white-space: nowrap; flex-shrink: 0; }}
        .fg-msg {{ flex: 1; font-family: 'Monaco','Menlo','Ubuntu Mono',monospace; font-size: 12px; color: #334155; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .fg-link {{ background: none; border: 1px solid #cbd5e1; color: #475569; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 5px; cursor: pointer; white-space: nowrap; flex-shrink: 0; transition: all 0.15s; }}
        .fg-link:hover {{ background: #f1f5f9; border-color: #2563eb; color: #2563eb; }}
        .fg-link.active {{ background: #2563eb; border-color: #2563eb; color: white; }}

        /* ── 2. Copy Error Button ────────────────────────────────────── */
        .copy-btn {{ background: none; border: 1px solid rgba(0,0,0,0.15); border-radius: 4px; padding: 3px 9px; font-size: 11px; cursor: pointer; color: #64748b; transition: all 0.15s; float: right; margin-left: 10px; }}
        .copy-btn:hover {{ background: #334155; color: white; border-color: #334155; }}
        .copy-btn.copied {{ background: #22c55e; color: white; border-color: #22c55e; }}

        /* ── 3. Jump to Failures FAB ─────────────────────────────────── */
        .jump-fab {{ position: fixed; bottom: 28px; right: 28px; z-index: 999; background: #ef4444; color: white; border: none; border-radius: 50px; padding: 13px 20px; font-size: 13px; font-weight: 700; cursor: pointer; box-shadow: 0 4px 16px rgba(239,68,68,0.4); transition: all 0.2s ease; display: flex; align-items: center; gap: 8px; }}
        .jump-fab:hover {{ background: #dc2626; transform: translateY(-2px); box-shadow: 0 6px 20px rgba(239,68,68,0.45); }}
        .jump-fab.hidden {{ opacity: 0; pointer-events: none; transform: translateY(10px); }}

        /* ── 4. JSON Syntax Highlighting ─────────────────────────────── */
        .j-key  {{ color: #7dd3fc; }}
        .j-str  {{ color: #86efac; }}
        .j-num  {{ color: #fcd34d; }}
        .j-bool {{ color: #c084fc; }}
        .j-null {{ color: #f87171; font-style: italic; }}

        /* ── 5. Screenshot Lightbox ──────────────────────────────────── */
        .lightbox-trigger {{ cursor: zoom-in !important; }}
        #lightbox {{ display: none; position: fixed; inset: 0; z-index: 9999; background: rgba(0,0,0,0.85); align-items: center; justify-content: center; padding: 24px; }}
        #lightbox.open {{ display: flex; }}
        #lightbox img {{ max-width: 92vw; max-height: 90vh; border-radius: 8px; box-shadow: 0 8px 40px rgba(0,0,0,0.6); object-fit: contain; }}
        #lightbox-close {{ position: fixed; top: 18px; right: 22px; color: white; font-size: 28px; cursor: pointer; background: rgba(255,255,255,0.15); border: none; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; line-height: 1; transition: background 0.15s; }}
        #lightbox-close:hover {{ background: rgba(255,255,255,0.3); }}

        /* ── 6. Mini Duration Bar ────────────────────────────────────── */
        .dur-bar-outer {{ width: 60px; height: 5px; background: #f1f5f9; border-radius: 3px; overflow: hidden; flex-shrink: 0; }}
        .dur-bar-inner {{ height: 100%; border-radius: 3px; transition: width 0.3s; }}

        /* ── 7. Copy Summary Button ──────────────────────────────────── */
        .copy-summary-btn {{ background: rgba(255,255,255,0.12); border: 1.5px solid rgba(255,255,255,0.25); color: white; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s; white-space: nowrap; margin-left: 12px; letter-spacing: 0.3px; }}
        .copy-summary-btn:hover {{ background: rgba(255,255,255,0.22); border-color: rgba(255,255,255,0.5); }}
        .copy-summary-btn.copied {{ background: #22c55e; border-color: #22c55e; }}

        /* ── 8. Active Filters Bar ───────────────────────────────────── */
        .active-filters-bar {{ display: none; align-items: center; gap: 8px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 8px 14px; margin-bottom: 14px; font-size: 12px; color: #1d4ed8; flex-wrap: wrap; }}
        .active-filters-bar.visible {{ display: flex; }}
        .af-label {{ font-weight: 600; }}
        .af-tag {{ background: #dbeafe; border: 1px solid #93c5fd; border-radius: 12px; padding: 2px 10px; font-weight: 700; }}
        .af-clear {{ margin-left: auto; background: none; border: 1px solid #93c5fd; color: #1d4ed8; border-radius: 5px; padding: 2px 10px; cursor: pointer; font-size: 11px; font-weight: 600; transition: all 0.15s; }}
        .af-clear:hover {{ background: #2563eb; color: white; border-color: #2563eb; }}
        
        /* Scrollbar Styling */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: #f5f5f5; }}
        ::-webkit-scrollbar-thumb {{ background: #bdc3c7; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #95a5a6; }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            .main-layout {{ grid-template-columns: 1fr; }}
            .sidebar {{ max-height: 300px; position: static; }}
            .navbar {{ padding: 15px 20px; }}
            .navbar h1 {{ font-size: 22px; }}
            .navbar-controls {{ flex-direction: column; align-items: stretch; }}
            .search-box {{ width: 100%; }}
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .summary-bar {{ flex-direction: column; align-items: flex-start; }}
            .donut-wrap {{ flex-direction: row; align-items: center; gap: 20px; }}
            .navbar-info {{ flex-direction: column; gap: 8px; }}
        }}
    </style>
</head>
<body>
    <div class="navbar">
        <div class="navbar-brand">
            <h1>Automation Test Report</h1>
            <div class="navbar-meta">
                <span><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
                <span><strong>Tag:</strong> {self.test_tag}</span>
                <span><strong>Browser:</strong> {self.test_browser}</span>
                <span><strong>Env:</strong> {self.test_env}</span>
            </div>
        </div>
        <div class="nav-main-tabs">
            <button class="nav-tab-btn active" id="navTabExec" onclick="switchTab('executions', this)">
                <span class="nav-tab-icon">&#9783;</span> TEST CASES
            </button>
            <button class="nav-tab-btn" id="navTabAnalytics" onclick="switchTab('analytics', this)">
                <span class="nav-tab-icon">&#9889;</span> ANALYTICS
            </button>
        </div>
        <div class="navbar-search">
            <button class="copy-summary-btn" id="copySummaryBtn" onclick="copyRunSummary(this)">&#128203; Copy Summary</button>
            <input type="text" class="search-box" id="searchBox" placeholder="Search tests..." onkeyup="filterTests()">
        </div>
    </div>

    <!-- Lightbox -->
    <div id="lightbox" onclick="closeLightbox(event)">
        <button id="lightbox-close" onclick="closeLightbox()">&times;</button>
        <img id="lightbox-img" src="" alt="Screenshot">
    </div>

    <!-- Jump to Failures FAB -->
    <button class="jump-fab" id="jumpFab" onclick="jumpToFirstFailure()" title="Jump to first failure">
        &#9660; First Failure
    </button>

    <div style="max-width: 1500px; margin: 0 auto; padding: 30px 20px;">
        <div class="summary-bar">
            <div class="donut-wrap">
                {donut_svg}
                <div class="donut-legend">
                    <div class="legend-item"><span class="legend-dot" style="background:{pass_color};"></span>Passed</div>
                    <div class="legend-item"><span class="legend-dot" style="background:#ef4444;"></span>Failed / Broken</div>
                    {'<div class="legend-item"><span class="legend-dot" style="background:#f59e0b;"></span>Skipped</div>' if s_n else ''}
                </div>
            </div>
            <div class="stats-grid">
                <div class="stat-card stat-active" style="border-left-color:#2563eb;" onclick="filterByStat('all',this)" title="Show all tests">
                    <div class="stat-value" style="color:#2563eb;">{self.results["total"]}</div>
                    <div class="stat-label">Total Tests</div>
                    <div class="stat-hint">click to filter</div>
                </div>
                <div class="stat-card" style="border-left-color:#22c55e;" onclick="filterByStat('passed',this)" title="Show passed tests">
                    <div class="stat-value" style="color:#22c55e;">{self.results["passed"]}</div>
                    <div class="stat-label">Passed</div>
                    <div class="stat-hint">click to filter</div>
                </div>
                <div class="stat-card" style="border-left-color:#ef4444;" onclick="filterByStat('failed',this)" title="Show failed &amp; broken tests">
                    <div class="stat-value" style="color:#ef4444;">{self.results["failed"] + self.results["broken"]}</div>
                    <div class="stat-label">Failed / Broken</div>
                    <div class="stat-hint">click to filter</div>
                </div>
                <div class="stat-card" style="border-left-color:#f59e0b;" onclick="filterByStat('skipped',this)" title="Show skipped tests">
                    <div class="stat-value" style="color:#f59e0b;">{self.results["skipped"]}</div>
                    <div class="stat-label">Skipped</div>
                    <div class="stat-hint">click to filter</div>
                </div>
            </div>
        </div>

        {self._generate_alerts_html()}

        <div id="executions" class="tab-content active">
            {''.join([
                '<details class="failure-groups-wrap">',
                f'<summary class="failure-groups-summary">&#9888; Common Failures <span class="fg-summary-count">{sum(len(t) for _,t in failure_groups[:8])} failures across {len(failure_groups[:8])} error types</span><span class="fg-toggle-hint">click to expand</span></summary>',
                '<div class="failure-groups">',
                '<div style="font-size:11px;color:#b91c1c;margin-bottom:10px;">Click Show All to filter tests by that error</div>',
                *[f'<div class="fg-row"><span class="fg-count">{len(tests)} test{"s" if len(tests)>1 else ""}</span><span class="fg-msg" title="{html_lib.escape(err)}">{html_lib.escape(err[:100])}</span><button class="fg-link" onclick="filterByError(\'{html_lib.escape(err[:120]).replace(chr(39), chr(34))}\',this)">Show All</button></div>'
                  for err, tests in failure_groups[:8] if err],
                '</div>',
                '</details>'
            ]) if failure_groups else ''}

            <div id="activeFiltersBar" class="active-filters-bar">
                <span class="af-label">Showing:</span>
                <span id="afStatTag" class="af-tag">All</span>
                <span style="color:#93c5fd;">&#183;</span>
                <span id="afTypeTag" class="af-tag">All Tests</span>
                <span id="afErrTag" style="display:none;" class="af-tag" title=""></span>
                <button class="af-clear" onclick="clearAllFilters()">&#215; Clear filters</button>
            </div>

            <div class="type-tabs">
                <button class="type-tab active" onclick="switchType('all', this)">All Tests <span class="type-tab-count">{len(api_tests)+len(ui_tests)+len(other_tests)}</span></button>
                <button class="type-tab" onclick="switchType('api', this)">API Tests <span class="type-tab-count">{len(api_tests)}</span></button>
                <button class="type-tab" onclick="switchType('ui', this)">UI Tests <span class="type-tab-count">{len(ui_tests)}</span></button>
                {'<button class="type-tab" onclick="switchType(\'other\', this)">Other <span class="type-tab-count">' + str(len(other_tests)) + '</span></button>' if other_tests else ''}
            </div>
            <div class="main-layout">
                <div class="sidebar">
                    <div class="sidebar-title">Test List</div>
                    <div id="combinedSidebar">{combined_sidebar}</div>
                </div>
                <div id="testCardsContainer">
                    {combined_cards_html}
                    <div class="footer">
                        <p><strong>Report Generated Successfully</strong> &nbsp;·&nbsp; {self.results["total"]} tests &nbsp;·&nbsp; {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                    </div>
                </div>
            </div>
        </div>

        <div id="analytics" class="tab-content">
            {self._generate_performance_analytics_html()}
        </div>
    </div>

    <script>
        // ── Baked-in run data ─────────────────────────────────────────────
        const RUN = {{
            tag: "{self.test_tag}", browser: "{self.test_browser}", env: "{self.test_env}",
            date: "{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            total: {self.results["total"]}, passed: {self.results["passed"]},
            failed: {self.results["failed"]}, broken: {self.results["broken"]},
            skipped: {self.results["skipped"]},
            passRate: {pass_rate:.1f},
            topErrors: [{", ".join(f'{{msg: "{html_lib.escape(err[:80]).replace(chr(34), chr(39))}", count: {len(tests)}}}' for err, tests in failure_groups[:5] if err)}]
        }};

        // ── State ──────────────────────────────────────────────────────────
        let statFilter = 'all';
        let typeFilter = 'all';

        // ── 8. Active Filters Bar ────────────────────────────────────────
        function updateFiltersBar() {{
            const bar   = document.getElementById('activeFiltersBar');
            const stTag = document.getElementById('afStatTag');
            const tyTag = document.getElementById('afTypeTag');
            const erTag = document.getElementById('afErrTag');
            const isDefault = statFilter === 'all' && typeFilter === 'all' && !errorFilter;
            bar.classList.toggle('visible', !isDefault);
            stTag.textContent = statFilter === 'all' ? 'All' : statFilter.charAt(0).toUpperCase() + statFilter.slice(1);
            tyTag.textContent = typeFilter === 'all' ? 'All Tests' : typeFilter.toUpperCase() + ' Tests';
            if (errorFilter) {{
                erTag.style.display = '';
                erTag.textContent = errorFilter.length > 40 ? errorFilter.slice(0, 40) + '...' : errorFilter;
                erTag.title = errorFilter;
            }} else {{
                erTag.style.display = 'none';
            }}
        }}

        // ── Apply all filters together ────────────────────────────────────
        function applyFilters() {{
            const searchTerm = (document.getElementById('searchBox').value || '').toLowerCase();
            document.querySelectorAll('#testCardsContainer .test-card').forEach(card => {{
                const matchesType = typeFilter === 'all' || (card.dataset.prefix || '') === typeFilter;
                const matchesStat = statFilter === 'all'
                    || card.classList.contains(statFilter)
                    || (statFilter === 'failed' && (card.classList.contains('failed') || card.classList.contains('broken')));
                const matchesErr  = !errorFilter || (card.dataset.keyError || '') === errorFilter;
                const title = (card.querySelector('.test-title') || {{}}).textContent || '';
                const matchesSearch = !searchTerm || title.toLowerCase().includes(searchTerm);
                card.style.display = (matchesType && matchesStat && matchesErr && matchesSearch) ? '' : 'none';
            }});
            document.querySelectorAll('#combinedSidebar .test-item').forEach(item => {{
                const card = document.querySelector('#testCardsContainer .test-card[data-card-id="' + item.dataset.cardId + '"]');
                item.style.display = (!card || card.style.display === 'none') ? 'none' : '';
            }});
            updateFiltersBar();
        }}

        // ── Stat card click ───────────────────────────────────────────────
        function filterByStat(status, card) {{
            document.querySelectorAll('.stat-card').forEach(c => c.classList.remove('stat-active'));
            card.classList.add('stat-active');
            statFilter = status;
            errorFilter = '';
            document.querySelectorAll('.fg-link').forEach(b => b.classList.remove('active'));
            applyFilters();
        }}

        // ── Type tab (All / API / UI) ─────────────────────────────────────
        function switchType(type, btn) {{
            document.querySelectorAll('.type-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            typeFilter = type;
            applyFilters();
        }}

        // ── 1. Filter by error group ──────────────────────────────────────
        function filterByError(err, btn) {{
            if (errorFilter === err) {{
                errorFilter = '';
                btn.classList.remove('active');
            }} else {{
                errorFilter = err;
                document.querySelectorAll('.fg-link').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            }}
            applyFilters();
        }}

        function clearAllFilters() {{
            statFilter  = 'all';
            typeFilter  = 'all';
            errorFilter = '';
            document.querySelectorAll('.stat-card').forEach(c => c.classList.remove('stat-active'));
            const totalCard = document.querySelector('.stat-card');
            if (totalCard) totalCard.classList.add('stat-active');
            document.querySelectorAll('.type-tab').forEach((b,i) => b.classList.toggle('active', i===0));
            document.querySelectorAll('.fg-link').forEach(b => b.classList.remove('active'));
            document.getElementById('searchBox').value = '';
            applyFilters();
        }}

        // ── Main nav tab ─────────────────────────────────────────────────
        function switchTab(tabName, btn) {{
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.nav-tab-btn').forEach(b => b.classList.remove('active'));
            const tab = document.getElementById(tabName);
            if (tab) tab.classList.add('active');
            if (btn) btn.classList.add('active');
            document.getElementById('jumpFab').classList.toggle('hidden', tabName !== 'executions');
        }}

        // ── Toggle card details ───────────────────────────────────────────
        function toggleDetails(cardId) {{
            const details = document.getElementById('details-' + cardId);
            if (!details) return;
            let card = details.parentElement;
            while (card && !card.classList.contains('test-card')) card = card.parentElement;
            if (card) {{ card.classList.toggle('expanded'); details.classList.toggle('expanded'); }}
        }}

        function filterTests() {{ applyFilters(); }}

        function selectTest(cardId) {{
            document.querySelectorAll('.test-item').forEach(i => i.classList.remove('active'));
            const item = document.querySelector('[data-card-id="' + cardId + '"].test-item');
            if (item) item.classList.add('active');
            const card = document.querySelector('.test-card[data-card-id="' + cardId + '"]');
            if (card) {{
                card.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                if (!card.classList.contains('expanded')) {{
                    card.classList.add('expanded');
                    const d = card.querySelector('.test-details');
                    if (d) d.classList.add('expanded');
                }}
            }}
        }}

        // ── 2. Copy error text ────────────────────────────────────────────
        function copyText(btn, text) {{
            navigator.clipboard.writeText(text).then(() => {{
                btn.textContent = '✓ Copied';
                btn.classList.add('copied');
                setTimeout(() => {{ btn.textContent = '📋 Copy'; btn.classList.remove('copied'); }}, 2000);
            }});
        }}

        // ── 3. Jump to first failure ──────────────────────────────────────
        function jumpToFirstFailure() {{
            const first = document.querySelector('#testCardsContainer .test-card.failed:not([style*="none"]), #testCardsContainer .test-card.broken:not([style*="none"])');
            if (!first) return;
            first.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            if (!first.classList.contains('expanded')) {{
                first.classList.add('expanded');
                const d = first.querySelector('.test-details');
                if (d) d.classList.add('expanded');
            }}
        }}

        // ── 4. JSON syntax highlight ──────────────────────────────────────
        function highlightJSON(pre) {{
            try {{
                let t = pre.textContent;
                t = t.replace(/("(?:[^"\\\\]|\\\\.)*")(\s*:)/g, '<span class="j-key">$1</span>$2');
                t = t.replace(/:\s*("(?:[^"\\\\]|\\\\.)*")/g, ': <span class="j-str">$1</span>');
                t = t.replace(/:\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g, ': <span class="j-num">$1</span>');
                t = t.replace(/:\s*(true|false)/g, ': <span class="j-bool">$1</span>');
                t = t.replace(/:\s*(null)/g, ': <span class="j-null">$1</span>');
                pre.innerHTML = t;
            }} catch(e) {{}}
        }}

        // ── 5. Screenshot lightbox ────────────────────────────────────────
        function openLightbox(src) {{
            document.getElementById('lightbox-img').src = src;
            document.getElementById('lightbox').classList.add('open');
            document.body.style.overflow = 'hidden';
        }}
        function closeLightbox(e) {{
            if (e && e.target !== document.getElementById('lightbox') && e.target !== document.getElementById('lightbox-close')) return;
            document.getElementById('lightbox').classList.remove('open');
            document.body.style.overflow = '';
        }}
        document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeLightbox({{ target: document.getElementById('lightbox') }}); }});

        // ── 7. Copy summary for ADO ───────────────────────────────────────
        function copyRunSummary(btn) {{
            const errLines = RUN.topErrors.map(e => '  • ' + e.msg + ' (' + e.count + ' test' + (e.count>1?'s':'') + ')').join('\\n');
            const text = [
                '## Automation Run Summary',
                'Date: ' + RUN.date + ' | Tag: ' + RUN.tag + ' | Browser: ' + RUN.browser + ' | Env: ' + RUN.env,
                '',
                '| Status | Count |',
                '|--------|-------|',
                '| Passed  | ' + RUN.passed + ' |',
                '| Failed  | ' + RUN.failed + ' |',
                '| Broken  | ' + RUN.broken + ' |',
                '| Skipped | ' + RUN.skipped + ' |',
                '| **Total** | **' + RUN.total + '** |',
                '',
                '**Pass Rate: ' + RUN.passRate + '%**',
                errLines ? '\\n### Top Failures\\n' + errLines : ''
            ].join('\\n');
            navigator.clipboard.writeText(text).then(() => {{
                btn.textContent = '✓ Copied!';
                btn.classList.add('copied');
                setTimeout(() => {{ btn.textContent = '📋 Copy Summary'; btn.classList.remove('copied'); }}, 2500);
            }});
        }}

        // ── On load ───────────────────────────────────────────────────────
        window.addEventListener('load', () => {{
            document.querySelectorAll('pre.json-preview, pre.api-json').forEach(highlightJSON);
            const hasFails = !!document.querySelector('#testCardsContainer .test-card.failed, #testCardsContainer .test-card.broken');
            document.getElementById('jumpFab').classList.toggle('hidden', !hasFails);
            animateDonut();
        }});

        function animateDonut() {{
            const arc  = document.getElementById('donut-pass-arc');
            const txt  = document.getElementById('donut-pct-text');
            if (!arc) return;

            const target      = parseFloat(arc.dataset.target);
            const circ        = parseFloat(arc.dataset.circumference);
            const targetRate  = parseFloat(arc.dataset.rate);
            const duration    = 1100;
            const startTime   = performance.now();

            function easeOutCubic(t) {{ return 1 - Math.pow(1 - t, 3); }}

            function frame(now) {{
                const progress = Math.min((now - startTime) / duration, 1);
                const eased    = easeOutCubic(progress);
                const current  = target * eased;

                arc.setAttribute('stroke-dasharray', current.toFixed(2) + ' ' + circ);
                if (txt) txt.textContent = Math.round(targetRate * eased) + '%';

                if (progress < 1) requestAnimationFrame(frame);
            }}

            requestAnimationFrame(frame);
        }}
    </script>
</body>
</html>'''
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(output_path)
    
    def _generate_performance_analytics_html(self) -> str:
        """Generate performance analytics section with duration insights, modules, and tiers"""
        analyzer = PerformanceAnalyzer()
        
        # Get duration data from current tests
        durations = []
        tier_data = {}    # tier -> {"passed": 0, "failed": 0, "total": 0}
        
        for test in self.results.get("tests", []):
            name = test.get("name", "")
            status = test.get("status", "unknown")
            duration_ms = test.get("duration", 0)
            
            if status != "skipped" and duration_ms > 0:
                duration_s = duration_ms / 1000
                durations.append({"name": name, "duration": duration_s, "status": status})
                
                # Categorize by tier
                tier = analyzer.get_duration_tier(duration_ms)
                if tier not in tier_data:
                    tier_data[tier] = {"passed": 0, "failed": 0, "total": 0}
                tier_data[tier]["total"] += 1
                if status == "passed":
                    tier_data[tier]["passed"] += 1
                else:
                    tier_data[tier]["failed"] += 1
        
        if not durations:
            return ""
        
        # Sort durations
        durations.sort(key=lambda x: x["duration"], reverse=True)
        
        html = '<div style="background: #f8f9fa; border-radius: 10px; padding: 25px; margin: 25px 0; border-left: 5px solid #2a5298;">'
        html += '<h2 style="margin-top: 0; color: #1e3c72;">⚡ Performance Analytics</h2>'
        
        # 1. TOP 10 SLOWEST TESTS
        html += '<div style="margin-bottom: 30px;">'
        html += '<h3 style="color: #2a5298; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px;">🐌 Top 10 Slowest Tests</h3>'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 13px;">'
        html += '<tr style="background: #f0f0f0; border-bottom: 2px solid #ddd;"><th style="text-align: left; padding: 12px;">Test Name</th><th style="text-align: right; padding: 12px;">Duration</th><th style="text-align: center; padding: 12px;">Status</th></tr>'
        
        for test in durations[:10]:
            status_color = "#27ae60" if test["status"] == "passed" else "#e74c3c"
            status_badge = "✅" if test["status"] == "passed" else "❌"
            html += f'<tr style="border-bottom: 1px solid #eee;"><td style="padding: 10px;">{html_lib.escape(test["name"][:80])}</td><td style="text-align: right; padding: 10px; font-weight: bold;">{test["duration"]:.2f}s</td><td style="text-align: center; padding: 10px; color: {status_color};">{status_badge}</td></tr>'
        
        html += '</table>'
        html += '</div>'
        
        # 2. PERFORMANCE TIER BREAKDOWN
        html += '<div style="margin-bottom: 30px;">'
        html += '<h3 style="color: #2a5298; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px;">📊 Performance Tier Breakdown</h3>'
        html += '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px;">'
        
        # Define tier order
        tier_order = ["< 1s", "1-5s", "5-30s", "30s+"]
        for tier in tier_order:
            if tier in tier_data:
                data = tier_data[tier]
                color = analyzer.get_tier_color(tier)
                pass_rate = (data["passed"] / data["total"] * 100) if data["total"] > 0 else 0
                html += f'''<div style="background: white; border: 2px solid {color}; border-radius: 8px; padding: 15px; text-align: center;">
                    <div style="font-size: 16px; font-weight: bold; color: {color}; margin-bottom: 8px;">{tier}</div>
                    <div style="font-size: 28px; font-weight: bold; color: {color}; margin-bottom: 5px;">{data["total"]}</div>
                    <div style="font-size: 12px; color: #666;">tests</div>
                    <div style="font-size: 13px; color: #27ae60; font-weight: 600; margin-top: 8px;">{pass_rate:.0f}% pass</div>
                </div>'''
        
        html += '</div>'
        html += '</div>'
        
        # 3. DURATION STATISTICS
        if durations:
            duration_values = [d["duration"] for d in durations]
            min_duration = min(duration_values)
            max_duration = max(duration_values)
            avg_duration = statistics.mean(duration_values)
            median_duration = statistics.median(duration_values)
            total_duration = sum(duration_values)
            
            html += '<div style="background: white; border-radius: 8px; padding: 20px; border: 2px solid #e0e0e0;">'
            html += '<h3 style="color: #2a5298; margin-top: 0; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px;">⏱️ Duration Statistics</h3>'
            html += '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px;">'
            
            stats = [
                ("Total Suite Time", f"{total_duration:.2f}s", "#2a5298"),
                ("Average Test", f"{avg_duration:.2f}s", "#f39c12"),
                ("Median Test", f"{median_duration:.2f}s", "#3498db"),
                ("Fastest Test", f"{min_duration:.2f}s", "#27ae60"),
                ("Slowest Test", f"{max_duration:.2f}s", "#e74c3c"),
            ]
            
            for label, value, color in stats:
                html += f'''<div style="padding: 12px; background: #f9f9f9; border-left: 4px solid {color}; border-radius: 4px;">
                    <div style="font-size: 12px; color: #666; font-weight: 600; text-transform: uppercase; margin-bottom: 5px;">{label}</div>
                    <div style="font-size: 22px; font-weight: bold; color: {color};">{value}</div>
                </div>'''
            
            html += '</div>'
            html += '</div>'
        
        # 4. SUITE PASS/FAIL BAR CHART
        suite_data = {}
        for test in self.results.get("tests", []):
            suite = test.get("suite", "") or "Unknown"
            st = test.get("status", "unknown")
            if suite not in suite_data:
                suite_data[suite] = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0}
            if st in suite_data[suite]:
                suite_data[suite][st] += 1

        if suite_data:
            html += '<div style="background:white;border-radius:8px;padding:20px;border:2px solid #e0e0e0;margin-top:25px;">'
            html += '<h3 style="color:#2a5298;margin-top:0;border-bottom:2px solid #e0e0e0;padding-bottom:10px;">📊 Results by Test Suite</h3>'

            max_total = max(sum(v.values()) for v in suite_data.values()) or 1
            for suite, counts in sorted(suite_data.items()):
                total = sum(counts.values())
                p, f, b, s = counts["passed"], counts["failed"], counts["broken"], counts["skipped"]
                failures = f + b
                pass_pct = round(p / total * 100) if total else 0
                fail_pct = round(failures / total * 100) if total else 0
                skip_pct = 100 - pass_pct - fail_pct

                bar_pass  = p / max_total * 100
                bar_fail  = failures / max_total * 100
                bar_skip  = s / max_total * 100

                html += f'''<div style="margin-bottom:14px;">
                    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;">
                        <span style="font-size:13px;font-weight:600;color:#2c3e50;">{html_lib.escape(suite)}</span>
                        <span style="font-size:12px;color:#7f8c8d;">{total} tests &nbsp;·&nbsp;
                            <span style="color:#27ae60;font-weight:600;">{p} pass</span>
                            {f'&nbsp;·&nbsp;<span style="color:#e74c3c;font-weight:600;">{failures} fail</span>' if failures else ''}
                            {f'&nbsp;·&nbsp;<span style="color:#f39c12;font-weight:600;">{s} skip</span>' if s else ''}
                        </span>
                    </div>
                    <div style="display:flex;height:12px;border-radius:6px;overflow:hidden;background:#f0f0f0;">
                        <div style="width:{bar_pass:.1f}%;background:#27ae60;" title="{p} passed"></div>
                        <div style="width:{bar_fail:.1f}%;background:#e74c3c;" title="{failures} failed"></div>
                        <div style="width:{bar_skip:.1f}%;background:#f39c12;" title="{s} skipped"></div>
                    </div>
                </div>'''

            html += '</div>'

        html += '</div>'
        return html

        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
        except:
            return ""
        
        runs = history_data.get("runs", [])
        if len(runs) < 1:
            return ""
        
        # Get current run (latest in history - already updated by _update_test_history)
        current_run = runs[-1] if runs else None
        
        if not current_run:
            return ""
        
        # Get current run's parameters for filtering
        current_tag = current_run.get("tag", "untagged")
        current_env = current_run.get("environment", "unknown")
        
        # Find last run with SAME tag and environment
        last_matching_run = None
        for run in reversed(runs[:-1]):  # Look backwards, excluding current run
            if run.get("tag") == current_tag and run.get("environment") == current_env:
                last_matching_run = run
                break
        
        # No previous run with same tag/env - can't compare
        if not last_matching_run:
            return ""
        
        curr_passed = current_run.get("passed", 0)
        curr_failed = current_run.get("failed", 0) + current_run.get("broken", 0)
        last_passed = last_matching_run.get("passed", 0)
        last_failed = last_matching_run.get("failed", 0) + last_matching_run.get("broken", 0)
        
        passed_diff = curr_passed - last_passed
        failed_diff = curr_failed - last_failed
        
        # Get timestamps for reference
        last_run_timestamp = last_matching_run.get("timestamp", "unknown")
        
        # Build HTML
        html = '<div style="background: #f5f5f5; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid #2196F3;">'
        html += f'<h3 style="margin-top: 0;">📊 Comparison with Last {current_tag.upper()} Run on {current_env.upper()}</h3>'
        html += f'<div style="font-size: 11px; color: #999; margin-bottom: 15px;">Last run: {last_run_timestamp}</div>'
        html += '<div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px;">'
        
        # Passed comparison
        passed_trend = "↑" if passed_diff > 0 else "↓" if passed_diff < 0 else "="
        passed_color = "#4CAF50" if passed_diff >= 0 else "#F44336"
        html += f'<div style="background: white; padding: 15px; border-radius: 6px;">'
        html += f'<div style="font-weight: bold; margin-bottom: 5px;">Passed Tests</div>'
        html += f'<div style="font-size: 24px; color: #4CAF50;">{curr_passed}</div>'
        html += f'<div style="font-size: 12px; color: {passed_color};">{passed_trend} {abs(passed_diff)} (vs {last_passed} last run)</div>'
        html += f'</div>'
        
        # Failed comparison
        failed_trend = "↓" if failed_diff < 0 else "↑" if failed_diff > 0 else "="
        failed_color = "#4CAF50" if failed_diff <= 0 else "#F44336"
        html += f'<div style="background: white; padding: 15px; border-radius: 6px;">'
        html += f'<div style="font-weight: bold; margin-bottom: 5px;">Failed Tests</div>'
        html += f'<div style="font-size: 24px; color: #F44336;">{curr_failed}</div>'
        html += f'<div style="font-size: 12px; color: {failed_color};">{failed_trend} {abs(failed_diff)} (vs {last_failed} last run)</div>'
        html += f'</div>'
        
        # Historical trend
        pass_rate_current = (curr_passed / (curr_passed + curr_failed) * 100) if (curr_passed + curr_failed) > 0 else 0
        pass_rate_last = (last_passed / (last_passed + last_failed) * 100) if (last_passed + last_failed) > 0 else 0
        rate_diff = pass_rate_current - pass_rate_last
        rate_trend = "↑" if rate_diff > 0 else "↓" if rate_diff < 0 else "="
        rate_color = "#4CAF50" if rate_diff >= 0 else "#F44336"
        html += f'<div style="background: white; padding: 15px; border-radius: 6px;">'
        html += f'<div style="font-weight: bold; margin-bottom: 5px;">Pass Rate</div>'
        html += f'<div style="font-size: 24px; color: #2196F3;">{pass_rate_current:.1f}%</div>'
        html += f'<div style="font-size: 12px; color: {rate_color};">{rate_trend} {abs(rate_diff):.1f}% (vs {pass_rate_last:.1f}% last run)</div>'
        html += f'</div>'
        
        html += '</div>'
        
        # ========== REGRESSIONS SECTION ==========
        regressions = self._detect_regressions(current_run, last_matching_run)
        if regressions:
            html += '<div style="margin-top: 20px; padding: 15px; background: #ffebee; border-left: 4px solid #F44336; border-radius: 6px;">'
            html += f'<h4 style="margin-top: 0; color: #C62828;">❌ {len(regressions)} Regression(s) Detected</h4>'
            html += '<ul style="margin: 10px 0; padding-left: 20px;">'
            for reg in regressions:
                html += f'<li style="margin: 5px 0;"><strong>{html_lib.escape(reg["name"])}</strong> → {reg["was"].upper()} to {reg["now"].upper()}</li>'
            html += '</ul>'
            html += '</div>'
        
        # ========== FIXES SECTION ==========
        fixes = self._detect_fixes(current_run, last_matching_run)
        if fixes:
            html += '<div style="margin-top: 20px; padding: 15px; background: #e8f5e9; border-left: 4px solid #4CAF50; border-radius: 6px;">'
            html += f'<h4 style="margin-top: 0; color: #2e7d32;">✅ {len(fixes)} Test(s) Fixed</h4>'
            html += '<ul style="margin: 10px 0; padding-left: 20px;">'
            for fix in fixes:
                html += f'<li style="margin: 5px 0;"><strong>{html_lib.escape(fix["name"])}</strong> → {fix["was"].upper()} to {fix["now"].upper()}</li>'
            html += '</ul>'
            html += '</div>'
        
        # ========== SLOWEST TESTS SECTION ==========
        slowest_tests = self._get_slowest_tests(current_run, runs)
        if slowest_tests:
            html += '<div style="margin-top: 20px; padding: 15px; background: #fff3e0; border-left: 4px solid #FF9800; border-radius: 6px;">'
            html += '<h4 style="margin-top: 0;">⏱️ Top 5 Slowest Tests</h4>'
            html += '<table style="width: 100%; border-collapse: collapse; font-size: 13px;">'
            html += '<tr style="border-bottom: 1px solid #ddd;"><th style="text-align: left; padding: 8px;">Test Name</th><th style="text-align: right; padding: 8px;">Duration</th><th style="text-align: center; padding: 8px;">Avg</th><th style="text-align: center; padding: 8px;">Trend</th></tr>'
            
            for test in slowest_tests:
                trend_color = "#F44336" if test['trend'] == 'slower' else "#4CAF50" if test['trend'] == 'faster' else "#999"
                trend_icon = "📈" if test['trend'] == 'slower' else "📉" if test['trend'] == 'faster' else "➡️"
                percent_str = f"{abs(test['percent_change']):.0f}%" if test['percent_change'] != 0 else "new"
                
                html += f'<tr style="border-bottom: 1px solid #eee;"><td style="padding: 8px;">{html_lib.escape(test["name"][:80])}</td><td style="text-align: right; padding: 8px;"><strong>{test["duration"]:.2f}s</strong></td>'
                html += f'<td style="text-align: right; padding: 8px;">{test["average"]:.2f}s</td>'
                html += f'<td style="text-align: center; padding: 8px; color: {trend_color};"><strong>{trend_icon} {percent_str}</strong></td></tr>'
            
            html += '</table>'
            html += '</div>'
        
        # ========== FLAKY TESTS SECTION ==========
        flaky_tests = []
        for test_name in current_run.get('tests', {}):
            flaky_info = self._detect_flaky_tests(test_name, runs)
            if flaky_info:
                flaky_tests.append({
                    'name': test_name,
                    **flaky_info
                })
        
        if flaky_tests:
            # Sort by pass rate (closest to 50% is most flaky)
            flaky_tests.sort(key=lambda x: abs(x['pass_rate'] - 50))
            
            html += '<div style="margin-top: 20px; padding: 15px; background: #f3e5f5; border-left: 4px solid #9C27B0; border-radius: 6px;">'
            html += f'<h4 style="margin-top: 0;">⚠️ {len(flaky_tests)} Flaky Test(s) Detected</h4>'
            html += '<ul style="margin: 10px 0; padding-left: 20px;">'
            for test in flaky_tests:
                html += f'<li style="margin: 5px 0;"><strong>{html_lib.escape(test["name"])}</strong> → {test["pass_rate"]:.0f}% pass rate ({test["pass_count"]}/{test["total_runs"]} runs)</li>'
            html += '</ul>'
            html += '</div>'
        
        html += '</div>'
        
        return html

    def _generate_alerts_html(self) -> str:
        """Generate alerts"""
        if not self.state:
            return ""
        
        alerts = []
        
        if self.results['total'] > 0:
            fail_rate = ((self.results['failed'] + self.results['broken']) / self.results['total']) * 100
            if fail_rate > 50:
                alerts.append(f'<div class="alert critical">❌ High failure rate: {fail_rate:.1f}%</div>')
            elif self.results['passed'] / self.results['total'] >= 0.9:
                alerts.append(f'<div class="alert success">✅ Excellent stability</div>')
        
        return "\n".join(alerts)


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python report_generator_enhanced.py <allure_results_dir> [output_dir] [--test-tag TAG] [--test-browser BROWSER] [--test-env ENV]")
        sys.exit(1)
    
    allure_dir = sys.argv[1]
    output_dir = "reports"
    
    # Parse optional parameters
    test_tag = None
    test_browser = None
    test_env = None
    
    args_to_parse = sys.argv[2:]
    i = 0
    while i < len(args_to_parse):
        arg = args_to_parse[i]
        # Check if it's a flag (not output_dir)
        if arg.startswith("--"):
            if arg == "--test-tag" and i + 1 < len(args_to_parse):
                test_tag = args_to_parse[i + 1]
                i += 2
            elif arg == "--test-browser" and i + 1 < len(args_to_parse):
                test_browser = args_to_parse[i + 1]
                i += 2
            elif arg == "--test-env" and i + 1 < len(args_to_parse):
                test_env = args_to_parse[i + 1]
                i += 2
            else:
                i += 1
        else:
            # This is the output_dir
            output_dir = arg
            i += 1
    
    generator = AllureReportGenerator(allure_dir, test_tag, test_browser, test_env)
    generator.parse_results()
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    html_filename = f"{date_str}_report_enhanced.html"
    json_filename = f"{date_str}_data.json"
    
    json_report = generator.generate_json_report(f"{output_dir}/{json_filename}")
    html_report = generator.generate_html_report(f"{output_dir}/{html_filename}")
    
    generator.print_summary()
    
    print(f"[OK] JSON Report: {json_report}")
    print(f"[OK] HTML Report: {html_report}")
    print(f"[OK] Historical tracking updated")


if __name__ == "__main__":
    main()

#EOF