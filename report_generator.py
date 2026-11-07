"""
Allure-Style Report Generator for CI Pipeline
Generates an enhanced Allure-like HTML report from pytest allure results
"""

import json
import os
from pathlib import Path
from datetime import datetime
import html as html_lib
import re
import sys


class AllureReportGenerator:
    """Generates Allure-style reports from pytest allure results"""
    
    # Patterns for sensitive data to redact
    SENSITIVE_PATTERNS = [
        r"['\"]password['\"]?\s*[:=]\s*['\"][^'\"]*['\"]",
        r"['\"]passwd['\"]?\s*[:=]\s*['\"][^'\"]*['\"]",
        r"['\"]secret['\"]?\s*[:=]\s*['\"][^'\"]*['\"]",
        r"['\"]api.?key['\"]?\s*[:=]\s*['\"][^'\"]*['\"]",
        r"['\"]token['\"]?\s*[:=]\s*['\"][^'\"]*['\"]",
        r"['\"]authorization['\"]?\s*[:=]\s*['\"][^'\"]*['\"]",
        r"['\"]auth['\"]?\s*[:=]\s*['\"][^'\"]*['\"]",
        r"['\"]client.?secret['\"]?\s*[:=]\s*['\"][^'\"]*['\"]",
        r"[A-Za-z0-9#!@$%^&*]{8,}",  # Generic strong password pattern
    ]

    def __init__(self, allure_results_dir: str, test_tag: str = None, test_browser: str = None, test_env: str = None):
        self.allure_results_dir = Path(allure_results_dir)
        self.test_tag = test_tag or "N/A"
        self.test_browser = test_browser or "N/A"
        self.test_env = test_env or "N/A"
        self.results = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "broken": 0,
            "total": 0,
            "duration": 0,
            "tests": [],
            "timestamp": datetime.now().isoformat(),
            "execution_params": {
                "tag": self.test_tag,
                "browser": self.test_browser,
                "environment": self.test_env
            }
        }

    def _sanitize_sensitive_data(self, text: str) -> str:
        """Remove sensitive information from error messages and traces"""
        if not text:
            return text
        
        # Redact password patterns
        text = re.sub(r"'password':\s*'[^']*'", "'password': '***'", text, flags=re.IGNORECASE)
        text = re.sub(r'"password":\s*"[^"]*"', '"password": "***"', text, flags=re.IGNORECASE)
        text = re.sub(r"password\s*=\s*['\"][^'\"]*['\"]", "password = '***'", text, flags=re.IGNORECASE)
        
        # Redact API keys
        text = re.sub(r"'api_key':\s*'[^']*'", "'api_key': '***'", text, flags=re.IGNORECASE)
        text = re.sub(r'"api_key":\s*"[^"]*"', '"api_key": "***"', text, flags=re.IGNORECASE)
        text = re.sub(r"'client_id':\s*'[^']*'", "'client_id': '***'", text, flags=re.IGNORECASE)
        text = re.sub(r'"client_id":\s*"[^"]*"', '"client_id": "***"', text, flags=re.IGNORECASE)
        
        # Redact tokens
        text = re.sub(r"'token':\s*'[^']*'", "'token': '***'", text, flags=re.IGNORECASE)
        text = re.sub(r'"token":\s*"[^"]*"', '"token": "***"', text, flags=re.IGNORECASE)
        
        # Redact Bearer tokens
        text = re.sub(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer ***", text, flags=re.IGNORECASE)
        
        # Redact config dict credentials
        text = re.sub(r"'[a-z_]*password[a-z_]*':\s*'[^']*'", "'***': '***'", text, flags=re.IGNORECASE)
        text = re.sub(r'"[a-z_]*password[a-z_]*":\s*"[^"]*"', '"***": "***"', text, flags=re.IGNORECASE)
        
        # Redact entire config sections that contain credentials
        text = re.sub(r"'[a-z_]*(?:password|secret|token|key)[a-z_]*':\s*'[^']*'", "'***': '***'", text, flags=re.IGNORECASE)
        
        return text

    def parse_results(self) -> dict:
        """Parse allure results and extract detailed test information"""
        if not self.allure_results_dir.exists():
            print(f"Warning: Allure results directory not found: {self.allure_results_dir}")
            return self.results

        # Find all result.json files
        result_files = sorted(self.allure_results_dir.glob("*-result.json"))
        
        for result_file in result_files:
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                    
                    status = result.get("status", "unknown")
                    name = result.get("name", "Unknown Test")
                    duration = result.get("stop", 0) - result.get("start", 0)
                    
                    # Extract failure info and sanitize
                    failure_info = None
                    if status in ["failed", "broken"]:
                        status_details = result.get("statusDetails", {})
                        message = status_details.get("message", "No error message")
                        trace = status_details.get("trace", "No trace available")
                        
                        # Sanitize sensitive data
                        message = self._sanitize_sensitive_data(message)
                        trace = self._sanitize_sensitive_data(trace)
                        
                        failure_info = {
                            "message": message,
                            "trace": trace
                        }
                    
                    # Extract test details
                    test_info = {
                        "name": html_lib.escape(name),
                        "status": status,
                        "duration": duration,
                        "description": result.get("description", ""),
                        "labels": result.get("labels", []),
                        "steps": result.get("steps", []),
                        "attachments": result.get("attachments", []),
                        "failure": failure_info
                    }
                    
                    # Update counters
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
        
        return self.results

    def generate_json_report(self, output_path: str) -> str:
        """Generate JSON report"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2)
        
        return str(output_path)

    def print_summary(self):
        """Print summary to console"""
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
        """Generate beautiful Allure-style HTML report"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        if self.results['total'] > 0:
            pass_rate = (self.results['passed'] / self.results['total']) * 100
        else:
            pass_rate = 0
        
        status_color = "#4CAF50" if pass_rate >= 80 else "#FF9800" if pass_rate >= 50 else "#F44336"
        status_text = "PASSED" if pass_rate >= 80 else "WARNING" if pass_rate >= 50 else "FAILED"
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Automation Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #f5f5f5;
            color: #333;
        }}
        .navbar {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 40px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }}
        .navbar h1 {{
            font-size: 28px;
            font-weight: bold;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }}
        .status-badge {{
            display: inline-block;
            background-color: {status_color};
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 30px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 4px;
            border-left: 4px solid #667eea;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            text-align: center;
        }}
        .stat-card.passed {{
            border-left-color: #4CAF50;
        }}
        .stat-card.failed {{
            border-left-color: #F44336;
        }}
        .stat-card.skipped {{
            border-left-color: #FF9800;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
        }}
        .stat-label {{
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .progress-section {{
            background: white;
            padding: 20px;
            border-radius: 4px;
            margin-bottom: 40px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        .progress-bar {{
            width: 100%;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 10px;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #4CAF50, #45a049);
            width: {pass_rate}%;
            transition: width 0.3s ease;
        }}
        .progress-text {{
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
        .test-section {{
            background: white;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .section-title {{
            background: #f5f5f5;
            padding: 15px 20px;
            border-bottom: 1px solid #e0e0e0;
            font-weight: bold;
            color: #333;
        }}
        .test-item {{
            padding: 15px 20px;
            border-left: 4px solid #ccc;
            border-bottom: 1px solid #f0f0f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .test-item:last-child {{
            border-bottom: none;
        }}
        .test-item.passed {{
            border-left-color: #4CAF50;
            background: #f1f8f6;
        }}
        .test-item.failed {{
            border-left-color: #F44336;
            background: #fef5f5;
        }}
        .test-item.broken {{
            border-left-color: #F44336;
            background: #fef5f5;
        }}
        .test-item.skipped {{
            border-left-color: #FF9800;
            background: #fffaf0;
        }}
        .test-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
            cursor: pointer;
        }}
        .test-name {{
            flex: 1;
            font-size: 13px;
        }}
        .test-duration {{
            color: #999;
            font-size: 12px;
            margin-right: 15px;
        }}
        .test-status {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .test-status.passed {{
            background: #c8e6c9;
            color: #2e7d32;
        }}
        .test-status.failed {{
            background: #ffcdd2;
            color: #c62828;
        }}
        .test-status.broken {{
            background: #ffcdd2;
            color: #c62828;
        }}
        .test-status.skipped {{
            background: #ffe0b2;
            color: #e65100;
        }}
        .toggle-btn {{
            background: none;
            border: none;
            cursor: pointer;
            font-size: 16px;
            margin-right: 10px;
            color: #666;
        }}
        .test-details {{
            display: none;
            padding: 15px 20px;
            background: white;
            border-bottom: 1px solid #f0f0f0;
            margin-top: 10px;
        }}
        .test-details.expanded {{
            display: block;
        }}
        .failure-section {{
            background: #fff5f5;
            border: 1px solid #ffcdd2;
            border-radius: 4px;
            padding: 15px;
            margin-bottom: 15px;
        }}
        .failure-title {{
            color: #c62828;
            font-weight: bold;
            margin-bottom: 8px;
        }}
        .failure-message {{
            color: #d32f2f;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            white-space: pre-wrap;
            word-break: break-word;
            margin-bottom: 10px;
            max-height: 200px;
            overflow-y: auto;
        }}
        .steps-section {{
            margin-bottom: 15px;
        }}
        .steps-title {{
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
        }}
        .step {{
            background: #f5f5f5;
            border-left: 3px solid #667eea;
            padding: 10px;
            margin-bottom: 8px;
            border-radius: 2px;
        }}
        .step-name {{
            font-weight: bold;
            color: #333;
            font-size: 12px;
        }}
        .step-status {{
            display: inline-block;
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 2px;
            margin-left: 8px;
            font-weight: bold;
        }}
        .step-status.passed {{
            background: #c8e6c9;
            color: #2e7d32;
        }}
        .step-status.failed {{
            background: #ffcdd2;
            color: #c62828;
        }}
        .step-attachments {{
            margin-top: 10px;
        }}
        .attachments-section {{
            margin-top: 15px;
        }}
        .attachments-title {{
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
        }}
        .attachment {{
            margin-bottom: 10px;
        }}
        .attachment-name {{
            font-size: 12px;
            color: #667eea;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .attachment-preview {{
            max-width: 100%;
            max-height: 400px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .json-preview {{
            background: #f5f5f5;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            max-height: 400px;
            overflow-y: auto;
            margin-top: 8px;
            color: #333;
        }}
        .json-preview code {{
            color: #d63384;
        }}
        .json-container {{
            background: #fafafa;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 12px;
            margin-bottom: 12px;
        }}
        .json-label {{
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
            font-size: 12px;
        }}
        .api-section {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 12px;
        }}
        @media (max-width: 768px) {{
            .api-section {{
                grid-template-columns: 1fr;
            }}
        }}
        .image-container {{
            margin-bottom: 12px;
        }}
        .image-label {{
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
            font-size: 12px;
        }}
        .images-section {{
            margin-bottom: 12px;
        }}
        .text-container {{
            margin-bottom: 12px;
        }}
        .text-label {{
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
            font-size: 12px;
        }}
        .text-preview {{
            background: #f5f5f5;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            max-height: 300px;
            overflow-y: auto;
            margin-top: 8px;
            color: #555;
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="navbar">
        <h1>📊 Test Automation Report</h1>
        <div style="font-size: 12px; margin-top: 10px; opacity: 0.9;">
            <span>Tag: <strong>{self.test_tag}</strong></span> | 
            <span>Browser: <strong>{self.test_browser}</strong></span> | 
            <span>Environment: <strong>{self.test_env}</strong></span>
        </div>
    </div>

    <div class="container">
        <div class="status-badge">{status_text}</div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{self.results["total"]}</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat-card passed">
                <div class="stat-value" style="color: #4CAF50;">{self.results["passed"]}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat-card failed">
                <div class="stat-value" style="color: #F44336;">{self.results["failed"] + self.results["broken"]}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat-card skipped">
                <div class="stat-value" style="color: #FF9800;">{self.results["skipped"]}</div>
                <div class="stat-label">Skipped</div>
            </div>
        </div>

        <div class="progress-section">
            <div class="progress-bar">
                <div class="progress-fill"></div>
            </div>
            <div class="progress-text">{pass_rate:.1f}% Pass Rate</div>
        </div>

        <div class="test-section">
            <div class="section-title">Test Results ({self.results["total"]} tests)</div>
            {self._generate_test_list_html()}
        </div>

        <div class="footer">
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Full Allure report available as downloadable artifact</p>
        </div>
    </div>
</body>
</html>
"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(output_path)

    def _generate_test_list_html(self) -> str:
        """Generate HTML for sorted test list (failed → skipped → passed)"""
        html = ""
        
        # Sort tests: failed/broken first, then skipped, then passed
        failed_tests = [t for t in self.results["tests"] if t["status"] in ["failed", "broken"]]
        skipped_tests = [t for t in self.results["tests"] if t["status"] == "skipped"]
        passed_tests = [t for t in self.results["tests"] if t["status"] == "passed"]
        
        sorted_tests = failed_tests + skipped_tests + passed_tests
        
        for idx, test in enumerate(sorted_tests):
            status = test["status"]
            name = test["name"][:100]
            duration_ms = test.get("duration", 0)
            duration_s = duration_ms / 1000
            
            # Check if test has details (failures, steps, attachments)
            has_details = bool(test.get("failure") or test.get("steps") or test.get("attachments"))
            toggle_btn = f'<button class="toggle-btn" onclick="toggleDetails({idx})">▶</button>' if has_details else '<span class="toggle-btn"></span>'
            
            html += f'''<div class="test-item {status}">
                <div class="test-header">
                    {toggle_btn}
                    <span class="test-name">{name}</span>
                    <span class="test-duration">{duration_s:.2f}s</span>
                    <span class="test-status {status}">{status}</span>
                </div>
'''
            
            # Add expandable details section
            if has_details:
                html += f'<div id="details-{idx}" class="test-details">'
                
                # Failure information
                if test.get("failure"):
                    failure = test["failure"]
                    html += f'''<div class="failure-section">
                    <div class="failure-title">❌ Failure Details</div>
                    <div class="failure-message">{html_lib.escape(failure.get("message", "No message"))}</div>
'''
                    if failure.get("trace"):
                        html += f'<div class="failure-message">{html_lib.escape(failure.get("trace", ""))}</div>'
                    html += '</div>'
                
                # Steps information
                if test.get("steps"):
                    html += '<div class="steps-section"><div class="steps-title">📝 Steps</div>'
                    for step in test["steps"]:
                        step_status = step.get("status", "unknown")
                        step_name = html_lib.escape(step.get("name", "Unknown step"))
                        html += f'''<div class="step">
                        <span class="step-name">{step_name}</span>
                        <span class="step-status {step_status}">{step_status.upper()}</span>
'''
                        if step.get("attachments"):
                            html += '<div class="step-attachments">'
                            for att in step.get("attachments", []):
                                att_name = att.get("name", "Attachment")
                                att_type = att.get("type", "")
                                html += f'<div style="font-size: 11px; color: #666;">📎 {att_name} ({att_type})</div>'
                            html += '</div>'
                        html += '</div>'
                    html += '</div>'
                
                # Attachments
                if test.get("attachments"):
                    html += '<div class="attachments-section"><div class="attachments-title">📎 Attachments</div>'
                    
                    # Separate attachments by type for better organization
                    json_attachments = []
                    image_attachments = []
                    text_attachments = []
                    other_attachments = []
                    
                    for att in test["attachments"]:
                        att_type = att.get("type", "")
                        if att_type in ["application/json", "text/json"] or att.get("name", "").lower().endswith(".json"):
                            json_attachments.append(att)
                        elif att_type.startswith("image/"):
                            image_attachments.append(att)
                        elif att_type.startswith("text/"):
                            text_attachments.append(att)
                        else:
                            other_attachments.append(att)
                    
                    # Display JSON attachments (API requests/responses)
                    if json_attachments:
                        html += '<div class="api-section">'
                        for att in json_attachments:
                            att_name = att.get("name", "Attachment")
                            att_source = att.get("source", "")
                            att_file = self.allure_results_dir / att_source
                            
                            if att_file.exists():
                                try:
                                    with open(att_file, 'r', encoding='utf-8') as f:
                                        json_data = json.load(f)
                                    
                                    # Detect if this is response (check for error fields)
                                    is_response = any(key in json_data for key in ["error", "message", "status", "code", "statusCode", "errors"])
                                    label = "📤 Request" if "request" in att_name.lower() else "📥 Response" if "response" in att_name.lower() else ("📥 Response" if is_response else "📤 Request")
                                    
                                    # Check for errors in response
                                    error_msg = json_data.get("message") or json_data.get("error") or json_data.get("errors")
                                    has_error = error_msg or json_data.get("statusCode", 200) >= 400
                                    
                                    html += f'<div class="json-container"><div class="json-label">{label}</div>'
                                    
                                    if has_error and "response" in att_name.lower().lower():
                                        html += f'<div style="background: #fff3cd; border: 1px solid #ffc107; padding: 8px; border-radius: 3px; margin-bottom: 8px; color: #856404; font-weight: bold;">⚠️ Error: {html_lib.escape(str(error_msg))}</div>'
                                    
                                    json_str = json.dumps(json_data, indent=2)
                                    html += f'<pre class="json-preview"><code>{html_lib.escape(json_str)}</code></pre></div>'
                                except Exception as e:
                                    html += f'<pre class="json-preview"><code>Error parsing JSON: {html_lib.escape(str(e))}</code></pre>'
                        html += '</div>'
                    
                    # Display image attachments (screenshots)
                    if image_attachments:
                        html += '<div class="images-section">'
                        for att in image_attachments:
                            att_name = att.get("name", "Screenshot")
                            att_source = att.get("source", "")
                            att_file = self.allure_results_dir / att_source
                            
                            if att_file.exists():
                                html += f'<div class="image-container"><div class="image-label">🖼️ {att_name}</div>'
                                html += f'<img src="data:image/png;base64,{self._get_base64_image(att_file)}" class="attachment-preview" />'
                                html += '</div>'
                        html += '</div>'
                    
                    # Display text attachments
                    if text_attachments:
                        for att in text_attachments:
                            att_name = att.get("name", "Log")
                            att_source = att.get("source", "")
                            att_file = self.allure_results_dir / att_source
                            
                            if att_file.exists():
                                try:
                                    with open(att_file, 'r', encoding='utf-8') as f:
                                        text_content = f.read()
                                    html += f'<div class="text-container"><div class="text-label">📄 {att_name}</div>'
                                    html += f'<pre class="text-preview"><code>{html_lib.escape(text_content[:1000])}</code></pre>'
                                    if len(text_content) > 1000:
                                        html += f'<div style="color: #999; font-size: 11px;">... (truncated, {len(text_content)} bytes total)</div>'
                                    html += '</div>'
                                except Exception as e:
                                    html += f'<pre>Error reading text: {html_lib.escape(str(e))}</pre>'
                    
                    html += '</div>'
                
                html += '</div>'
            
            html += '</div>'
        
        # Add JavaScript for toggle functionality
        html += '''<script>
function toggleDetails(idx) {
    const details = document.getElementById('details-' + idx);
    const btn = event.target;
    if (details.classList.contains('expanded')) {
        details.classList.remove('expanded');
        btn.textContent = '▶';
    } else {
        details.classList.add('expanded');
        btn.textContent = '▼';
    }
}
</script>'''
        
        return html
    
    def _get_base64_image(self, image_path):
        """Convert image to base64 for inline display"""
        try:
            import base64
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"Could not encode image {image_path}: {e}")
            return ""


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    
    if len(sys.argv) < 2:
        print("Usage: python report_generator.py <allure_results_dir> [output_dir] [build_number] [test_tag] [test_browser] [test_env]")
        sys.exit(1)
    
    allure_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "reports"
    build_number = sys.argv[3] if len(sys.argv) > 3 else None
    test_tag = sys.argv[4] if len(sys.argv) > 4 else None
    test_browser = sys.argv[5] if len(sys.argv) > 5 else None
    test_env = sys.argv[6] if len(sys.argv) > 6 else None
    
    # Generate report
    generator = AllureReportGenerator(allure_dir, test_tag=test_tag, test_browser=test_browser, test_env=test_env)
    generator.parse_results()
    
    # Generate filename with date and build number
    date_str = datetime.now().strftime("%Y-%m-%d")
    if build_number:
        html_filename = f"{date_str}_Build{build_number}_report.html"
        json_filename = f"{date_str}_Build{build_number}_data.json"
    else:
        html_filename = f"{date_str}_report.html"
        json_filename = f"{date_str}_data.json"
    
    # Generate outputs
    json_report = generator.generate_json_report(f"{output_dir}/{json_filename}")
    html_report = generator.generate_html_report(f"{output_dir}/{html_filename}")
    
    # Print summary
    generator.print_summary()
    
    print(f"✓ JSON Report: {json_report}")
    print(f"✓ HTML Report: {html_report}")


if __name__ == "__main__":
    main()
