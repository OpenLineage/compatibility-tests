#!/usr/bin/env python3
"""
dbt Producer Compatibility Test

This test validates that dbt generates compliant OpenLineage events
when using local file transport with CSV → dbt → DuckDB scenario.

Adapted from DIO11y-lab PIE test framework.
"""
import pytest
import json
import os
from pathlib import Path


def test_schema_facet_validation():
    """Validates OpenLineage schema facet compliance."""
    # Load generated events from file transport
    events_file = Path("output/openlineage_events.json")
    assert events_file.exists(), "OpenLineage events file not found"
    
    with open(events_file, 'r') as f:
        events = [json.loads(line) for line in f if line.strip()]
    
    assert len(events) > 0, "No events found in output file"
    
    # Validate schema facet structure
    schema_events = [e for e in events if 'outputs' in e and 
                    any('facets' in out and 'schema' in out.get('facets', {}) 
                        for out in e['outputs'])]
    
    assert len(schema_events) > 0, "No schema facets found in events"
    
    # Validate schema facet content
    for event in schema_events:
        for output in event['outputs']:
            schema_facet = output.get('facets', {}).get('schema', {})
            if schema_facet:
                assert 'fields' in schema_facet, "Schema facet missing fields"
                assert len(schema_facet['fields']) > 0, "Schema fields empty"


def test_sql_facet_validation():
    """Validates SQL facet presence and structure."""
    events_file = Path("output/openlineage_events.json")
    assert events_file.exists(), "OpenLineage events file not found"
    
    with open(events_file, 'r') as f:
        events = [json.loads(line) for line in f if line.strip()]
    
    # Look for SQL facets in job facets
    sql_events = [e for e in events if 'job' in e and 
                 'facets' in e['job'] and 'sql' in e['job']['facets']]
    
    assert len(sql_events) > 0, "No SQL facets found in events"
    
    for event in sql_events:
        sql_facet = event['job']['facets']['sql']
        assert 'query' in sql_facet, "SQL facet missing query"
        assert len(sql_facet['query'].strip()) > 0, "SQL query is empty"


def test_lineage_structure_validation():
    """Validates basic lineage structure compliance."""
    events_file = Path("output/openlineage_events.json")
    assert events_file.exists(), "OpenLineage events file not found"
    
    with open(events_file, 'r') as f:
        events = [json.loads(line) for line in f if line.strip()]
    
    assert len(events) > 0, "No events found"
    
    # Validate required OpenLineage event structure
    required_keys = {"eventType", "eventTime", "run", "job", "inputs", "outputs"}
    for i, event in enumerate(events):
        missing_keys = required_keys - set(event.keys())
        assert not missing_keys, f"Event {i} missing keys: {missing_keys}"
    
    # Validate run ID consistency
    if len(events) > 1:
        first_run_id = events[0]["run"]["runId"]
        for event in events[1:]:
            assert event["run"]["runId"] == first_run_id, "Inconsistent runIds across events"


def test_column_lineage_validation():
    """Validates column lineage facet structure."""
    events_file = Path("output/openlineage_events.json")
    assert events_file.exists(), "OpenLineage events file not found"
    
    with open(events_file, 'r') as f:
        events = [json.loads(line) for line in f if line.strip()]
    
    # Look for column lineage facets
    column_lineage_events = [e for e in events if 'outputs' in e and
                           any('facets' in out and 'columnLineage' in out.get('facets', {})
                               for out in e['outputs'])]
    
    if len(column_lineage_events) > 0:
        for event in column_lineage_events:
            for output in event['outputs']:
                col_lineage = output.get('facets', {}).get('columnLineage', {})
                if col_lineage:
                    assert 'fields' in col_lineage, "Column lineage missing fields"
                    # Validate field structure
                    for field_name, field_info in col_lineage['fields'].items():
                        assert 'inputFields' in field_info, f"Field {field_name} missing inputFields"


def test_dbt_job_naming():
    """Validates dbt job naming conventions."""
    events_file = Path("output/openlineage_events.json")
    assert events_file.exists(), "OpenLineage events file not found"
    
    with open(events_file, 'r') as f:
        events = [json.loads(line) for line in f if line.strip()]
    
    job_names = set()
    for event in events:
        job_name = event.get("job", {}).get("name")
        if job_name:
            job_names.add(job_name)
    
    assert len(job_names) > 0, "No job names found in events"
    
    # Validate dbt job naming patterns
    dbt_jobs = [name for name in job_names if 'dbt' in name.lower() or '.' in name]
    assert len(dbt_jobs) > 0, f"No dbt-style job names found. Jobs: {sorted(job_names)}"