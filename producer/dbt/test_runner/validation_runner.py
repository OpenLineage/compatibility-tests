#!/usr/bin/env python3
"""
Test validation runner for dbt producer compatibility test.

Validates extracted PIE test functions against real OpenLineage events.
"""
import json
import sys
from pathlib import Path

def load_openlineage_events(events_file_path):
    """Load OpenLineage events from JSONL file."""
    events = []
    if not events_file_path.exists():
        print(f"ERROR: Events file not found: {events_file_path}")
        return events
    
    with open(events_file_path, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"WARNING: Failed to parse JSON line: {e}")
    
    print(f"Loaded {len(events)} events from {events_file_path}")
    return events

def validate_schema_facets(events):
    """Test schema facet validation from PIE framework."""
    print("=== Testing Schema Facet Validation ===")
    
    # Find events with schema facets
    schema_events = []
    for event in events:
        if 'outputs' in event:
            for output in event['outputs']:
                if output.get('facets', {}).get('schema'):
                    schema_events.append(event)
                    break
    
    print(f"Found {len(schema_events)} events with schema facets")
    
    if len(schema_events) == 0:
        print("❌ FAIL: No schema facets found in events")
        return False
    
    # Validate schema facet structure
    for i, event in enumerate(schema_events):
        for output in event['outputs']:
            schema_facet = output.get('facets', {}).get('schema')
            if schema_facet:
                print(f"  Event {i+1}: Checking schema facet...")
                
                if 'fields' not in schema_facet:
                    print(f"    ❌ FAIL: Schema facet missing 'fields'")
                    return False
                
                if len(schema_facet['fields']) == 0:
                    print(f"    ❌ FAIL: Schema fields empty")
                    return False
                
                print(f"    ✅ PASS: Schema facet has {len(schema_facet['fields'])} fields")
    
    print("✅ PASS: Schema facet validation")
    return True

def validate_sql_facets(events):
    """Test SQL facet validation from PIE framework."""
    print("=== Testing SQL Facet Validation ===")
    
    # Find events with SQL facets
    sql_events = []
    for event in events:
        if 'job' in event and event['job'].get('facets', {}).get('sql'):
            sql_events.append(event)
    
    print(f"Found {len(sql_events)} events with SQL facets")
    
    if len(sql_events) == 0:
        print("❌ FAIL: No SQL facets found in events")
        return False
    
    # Validate SQL facet structure
    for i, event in enumerate(sql_events):
        sql_facet = event['job']['facets']['sql']
        print(f"  Event {i+1}: Checking SQL facet...")
        
        if 'query' not in sql_facet:
            print(f"    ❌ FAIL: SQL facet missing 'query'")
            return False
        
        if not sql_facet['query'].strip():
            print(f"    ❌ FAIL: SQL query is empty")
            return False
        
        if 'dialect' not in sql_facet:
            print(f"    ❌ FAIL: SQL facet missing 'dialect'")
            return False
        
        print(f"    ✅ PASS: SQL facet has query ({len(sql_facet['query'])} chars) and dialect '{sql_facet['dialect']}'")
    
    print("✅ PASS: SQL facet validation")
    return True

def validate_lineage_structure(events):
    """Test lineage structure validation from PIE framework."""
    print("=== Testing Lineage Structure Validation ===")
    
    # Find START/COMPLETE event pairs
    start_events = [e for e in events if e.get('eventType') == 'START']
    complete_events = [e for e in events if e.get('eventType') == 'COMPLETE']
    
    print(f"Found {len(start_events)} START events and {len(complete_events)} COMPLETE events")
    
    if len(start_events) == 0:
        print("❌ FAIL: No START events found")
        return False
    
    if len(complete_events) == 0:
        print("❌ FAIL: No COMPLETE events found")
        return False
    
    # Validate event structure
    for i, event in enumerate(events):
        print(f"  Event {i+1}: Checking structure...")
        
        required_fields = ['eventTime', 'eventType', 'job', 'run', 'producer']
        for field in required_fields:
            if field not in event:
                print(f"    ❌ FAIL: Missing required field '{field}'")
                return False
        
        # Validate job structure
        job = event['job']
        if 'name' not in job or 'namespace' not in job:
            print(f"    ❌ FAIL: Job missing name or namespace")
            return False
        
        # Validate run structure
        run = event['run']
        if 'runId' not in run:
            print(f"    ❌ FAIL: Run missing runId")
            return False
        
        print(f"    ✅ PASS: Event structure valid")
    
    print("✅ PASS: Lineage structure validation")
    return True

