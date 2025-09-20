#!/usr/bin/env python3
"""
CLI Interface for OpenLineage dbt Producer Test Runner

Simple command-line interface for running atomic validation tests.
"""

import click
import json
from pathlib import Path
from openlineage_test_runner import OpenLineageTestRunner


@click.group()
def cli():
    """OpenLineage dbt Producer Test Runner"""
    pass


@cli.command()
@click.option('--base-path', default=None, help='Base path for test execution (auto-detected if not provided)')
@click.option('--output-file', help='Save report to JSON file')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def run_atomic(base_path, output_file, verbose):
    """Run atomic validation tests"""
    click.echo("🧪 Running OpenLineage dbt Producer Atomic Tests...\n")
    
    runner = OpenLineageTestRunner(base_path=base_path)
    report = runner.run_atomic_tests()
    
    # Print report
    runner.print_report(report)
    
    # Save to file if requested
    if output_file:
        report_data = {
            'total_tests': report.total_tests,
            'passed_tests': report.passed_tests, 
            'failed_tests': report.failed_tests,
            'summary': report.summary,
            'results': [
                {
                    'test_name': r.test_name,
                    'passed': r.passed,
                    'message': r.message,
                    'details': r.details
                }
                for r in report.results
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        click.echo(f"\n📄 Report saved to: {output_file}")
    
    # Exit with appropriate code
    if report.failed_tests > 0:
        click.echo(f"\n❌ {report.failed_tests} tests failed")
        exit(1)
    else:
        click.echo(f"\n✅ All {report.total_tests} tests passed!")
        exit(0)


@cli.command()
@click.option('--base-path', default='.', help='Base path for test execution')
def check_environment(base_path):
    """Check if environment is ready for testing"""
    click.echo("🔍 Checking OpenLineage dbt Test Environment...\n")
    
    runner = OpenLineageTestRunner(base_path=base_path)
    
    # Run just the availability tests
    results = []
    results.append(runner.test_dbt_availability())
    results.append(runner.test_duckdb_availability())
    
    all_passed = all(r.passed for r in results)
    
    for result in results:
        status = "✅" if result.passed else "❌"
        click.echo(f"{status} {result.test_name}: {result.message}")
        
        if result.details:
            for key, value in result.details.items():
                click.echo(f"   {key}: {value}")
    
    if all_passed:
        click.echo("\n✅ Environment is ready for testing!")
        exit(0)
    else:
        click.echo("\n❌ Environment issues detected")
        exit(1)


@cli.command()
def setup():
    """Setup test environment and install dependencies"""
    click.echo("⚙️  Setting up OpenLineage dbt Test Environment...\n")
    
    try:
        import subprocess
        import sys
        
        # Install requirements
        requirements_file = Path(__file__).parent / "requirements.txt"
        if requirements_file.exists():
            click.echo("📦 Installing Python dependencies...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ])
            click.echo("✅ Dependencies installed successfully!")
        else:
            click.echo("⚠️  requirements.txt not found")
        
        # Check environment
        click.echo("\n🔍 Checking environment...")
        runner = OpenLineageTestRunner()
        
        dbt_result = runner.test_dbt_availability()
        duckdb_result = runner.test_duckdb_availability()
        
        if dbt_result.passed and duckdb_result.passed:
            click.echo("✅ Environment setup complete!")
            exit(0)
        else:
            click.echo("❌ Environment setup issues detected")
            if not dbt_result.passed:
                click.echo(f"   dbt: {dbt_result.message}")
            if not duckdb_result.passed:
                click.echo(f"   duckdb: {duckdb_result.message}")
            exit(1)
            
    except Exception as e:
        click.echo(f"❌ Setup failed: {str(e)}")
        exit(1)


@cli.command()
def validate_events():
    """Run PIE framework validation tests against generated OpenLineage events"""
    click.echo("🔍 Validating OpenLineage events with PIE framework tests...\n")
    
    try:
        import subprocess
        import sys
        
        validation_script = Path(__file__).parent / "validation_runner.py"
        
        result = subprocess.run([sys.executable, str(validation_script)], 
                              capture_output=False, text=True)
        exit(result.returncode)
    except Exception as e:
        click.echo(f"❌ Error running validation: {e}")
        exit(1)


if __name__ == '__main__':
    cli()