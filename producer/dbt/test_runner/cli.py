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
@click.option('--events-file', required=True, help='Path to OpenLineage events JSONL file')
@click.option('--spec-dir', required=True, help='Path to OpenLineage specification directory')
def validate_events(events_file, spec_dir):
    """Run schema validation against OpenLineage specifications"""
    click.echo("🔍 Validating OpenLineage events against official schemas...\n")
    
    try:
        from validation_runner import run_schema_validation
        
        events_path = Path(events_file)
        spec_path = Path(spec_dir)
        
        if not events_path.exists():
            click.echo(f"❌ Events file not found: {events_path}")
            exit(1)
            
        if not spec_path.exists():
            click.echo(f"❌ Spec directory not found: {spec_path}")
            exit(1)
        
        success = run_schema_validation(events_path, spec_path)
        exit(0 if success else 1)
        
    except Exception as e:
        click.echo(f"❌ Error running validation: {e}")
        exit(1)


@cli.command()
@click.option('--scenario', required=True, help='Scenario name to run')
@click.option('--output-dir', required=True, help='Output directory for events')
def run_scenario(scenario, output_dir):
    """Run a specific scenario for CI/CD workflow using dbt-ol wrapper"""
    import subprocess
    import os
    
    click.echo(f"🚀 Running scenario: {scenario}")
    click.echo(f"📁 Output directory: {output_dir}\n")
    
    # Validate scenario exists
    scenario_path = Path(__file__).parent.parent / "scenarios" / scenario
    if not scenario_path.exists():
        click.echo(f"❌ Scenario not found: {scenario}")
        exit(1)
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Path to runner directory
    runner_dir = Path(__file__).parent.parent / "runner"
    
    # Create scenario-specific output directory
    scenario_output_dir = output_path / scenario
    scenario_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Temporary events file for this run
    temp_events_file = scenario_output_dir / "openlineage_events.jsonl"
    
    # Backup and modify openlineage.yml
    openlineage_config = runner_dir / "openlineage.yml"
    openlineage_backup = runner_dir / "openlineage.yml.backup"
    
    import shutil
    import yaml
    
    try:
        # Backup original config
        if openlineage_config.exists():
            shutil.copy(openlineage_config, openlineage_backup)
        
        # Update config to write to our output directory
        config = {
            'transport': {
                'type': 'file',
                'log_file_path': str(temp_events_file.absolute()),
                'append': False
            }
        }
        
        with open(openlineage_config, 'w') as f:
            yaml.dump(config, f)
        
        click.echo("📝 Updated OpenLineage configuration")
        
        # Run dbt-ol commands (wrapper that emits OpenLineage events)
        click.echo("🔨 Running dbt-ol seed...")
        result = subprocess.run(
            ['dbt-ol', 'seed', '--project-dir', str(runner_dir), '--profiles-dir', str(runner_dir), 
             '--vars', f'scenario: {scenario}', '--no-version-check'],
            cwd=runner_dir,
            check=True
        )
        
        click.echo("🔨 Running dbt-ol run...")
        subprocess.run(
            ['dbt-ol', 'run', '--project-dir', str(runner_dir), '--profiles-dir', str(runner_dir),
             '--vars', f'scenario: {scenario}', '--no-version-check'],
            cwd=runner_dir,
            check=True
        )
        
        click.echo("🔨 Running dbt-ol test...")
        result = subprocess.run(
            ['dbt-ol', 'test', '--project-dir', str(runner_dir), '--profiles-dir', str(runner_dir),
             '--vars', f'scenario: {scenario}', '--no-version-check'],
            cwd=runner_dir
        )
        if result.returncode != 0:
            click.echo("⚠️  dbt test had failures (continuing to capture events)")
        
        # The file transport creates individual JSON files with timestamps
        # Find and rename them to sequential format
        import glob
        event_files = sorted(glob.glob(str(scenario_output_dir / "openlineage_events.jsonl-*.json")))
        
        if event_files:
            click.echo(f"📋 Generated {len(event_files)} OpenLineage events")
            
            # Rename to sequential format
            for i, event_file in enumerate(event_files, 1):
                old_path = Path(event_file)
                new_path = scenario_output_dir / f"event_{i:03d}.json"
                old_path.rename(new_path)
            
            click.echo(f"✅ Events written to {scenario_output_dir}")
        else:
            click.echo(f"⚠️  No events generated in {scenario_output_dir}")
        
        exit(0)
        
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ dbt command failed: {e}")
        if e.output:
            click.echo(f"   Output: {e.output.decode()}")
        exit(1)
    except Exception as e:
        click.echo(f"❌ Error running scenario: {e}")
        exit(1)
    finally:
        # Restore original config
        if openlineage_backup.exists():
            shutil.move(openlineage_backup, openlineage_config)
            click.echo("🔄 Restored original OpenLineage configuration")


if __name__ == '__main__':
    cli()