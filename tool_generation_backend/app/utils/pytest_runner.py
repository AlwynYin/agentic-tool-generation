"""
Pytest runner utility for executing generated tests and parsing results.
"""

import asyncio
import json
import re
import logging
from pathlib import Path
from typing import Optional, Tuple
from app.models.pipeline_v2 import TestResults, TestFailure
from app.config import get_settings

logger = logging.getLogger(__name__)


class PytestRunner:
    """
    Executes pytest on generated test files and parses results.
    """

    def __init__(self):
        self.settings = get_settings()
        self.timeout = self.settings.pytest_timeout

    async def run_tests(
        self,
        test_file_path: str,
        working_dir: Optional[str] = None
    ) -> TestResults:
        """
        Run pytest on a test file and return parsed results.

        Args:
            test_file_path: Path to the test file (absolute or relative)
            working_dir: Working directory for pytest execution (defaults to tool_service_dir)

        Returns:
            TestResults: Parsed test execution results
        """
        try:
            # Default to tool_service directory if not specified
            if working_dir is None:
                working_dir = self.settings.tool_service_dir

            # Build pytest command
            cmd = [
                "pytest",
                test_file_path,
                "-v",  # Verbose output
                "--tb=short",  # Short traceback format
                "--json-report",  # Generate JSON report
                "--json-report-file=.pytest_report.json",  # Report file location
                f"--timeout={self.timeout}",  # Test timeout
            ]

            # Optional: Add coverage if configured
            # cmd.extend(["--cov", "--cov-report=json"])

            logger.info(f"Running pytest: {' '.join(cmd)}")
            logger.info(f"Working directory: {working_dir}")

            # Execute pytest
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout + 10  # Add buffer to pytest's own timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                logger.error(f"Pytest execution timed out after {self.timeout + 10} seconds")
                return TestResults(
                    passed=0,
                    failed=0,
                    errors=1,
                    failures=[TestFailure(
                        test_name="pytest_execution",
                        error_message=f"Test execution timed out after {self.timeout + 10} seconds",
                        traceback=""
                    )],
                    duration=float(self.timeout + 10)
                )

            stdout_text = stdout.decode('utf-8')
            stderr_text = stderr.decode('utf-8')

            logger.info(f"Pytest stdout:\n{stdout_text}")
            if stderr_text:
                logger.warning(f"Pytest stderr:\n{stderr_text}")

            # Parse JSON report if available
            json_report_path = Path(working_dir) / ".pytest_report.json"
            if json_report_path.exists():
                results = self._parse_json_report(json_report_path)
            else:
                # Fallback to parsing stdout
                logger.warning("JSON report not found, parsing stdout")
                results = self._parse_stdout(stdout_text, stderr_text)

            # Clean up report file
            if json_report_path.exists():
                json_report_path.unlink()

            return results

        except FileNotFoundError as e:
            logger.error(f"Test file not found: {test_file_path}")
            return TestResults(
                passed=0,
                failed=0,
                errors=1,
                failures=[TestFailure(
                    test_name="file_not_found",
                    error_message=f"Test file not found: {test_file_path}",
                    traceback=str(e)
                )]
            )
        except Exception as e:
            logger.error(f"Error running pytest: {e}")
            return TestResults(
                passed=0,
                failed=0,
                errors=1,
                failures=[TestFailure(
                    test_name="pytest_execution_error",
                    error_message=str(e),
                    traceback=""
                )]
            )

    def _parse_json_report(self, report_path: Path) -> TestResults:
        """
        Parse pytest JSON report.

        Args:
            report_path: Path to .pytest_report.json

        Returns:
            TestResults: Parsed results
        """
        try:
            with open(report_path, 'r') as f:
                data = json.load(f)

            summary = data.get('summary', {})
            tests = data.get('tests', [])

            passed = summary.get('passed', 0)
            failed = summary.get('failed', 0)
            errors = summary.get('error', 0)
            duration = data.get('duration', 0.0)

            # Extract failures
            failures = []
            for test in tests:
                if test.get('outcome') in ['failed', 'error']:
                    failures.append(TestFailure(
                        test_name=test.get('nodeid', 'unknown'),
                        error_message=test.get('call', {}).get('longrepr', 'Unknown error'),
                        traceback=test.get('call', {}).get('longrepr', '')
                    ))

            return TestResults(
                passed=passed,
                failed=failed,
                errors=errors,
                failures=failures,
                duration=duration
            )

        except Exception as e:
            logger.error(f"Error parsing JSON report: {e}")
            return TestResults(
                passed=0,
                failed=0,
                errors=1,
                failures=[TestFailure(
                    test_name="report_parsing_error",
                    error_message=f"Failed to parse pytest report: {str(e)}",
                    traceback=""
                )]
            )

    def _parse_stdout(self, stdout: str, stderr: str) -> TestResults:
        """
        Fallback parser for pytest stdout when JSON report is unavailable.

        Args:
            stdout: Pytest stdout text
            stderr: Pytest stderr text

        Returns:
            TestResults: Parsed results
        """
        passed = 0
        failed = 0
        errors = 0
        failures = []

        # Parse summary line (e.g., "5 passed, 2 failed in 1.23s")
        summary_pattern = r'(\d+)\s+passed'
        summary_match = re.search(summary_pattern, stdout)
        if summary_match:
            passed = int(summary_match.group(1))

        failed_pattern = r'(\d+)\s+failed'
        failed_match = re.search(failed_pattern, stdout)
        if failed_match:
            failed = int(failed_match.group(1))

        error_pattern = r'(\d+)\s+error'
        error_match = re.search(error_pattern, stdout)
        if error_match:
            errors = int(error_match.group(1))

        # Parse duration
        duration_pattern = r'in\s+([\d.]+)s'
        duration_match = re.search(duration_pattern, stdout)
        duration = float(duration_match.group(1)) if duration_match else 0.0

        # Parse individual test failures (simple extraction)
        # This is a basic implementation - the JSON report is preferred
        failure_pattern = r'FAILED\s+([\w/:.]+)\s+-\s+(.*?)(?=\n\n|\Z)'
        failure_matches = re.finditer(failure_pattern, stdout, re.DOTALL)

        for match in failure_matches:
            test_name = match.group(1)
            error_message = match.group(2).strip()
            failures.append(TestFailure(
                test_name=test_name,
                error_message=error_message,
                traceback=""
            ))

        return TestResults(
            passed=passed,
            failed=failed,
            errors=errors,
            failures=failures,
            duration=duration
        )


# Singleton instance
_pytest_runner = None


def get_pytest_runner() -> PytestRunner:
    """Get singleton pytest runner instance."""
    global _pytest_runner
    if _pytest_runner is None:
        _pytest_runner = PytestRunner()
    return _pytest_runner
