# Multi-Spec OpenLineage Compatibility Testing

## Overview

The dbt producer compatibility test now supports **multi-specification testing** to validate compatibility across different OpenLineage spec versions.

## Key Features

### ✅ Spec-Version-Aware Event Storage
```bash
# Each spec version gets its own event file and directory
output/
├── spec_2-0-2/
│   └── openlineage_events_2-0-2.jsonl     # Events for spec 2-0-2
├── spec_2-0-1/
│   └── openlineage_events_2-0-1.jsonl     # Events for spec 2-0-1
└── spec_1-1-1/
    └── openlineage_events_1-1-1.jsonl     # Events for spec 1-1-1
```

### ✅ Spec-Version-Aware Reports
```bash
# Each spec version gets its own validation report
output/
├── dbt_producer_report_2-0-2.json
├── dbt_producer_report_2-0-1.json
└── dbt_producer_report_1-1-1.json
```

## Usage

### Single Spec Version Testing
```bash
# Test against specific OpenLineage spec version
./run_dbt_tests.sh \
  --openlineage-directory /path/to/openlineage \
  --openlineage-release 2-0-2

# Results:
# - Events: output/spec_2-0-2/openlineage_events_2-0-2.jsonl
# - Report: output/dbt_producer_report_2-0-2.json
```

### Multi-Spec Version Testing
```bash
# Test against multiple OpenLineage spec versions
./run_multi_spec_tests.sh \
  --openlineage-directory /path/to/openlineage \
  --spec-versions 2-0-2,2-0-1,1-1-1

# Results:
# - Events: output/spec_{version}/openlineage_events_{version}.jsonl
# - Reports: output/dbt_producer_report_{version}.json
```

## Implementation vs Specification Testing Matrix

### ✅ Currently Supported (Multi-Spec Schema Validation)
| Implementation | Specification | Status |
|----------------|---------------|---------|
| dbt-ol 1.37.0  | 2-0-2        | ✅ Tested |
| dbt-ol 1.37.0  | 2-0-1        | ✅ Tested |
| dbt-ol 1.37.0  | 1-1-1        | ✅ Tested |

**Tests:** Forward/backward compatibility of current implementation against different OpenLineage spec schema versions.

### 🔮 Future Enhancement: Multi-Implementation Testing
| Implementation | Specification | Status |
|----------------|---------------|---------|
| dbt-ol 1.36.0  | 2-0-2        | 🔮 Future feature |
| dbt-ol 1.36.0  | 2-0-1        | 🔮 Future feature |
| dbt-ol 1.35.0  | 2-0-2        | 🔮 Future feature |

**Would Test:** Different implementation versions against different specification versions (N×M matrix).

## Compatibility Validation

### Forward Compatibility Testing
```bash
# New implementation vs older specification
dbt-ol 1.37.0 → OpenLineage spec 2-0-1  ✅ Tested
dbt-ol 1.37.0 → OpenLineage spec 1-1-1  ✅ Tested
```

### Cross-Version Event Analysis
```bash
# Compare events across spec versions
diff output/spec_2-0-2/openlineage_events_2-0-2.jsonl \
     output/spec_2-0-1/openlineage_events_2-0-1.jsonl

# Analyze schema differences
jq -r '.schemaURL' output/spec_2-0-2/openlineage_events_2-0-2.jsonl | head -1
# Expected: https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent

jq -r '.schemaURL' output/spec_2-0-1/openlineage_events_2-0-1.jsonl | head -1  
# Expected: https://openlineage.io/spec/2-0-1/OpenLineage.json#/$defs/RunEvent
```

## Event File Structure

### Spec-Specific Event Content
```json
{
  "eventTime": "2025-09-21T12:00:00Z",
  "eventType": "START",
  "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent",
  "producer": "https://github.com/OpenLineage/OpenLineage/tree/1.37.0/integration/dbt",
  "run": {
    "runId": "...",
    "facets": {
      "dbt_version": {
        "_schemaURL": "https://openlineage.io/spec/facets/2-0-2/...",
        "version": "1.10.11"
      }
    }
  },
  "job": { ... },
  "inputs": [ ... ],
  "outputs": [ ... ]
}
```

## Framework Enhancement Roadmap

### Phase 1: Multi-Spec Schema Validation ✅ COMPLETE
- [x] Spec-version-aware event files
- [x] Spec-version-aware reports  
- [x] Multi-spec test runner
- [x] Clear spec version identification
- [x] Forward/backward compatibility testing (same implementation, different schemas)

### Phase 2: Multi-Implementation Support 🔮 FUTURE ENHANCEMENT
- [ ] Multiple dbt-ol version management
- [ ] Virtual environment per implementation version
- [ ] Complete N×M matrix testing (implementations × specifications)
- [ ] Backward compatibility testing (old implementation vs new spec)
- [ ] **Estimated effort: 30-50 hours** (research + infrastructure + tooling)

### Phase 3: Advanced Analysis 🔮 FUTURE ENHANCEMENT
- [ ] Cross-spec event comparison analysis
- [ ] Breaking change detection between spec versions
- [ ] Compatibility regression detection
- [ ] Production upgrade guidance

## Benefits

### ✅ Clear Spec Version Identification
- No more mixed events from different spec versions
- Clear traceability of which spec was tested
- Separate validation results per spec version

### ✅ Forward/Backward Compatibility Testing
- Test current implementation against multiple spec versions
- Identify spec version compatibility boundaries
- Validate upgrade/downgrade scenarios

### ✅ Foundation for Future Enhancements
- Framework ready for multi-implementation support (Phase 2)
- Clear extension path for N×M matrix testing
- Structured approach to compatibility validation

## Current Scope & Limitations

### ✅ What This Provides
- **Multi-spec schema validation**: Same implementation, different OpenLineage spec schemas
- **Forward compatibility**: Can current implementation generate spec 1-1-1 compliant events?
- **Backward compatibility**: Does current implementation work with older validation schemas?
- **Clear separation**: Spec-version-specific event files and reports

### 🔮 What This Doesn't Provide (Future Enhancements)
- **Multi-implementation testing**: Different dbt-ol versions with different specs
- **Version matrix**: N×M combinations of implementations and specifications
- **Virtual environment management**: Isolated testing of different library versions

## Example Output

```bash
$ ./run_multi_spec_tests.sh --openlineage-directory /path/to/openlineage

🧪 TESTING AGAINST SPEC VERSION: 2-0-2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ PASSED: Spec version 2-0-2

🧪 TESTING AGAINST SPEC VERSION: 2-0-1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ PASSED: Spec version 2-0-1

🧪 TESTING AGAINST SPEC VERSION: 1-1-1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ PASSED: Spec version 1-1-1

===============================================================================
                       MULTI-SPEC TEST SUMMARY                               
===============================================================================
Total spec versions tested: 3
Passed spec versions: 3
Failed spec versions: 0

📁 Results by spec version:
  📋 Spec 2-0-2: 24 events → output/spec_2-0-2/openlineage_events_2-0-2.jsonl
  📊 Spec 2-0-2: Report → output/dbt_producer_report_2-0-2.json
  📋 Spec 2-0-1: 24 events → output/spec_2-0-1/openlineage_events_2-0-1.jsonl
  📊 Spec 2-0-1: Report → output/dbt_producer_report_2-0-1.json
  📋 Spec 1-1-1: 24 events → output/spec_1-1-1/openlineage_events_1-1-1.jsonl
  📊 Spec 1-1-1: Report → output/dbt_producer_report_1-1-1.json
===============================================================================
🎉 ALL SPEC VERSIONS PASSED!
```