def validate_column_lineage(events):
    """Test column lineage validation from PIE framework."""
    print("=== Testing Column Lineage Validation ===")
    
    # Find events with column lineage facets
    column_lineage_events = []
    for event in events:
        if 'outputs' in event:
            for output in event['outputs']:
                if output.get('facets', {}).get('columnLineage'):
                    column_lineage_events.append(event)
                    break
    
    print(f"Found {len(column_lineage_events)} events with column lineage facets")
    
    if len(column_lineage_events) == 0:
        print("❌ FAIL: No column lineage facets found in events")
        return False
    
    # Validate column lineage structure
    for i, event in enumerate(column_lineage_events):
        for output in event['outputs']:
            col_lineage = output.get('facets', {}).get('columnLineage')
            if col_lineage:
                print(f"  Event {i+1}: Checking column lineage...")
                
                if 'fields' not in col_lineage:
                    print(f"    ❌ FAIL: Column lineage missing 'fields'")
                    return False
                
                fields = col_lineage['fields']
                if len(fields) == 0:
                    print(f"    ❌ FAIL: Column lineage fields empty")
                    return False
                
                # Validate field structure
                for field_name, field_info in fields.items():
                    if 'inputFields' not in field_info:
                        print(f"    ❌ FAIL: Field '{field_name}' missing inputFields")
                        return False
                
                print(f"    ✅ PASS: Column lineage has {len(fields)} fields")
    
    print("✅ PASS: Column lineage validation")
    return True

def validate_dbt_job_naming(events):
    """Test dbt job naming convention from PIE framework."""
    print("=== Testing dbt Job Naming Validation ===")
    
    # Find dbt job events
    dbt_job_events = [e for e in events if 'dbt' in e.get('job', {}).get('namespace', '').lower()]
    
    print(f"Found {len(dbt_job_events)} dbt job events")
    
    if len(dbt_job_events) == 0:
        print("❌ FAIL: No dbt job events found")
        return False
    
    # Validate naming conventions
    for i, event in enumerate(dbt_job_events):
        job = event['job']
        job_name = job['name']
        job_namespace = job['namespace']
        
        print(f"  Event {i+1}: Checking job naming...")
        print(f"    Job name: '{job_name}'")
        print(f"    Job namespace: '{job_namespace}'")
        
        # Check for dbt-specific patterns
        if not any(pattern in job_name.lower() for pattern in ['dbt', 'openlineage_compatibility_test', 'stg_', 'customer']):
            print(f"    ❌ FAIL: Job name doesn't follow dbt conventions")
            return False
        
        if 'dbt' not in job_namespace.lower():
            print(f"    ❌ FAIL: Job namespace doesn't contain 'dbt'")
            return False
        
        print(f"    ✅ PASS: Job naming follows dbt conventions")
    
    print("✅ PASS: dbt job naming validation")
    return True

def main():
    """Run all validation tests against real OpenLineage events."""
    print("OpenLineage dbt Producer Compatibility Test Validation")
    print("=" * 60)
    
    # Load events from the real dbt project
    base_path = Path(__file__).parent.parent
    events_file = base_path / "events" / "openlineage_events.jsonl"
    
    events = load_openlineage_events(events_file)
    
    if not events:
        print("❌ FAIL: No events to validate")
        return False
    
    # Run all validation tests
    tests = [
        validate_schema_facets,
        validate_sql_facets,
        validate_lineage_structure,
        validate_column_lineage,
        validate_dbt_job_naming
    ]
    
    results = []
    for test in tests:
        try:
            result = test(events)
            results.append(result)
            print()
        except Exception as e:
            print(f"❌ ERROR in {test.__name__}: {e}")
            results.append(False)
            print()
    
    # Summary
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    test_names = [
        "Schema Facet Validation",
        "SQL Facet Validation", 
        "Lineage Structure Validation",
        "Column Lineage Validation",
        "dbt Job Naming Validation"
    ]
    
    for i, (test_name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i+1}. {test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL VALIDATION TESTS PASSED!")
        return True
    else:
        print("💥 SOME VALIDATION TESTS FAILED!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)