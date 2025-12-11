#!/usr/bin/env python3
"""
OpenLineage dbt Producer Test Runner

A comprehensive test validation library for validating dbt producer compatibility tests
at the most atomic level. This library can execute, validate, and report on each
component of the dbt OpenLineage integration.

Usage:
    from test_runner import OpenLineageTestRunner
    
    runner = OpenLineageTestRunner()
    results = runner.run_all_tests()
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging


@dataclass
class TestResult:
    """Test result container"""
    test_name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    execution_time: Optional[float] = None


@dataclass
class ValidationReport:
    """Complete validation report"""
    total_tests: int
    passed_tests: int
    failed_tests: int
    results: List[TestResult]
    summary: str


class OpenLineageTestRunner:
    """
    Atomic-level test runner for dbt OpenLineage compatibility tests
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize test runner
        
        Args:
            base_path: Base path for test execution. If None, will auto-detect based on script location.
        """
        # Auto-detect base path if not provided
        if base_path is None:
            # We're in producer/dbt/test_runner/, so go up one level to producer/dbt/
            script_dir = Path(__file__).parent
            self.base_path = script_dir.parent
        else:
            self.base_path = Path(base_path)
        
        # Ensure we're working with absolute paths for clarity
        self.base_path = self.base_path.resolve()
        self.base_dir = self.base_path  # Compatibility alias
        
        # Set up paths relative to the base path
        self.dbt_project_dir = self.base_path / "runner"  # Our real dbt project
        self.events_dir = self.base_path / "events"  # Events directory 
        self.output_dir = self.base_path / "output"  # Output directory for reports
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Ensure directories exist
        self.events_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
    
    def test_dbt_availability(self) -> TestResult:
        """
        Test if dbt-ol and dbt are available using simple command existence checks.
        This is a straightforward environment validation approach.
        """
        # Check 1: dbt-ol command exists
        if not shutil.which("dbt-ol"):
            return TestResult(
                test_name="dbt_availability",
                passed=False,
                message="dbt-ol command not found in PATH - please install openlineage-dbt package"
            )
        
        # Check 2: dbt command exists
        if not shutil.which("dbt"):
            return TestResult(
                test_name="dbt_availability",
                passed=False,
                message="dbt command not found in PATH - please install dbt"
            )
        
        # Check 3: Basic project structure exists
        dbt_project_file = self.dbt_project_dir / "dbt_project.yml"
        if not dbt_project_file.exists():
            return TestResult(
                test_name="dbt_availability",
                passed=False,
                message=f"dbt_project.yml not found at {dbt_project_file}"
            )
        
        # All checks passed
        return TestResult(
            test_name="dbt_availability",
            passed=True,
            message="dbt-ol and dbt are available, project structure is valid",
            details={
                "dbt_ol_path": shutil.which("dbt-ol"),
                "dbt_path": shutil.which("dbt"),
                "project_file": str(dbt_project_file)
            }
        )
    
    def test_duckdb_availability(self) -> TestResult:
        """
        Test if DuckDB Python package is available
        """
        try:
            import duckdb
            version = duckdb.__version__
            
            # Test basic DuckDB functionality
            conn = duckdb.connect(":memory:")
            conn.execute("SELECT 1 as test").fetchone()
            conn.close()
            
            return TestResult(
                test_name="duckdb_availability",
                passed=True,
                message="DuckDB is available and functional",
                details={"version": version}
            )
        except ImportError:
            return TestResult(
                test_name="duckdb_availability",
                passed=False,
                message="DuckDB Python package not installed"
            )
        except Exception as e:
            return TestResult(
                test_name="duckdb_availability",
                passed=False,
                message=f"DuckDB test failed: {str(e)}"
            )
    
    def validate_dbt_project_structure(self) -> TestResult:
        """
        Validate that our real dbt project has the required structure
        """
        try:
            required_files = [
                "dbt_project.yml",
                "profiles.yml", 
                "models/schema.yml",
                "models/staging/stg_customers.sql",
                "models/staging/stg_orders.sql", 
                "models/marts/customer_analytics.sql",
                "seeds/raw_customers.csv",
                "seeds/raw_orders.csv"
            ]
            
            missing_files = []
            existing_files = []
            
            for file_path in required_files:
                full_path = self.dbt_project_dir / file_path
                if full_path.exists():
                    existing_files.append(file_path)
                else:
                    missing_files.append(file_path)
            
            if missing_files:
                return TestResult(
                    test_name="validate_dbt_project_structure",
                    passed=False,
                    message=f"Missing required files: {missing_files}",
                    details={
                        "missing_files": missing_files,
                        "existing_files": existing_files,
                        "project_dir": str(self.dbt_project_dir)
                    }
                )
            
            return TestResult(
                test_name="validate_dbt_project_structure",
                passed=True,
                message="dbt project structure is valid",
                details={
                    "project_dir": str(self.dbt_project_dir),
                    "validated_files": existing_files
                }
            )
            
        except Exception as e:
            return TestResult(
                test_name="validate_dbt_project_structure",
                passed=False,
                message=f"Project validation failed: {str(e)}"
            )
    
    def test_dbt_execution(self) -> TestResult:
        """
        Test dbt execution against our real project
        """
        try:
            if not self.dbt_project_dir.exists():
                return TestResult(
                    test_name="test_dbt_execution",
                    passed=False,
                    message=f"dbt project directory not found: {self.dbt_project_dir}"
                )
            
            # Change to dbt project directory
            original_cwd = os.getcwd()
            os.chdir(self.dbt_project_dir)
            
            try:
                # Clean any previous runs using dbt-ol wrapper
                clean_result = subprocess.run(
                    ["dbt-ol", "clean", "--no-version-check"],
                    capture_output=True,
                    text=True,
                    timeout=60  # Increased from 30
                )
                
                # Test dbt-ol seed (load our CSV data) - using OpenLineage wrapper
                seed_result = subprocess.run(
                    ["dbt-ol", "seed", "--no-version-check"],
                    capture_output=True,
                    text=True,
                    timeout=180  # Increased from 60 to account for parsing time
                )
                
                if seed_result.returncode != 0:
                    return TestResult(
                        test_name="test_dbt_execution",
                        passed=False,
                        message=f"dbt-ol seed failed: {seed_result.stderr}",
                        details={
                            "stdout": seed_result.stdout,
                            "stderr": seed_result.stderr
                        }
                    )
                
                # Test dbt-ol run (execute our models) - using OpenLineage wrapper
                run_result = subprocess.run(
                    ["dbt-ol", "run", "--no-version-check"],
                    capture_output=True,
                    text=True,
                    timeout=240  # Increased from 120 to be more generous
                )
                
                if run_result.returncode != 0:
                    return TestResult(
                        test_name="test_dbt_execution",
                        passed=False,
                        message=f"dbt-ol run failed: {run_result.stderr}",
                        details={
                            "stdout": run_result.stdout,
                            "stderr": run_result.stderr
                        }
                    )
                
                return TestResult(
                    test_name="test_dbt_execution",
                    passed=True,
                    message="dbt execution successful using dbt-ol wrapper",
                    details={
                        "project_dir": str(self.dbt_project_dir),
                        "seed_output": seed_result.stdout,
                        "run_output": run_result.stdout
                    }
                )
                
            finally:
                os.chdir(original_cwd)
                
        except subprocess.TimeoutExpired:
            return TestResult(
                test_name="test_dbt_execution",
                passed=False,
                message="dbt execution timed out"
            )
        except Exception as e:
            return TestResult(
                test_name="test_dbt_execution",
                passed=False,
                message=f"dbt execution failed: {str(e)}"
            )

    def test_openlineage_event_generation(self) -> TestResult:
        """
        Test OpenLineage event generation with dbt-ol wrapper
        """
        try:
            if not self.dbt_project_dir.exists():
                return TestResult(
                    test_name="test_openlineage_event_generation",
                    passed=False,
                    message=f"dbt project directory not found: {self.dbt_project_dir}"
                )
            
            # Ensure events directory exists
            events_dir = self.base_dir / "events"
            events_dir.mkdir(exist_ok=True)
            
            # Clear any existing events
            events_file = events_dir / "openlineage_events.jsonl"
            if events_file.exists():
                events_file.unlink()
            
            # Change to dbt project directory
            original_cwd = os.getcwd()
            os.chdir(self.dbt_project_dir)
            
            try:
                # Set OpenLineage environment variables
                env = os.environ.copy()
                openlineage_config = self.dbt_project_dir / "openlineage.yml"
                
                if openlineage_config.exists():
                    env["OPENLINEAGE_CONFIG"] = str(openlineage_config)
                
                # Set namespace for our test environment
                env["OPENLINEAGE_NAMESPACE"] = "dbt_compatibility_test"
                
                # Run dbt with OpenLineage integration using dbt-ol wrapper
                run_result = subprocess.run(
                    ["dbt-ol", "run", "--no-version-check"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    env=env
                )
                
                # Check if events were generated
                if events_file.exists():
                    with open(events_file, 'r') as f:
                        content = f.read().strip()
                        
                    if content:
                        # Basic validation - check for OpenLineage event structure
                        import json
                        lines = content.strip().split('\n')
                        valid_events = 0
                        event_types = []
                        
                        for line in lines:
                            if line.strip():
                                try:
                                    event = json.loads(line)
                                    if 'eventType' in event and 'eventTime' in event:
                                        valid_events += 1
                                        event_types.append(event.get('eventType', 'unknown'))
                                except json.JSONDecodeError:
                                    continue
                        
                        if valid_events > 0:
                            return TestResult(
                                test_name="test_openlineage_event_generation",
                                passed=True,
                                message=f"OpenLineage events generated successfully via dbt-ol",
                                details={
                                    "events_file": str(events_file),
                                    "valid_events": valid_events,
                                    "event_types": event_types,
                                    "file_size": len(content),
                                    "dbt_output": run_result.stdout[-1000:] if run_result.stdout else ""
                                }
                            )
                        else:
                            return TestResult(
                                test_name="test_openlineage_event_generation",
                                passed=False,
                                message="Events file contains no valid OpenLineage events",
                                details={
                                    "events_file": str(events_file),
                                    "file_content": content[:500] + "..." if len(content) > 500 else content
                                }
                            )
                    else:
                        return TestResult(
                            test_name="test_openlineage_event_generation",
                            passed=False,
                            message="Events file exists but is empty"
                        )
                else:
                    # Check if dbt-ol command failed
                    if run_result.returncode != 0:
                        return TestResult(
                            test_name="test_openlineage_event_generation",
                            passed=False,
                            message=f"dbt-ol command failed with return code {run_result.returncode}",
                            details={
                                "stdout": run_result.stdout,
                                "stderr": run_result.stderr,
                                "expected_file": str(events_file)
                            }
                        )
                    else:
                        return TestResult(
                            test_name="test_openlineage_event_generation",
                            passed=False,
                            message="No OpenLineage events file generated, but dbt-ol succeeded",
                            details={
                                "expected_file": str(events_file),
                                "dbt_output": run_result.stdout,
                                "dbt_stderr": run_result.stderr
                            }
                        )
                    
            finally:
                os.chdir(original_cwd)
                
        except subprocess.TimeoutExpired:
            return TestResult(
                test_name="test_openlineage_event_generation",
                passed=False,
                message="dbt-ol execution timed out"
            )
        except FileNotFoundError:
            return TestResult(
                test_name="test_openlineage_event_generation",
                passed=False,
                message="dbt-ol command not found. Make sure openlineage-dbt package is installed."
            )
        except Exception as e:
            return TestResult(
                test_name="test_openlineage_event_generation",
                passed=False,
                message=f"OpenLineage event generation failed: {str(e)}"
            )
    
    def run_atomic_tests(self) -> ValidationReport:
        """
        Run all atomic tests in sequence against our real dbt project
        """
        results = []
        
        # Availability tests (no setup needed)
        results.append(self.test_dbt_availability())
        results.append(self.test_duckdb_availability())
        
        # Project structure validation
        structure_result = self.validate_dbt_project_structure()
        results.append(structure_result)
        
        if structure_result.passed:
            # dbt execution test
            execution_result = self.test_dbt_execution()
            results.append(execution_result)
            
            # OpenLineage event generation test (only if dbt execution passed)
            if execution_result.passed:
                results.append(self.test_openlineage_event_generation())
        
        return self._generate_report(results)
    
    def _generate_report(self, results: List[TestResult]) -> ValidationReport:
        """
        Generate validation report from test results
        """
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.passed)
        failed_tests = total_tests - passed_tests
        
        if failed_tests == 0:
            summary = f"✅ ALL {total_tests} ATOMIC TESTS PASSED"
        else:
            summary = f"❌ {failed_tests}/{total_tests} TESTS FAILED"
        
        return ValidationReport(
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            results=results,
            summary=summary
        )
    
    def print_report(self, report: ValidationReport) -> None:
        """
        Print formatted validation report
        """
        print("\n" + "="*60)
        print("OpenLineage dbt Producer Test Validation Report")
        print("="*60)
        print(f"\n{report.summary}\n")
        
        for result in report.results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"{status} | {result.test_name}")
            print(f"      {result.message}")
            
            if result.details:
                for key, value in result.details.items():
                    if isinstance(value, (list, dict)):
                        print(f"      {key}: {json.dumps(value, indent=2)}")
                    else:
                        print(f"      {key}: {value}")
            print()


def main():
    """
    Main execution function for standalone usage
    """
    runner = OpenLineageTestRunner()
    report = runner.run_atomic_tests()
    runner.print_report(report)
    
    # Exit with error code if any tests failed
    sys.exit(0 if report.failed_tests == 0 else 1)


if __name__ == "__main__":
    main()