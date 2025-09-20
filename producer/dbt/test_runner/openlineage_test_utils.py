# Copyright 2018-2025 contributors to the OpenLineage project
# SPDX-License-Identifier: Apache-2.0
# Adapted from OpenLineage official test utilities

from typing import Any, Dict, List, Literal


def filter_events_by_job(events: List[Dict[str, Any]], job_name: str) -> List[Dict[str, Any]]:
    """Filter events by job name."""
    return [event for event in events if event.get("job", {}).get("name") == job_name]


def get_events_by_type(events: List[Dict[str, Any]], event_type: str) -> List[Dict[str, Any]]:
    """Get events by event type (START, COMPLETE, FAIL)."""
    return [event for event in events if event.get("eventType") == event_type]


def validate_lineage_chain(events: List[Dict[str, Any]], expected_models: List[str]) -> bool:
    """Validate that all expected models appear in the lineage chain."""
    job_names = set()
    for event in events:
        job_name = event.get("job", {}).get("name")
        if job_name:
            job_names.add(job_name)

    for model in expected_models:
        if model not in job_names:
            return False

    return True


def extract_dataset_names(event: Dict[str, Any], io_type: str) -> List[str]:
    """Extract dataset names from inputs or outputs."""
    datasets = event.get(io_type, [])
    return [dataset.get("name", "") for dataset in datasets]


def validate_event_ordering(events: List[Dict[str, Any]]) -> bool:
    """Validate that START events come before COMPLETE events for each job."""
    job_names = set(event.get("job", {}).get("name") for event in events)
    job_names.discard(None)
    
    for job_name in job_names:
        job_events = filter_events_by_job(events, job_name)
        start_events = get_events_by_type(job_events, "START")
        complete_events = get_events_by_type(job_events, "COMPLETE")
        
        if start_events and complete_events:
            start_time = start_events[0]["eventTime"]
            complete_time = complete_events[0]["eventTime"]
            
            if start_time >= complete_time:
                return False
    
    return True


def get_unique_models(events: List[Dict[str, Any]]) -> List[str]:
    """Get list of unique model names from events."""
    job_names = set()
    for event in events:
        job_name = event.get("job", {}).get("name")
        if job_name:
            job_names.add(job_name)
    return list(job_names)