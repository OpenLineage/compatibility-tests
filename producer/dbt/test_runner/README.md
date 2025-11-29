# OpenLineage dbt Producer Test Runner

## Quick Start

### 1. Setup Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Linux/Mac
# or 
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Tests

```bash
# Check environment
python cli.py check-environment

# Run all atomic tests
python cli.py run-atomic

# Run with verbose output and save report
python cli.py run-atomic --verbose --output-file report.json
```

### 3. Manual Testing

```bash
# Run the test runner directly
python openlineage_test_runner.py

# Or import in Python
python -c "from openlineage_test_runner import OpenLineageTestRunner; runner = OpenLineageTestRunner(); print(runner.run_atomic_tests())"
```

## Test Components

The atomic test runner validates:

1. **Environment Availability**
   - dbt command availability
   - PostgreSQL adapter package installation

2. **dbt Project Creation**
   - Minimal dbt project structure
   - Profile configuration for PostgreSQL

3. **dbt Execution**
   - Model compilation and execution
   - CSV seed loading and transformation

4. **Cleanup**
   - Temporary file removal
   - Project cleanup

## CLI Commands

- `check-environment`: Verify dbt and PostgreSQL adapter availability
- `run-atomic`: Run all atomic validation tests
- `setup`: Install dependencies (requires virtual environment)

## Integration with OpenLineage

This test runner provides the foundation for OpenLineage event validation. When integrated with the OpenLineage dbt adapter, it can capture and validate lineage events generated during dbt execution.

## Troubleshooting

1. **Python Environment Issues**: Use virtual environment as shown above
2. **dbt Not Found**: Install dbt-core and dbt-postgres in your environment
3. **PostgreSQL Issues**: Ensure psycopg2-binary Python package is installed
4. **Permission Errors**: Make sure scripts are executable (`chmod +x`)