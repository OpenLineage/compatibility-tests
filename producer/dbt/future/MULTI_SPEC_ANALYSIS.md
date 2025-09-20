# Cross-Version Compatibility Testing Analysis

## Problem Statement

OpenLineage has two distinct version numbers that are currently treated as locked together:
1. **Implementation Version** (e.g., 1.23.0, 1.30.0) - The code in openlineage-dbt package
2. **Specification Version** (e.g., 2-0-2, 2-0-1) - The JSON schema for event validation

Current testing locks these together, preventing validation of critical compatibility scenarios.

## Critical Distinction

### Implementation Version vs Specification Version
```bash
# Implementation Version (Git Tag / PyPI Package Version)
# File: integration/dbt/setup.py
__version__ = "1.30.0"  # The openlineage-dbt code version

# Specification Version (Schema $id in JSON)
# File: spec/OpenLineage.json (in same git tag)
"$id": "https://openlineage.io/spec/2-0-2/OpenLineage.json"  # The schema version
```

**Key Finding**: Multiple implementation versions can bundle the same specification:
- Implementation 1.23.0 → bundles spec 2-0-2
- Implementation 1.30.0 → bundles spec 2-0-2 (same spec!)
- Implementation 1.37.0 → bundles spec 2-0-2 (same spec!)

## Current Framework Analysis

### What CI/CD Framework Does Today
```yaml
# .github/workflows/producer_dbt.yml
pip install openlineage-dbt==${{ inputs.ol_release }}        # Implementation version
release_tags: ${{ inputs.ol_release }}                       # Spec version (SAME VALUE)
```

**Result**: Implementation version X is ONLY validated against spec from tag X.
- Install 1.30.0 → validate against spec from 1.30.0 (which is spec 2-0-2)
- Install 1.37.0 → validate against spec from 1.37.0 (which is also spec 2-0-2)

### Locked Version Testing
```bash
# Current testing: Implementation and spec versions are LOCKED
matrix:
  openlineage_versions: ["1.23.0", "1.30.0"]
  
# Results in:
# Test 1: Install 1.23.0 → validate against spec from tag 1.23.0
# Test 2: Install 1.30.0 → validate against spec from tag 1.30.0
```

### Framework Capability (Currently Unused)
The validation action DOES accept separate parameters:
```yaml
# .github/actions/run_event_validation/action.yml
inputs:
  ol_release: "1.30.0"           # Could be different
  release_tags: "1.37.0"         # Could be different!
```

**The framework CAN test cross-version scenarios but doesn't currently use this capability.**

### Current Limitations
- **No cross-version testing**: Implementation 1.30.0 never validated against spec from 1.37.0
- **Unknown forward compatibility**: Does old implementation work with newer specs?
- **Unknown backward compatibility**: Does new implementation work with older specs?
- **No version mapping documentation**: Which implementations bundle which specs?
- **Missed compatibility insights**: Can't detect breaking changes across versions

### Example of Missing Coverage
```json
// What we test today (locked versions):
{
  "producer": "...tree/1.30.0/integration/dbt",     // Implementation 1.30.0
  "schemaURL": "...spec/2-0-2/OpenLineage.json"     // Spec from 1.30.0 (which is 2-0-2)
}

// What we DON'T test (cross-version scenarios):
{
  "producer": "...tree/1.30.0/integration/dbt",     // Implementation 1.30.0
  "schemaURL": "...spec/2-0-2/OpenLineage.json"     // Spec from 1.37.0 (also 2-0-2, but potentially different!)
}
```

## Proposed Cross-Version Compatibility Testing 

### Cross-Version Testing Approach
```bash
# Test EVERY combination of implementation × specification

# Forward Compatibility Testing:
# Old implementation → newer spec (will old code work with new validators?)
Implementation 1.30.0 → validate against spec from tag 1.37.0
Implementation 1.23.0 → validate against spec from tag 1.37.0

# Backward Compatibility Testing:
# New implementation → older spec (will new code work with old validators?)
Implementation 1.37.0 → validate against spec from tag 1.30.0
Implementation 1.37.0 → validate against spec from tag 1.23.0

# Native Testing (what we do today):
Implementation 1.30.0 → validate against spec from tag 1.30.0
```

### Cross-Version Testing Benefits
- **Forward compatibility validation**: Ensure old implementations don't break with new specs
- **Backward compatibility validation**: Ensure new implementations maintain compatibility
- **Comprehensive compatibility matrix**: Document which versions work together
- **Breaking change detection**: Identify when spec changes break implementations
- **Upgrade planning**: Help users understand version upgrade paths
- **Framework utilization**: Leverage existing CI/CD capability (`ol_release` ≠ `release_tags`)

### Cross-Version Testing Output Example
```json
// Test 1: Implementation 1.30.0 against its native spec (Current behavior)
{
  "producer": "...tree/1.30.0/integration/dbt",
  "schemaURL": "...spec/2-0-2/OpenLineage.json"  // From tag 1.30.0
}
// Result: ✅ PASS (expected)

// Test 2: Implementation 1.30.0 against newer spec (Forward compatibility)
{
  "producer": "...tree/1.30.0/integration/dbt",
  "schemaURL": "...spec/2-0-2/OpenLineage.json"  // From tag 1.37.0
}
// Result: ✅ PASS or ❌ FAIL? (Currently unknown!)

// Test 3: Implementation 1.37.0 against older spec (Backward compatibility)
{
  "producer": "...tree/1.37.0/integration/dbt",
  "schemaURL": "...spec/2-0-2/OpenLineage.json"  // From tag 1.30.0
}
// Result: ✅ PASS or ❌ FAIL? (Currently unknown!)
```

## Implementation Requirements

### 1. Version Mapping Research (Critical First Step)
```bash
# Document which implementation versions bundle which specification versions
# This mapping is essential for understanding compatibility relationships

# Research needed: Check each git tag
Implementation 1.37.0 → Spec version?  # Check spec/OpenLineage.json $id
Implementation 1.30.0 → Spec version?  # Check spec/OpenLineage.json $id
Implementation 1.23.0 → Spec version?  # Check spec/OpenLineage.json $id

# Initial findings:
# Tag 1.23.0 → spec 2-0-2
# Tag 1.30.0 → spec 2-0-2 (SAME SPEC as 1.23.0!)
# Tag 1.37.0 → spec 2-0-2 (SAME SPEC as 1.30.0!)
```

### 2. Framework Configuration Enhancement
```yaml
# Enable cross-version testing in CI/CD
# Option A: Add to versions.json
{
  "openlineage_versions": ["1.23.0", "1.30.0", "1.37.0"],
  "spec_versions_to_test": ["1.23.0", "1.30.0", "1.37.0"],  # NEW
  "component_version": ["1.8.0"]
}

# Option B: Matrix expansion in workflow
strategy:
  matrix:
    implementation: ["1.30.0", "1.37.0"]
    spec_tag: ["1.23.0", "1.30.0", "1.37.0"]  # Cross-product testing
```

### 3. Comprehensive Compatibility Matrix
| Implementation | Native Spec | Spec from 1.23.0 | Spec from 1.30.0 | Spec from 1.37.0 |
|----------------|-------------|------------------|------------------|------------------|
| 1.37.0         | 2-0-2       | ✅ Backward?     | ✅ Backward?     | ✅ Native        |
| 1.30.0         | 2-0-2       | ✅ Backward?     | ✅ Native        | ✅ Forward?      |
| 1.23.0         | 2-0-2       | ✅ Native        | ✅ Forward?      | ✅ Forward?      |

**Note**: Even though all bundle spec 2-0-2, the spec files may have evolved between tags!

## Implementation Path Forward

### 1. Version Mapping Research (Critical First Step)
```bash
# Document which implementation versions bundle which specification versions
# This is foundational for understanding compatibility relationships

# For each OpenLineage release tag:
git checkout <tag>
cat spec/OpenLineage.json | jq -r '."$id"'  # Extract spec version
cat integration/dbt/setup.py | grep __version__  # Extract implementation version

# Build comprehensive mapping table:
# Implementation 1.23.0 → Spec 2-0-2
# Implementation 1.30.0 → Spec 2-0-2
# Implementation 1.37.0 → Spec 2-0-2
```

### 2. Framework Configuration Prototype
```yaml
# Modify workflow to enable cross-version testing
# Using existing framework capability (separate parameters):

jobs:
  cross-version-test:
    strategy:
      matrix:
        implementation: ["1.30.0", "1.37.0"]
        spec_tag: ["1.23.0", "1.30.0", "1.37.0"]
    steps:
      - name: Install implementation
        run: pip install openlineage-dbt==${{ matrix.implementation }}
      
      - name: Validate against spec
        uses: ./.github/actions/run_event_validation
        with:
          ol_release: ${{ matrix.implementation }}      # Implementation version
          release_tags: ${{ matrix.spec_tag }}           # Spec version (DIFFERENT!)
```

### 3. Compatibility Analysis
Once cross-version testing is implemented, analyze results to:
- Identify breaking changes between spec versions
- Document forward/backward compatibility boundaries
- Guide users on safe upgrade paths
- Detect when spec evolution breaks older implementations

## Analysis Summary

The OpenLineage compatibility testing framework currently locks implementation and specification versions together, preventing validation of critical cross-version compatibility scenarios.

### Key Findings

1. **Two Distinct Version Numbers**:
   - Implementation version (e.g., 1.30.0) - The openlineage-dbt code
   - Specification version (e.g., 2-0-2) - The JSON schema
   - Currently locked together in testing

2. **Framework Capability Exists But Unused**:
   - Validation action accepts separate `ol_release` and `release_tags` parameters
   - Could enable cross-version testing with minimal changes
   - Currently both parameters set to same value

3. **Multiple Implementations Can Share Same Spec**:
   - Implementation 1.23.0, 1.30.0, 1.37.0 all bundle spec 2-0-2
   - But spec files may have evolved between tags
   - Need to test these cross-version scenarios

### Proposed Enhancement

This analysis proposes cross-version compatibility testing that would:

1. **Version Mapping Research**: Document implementation→spec relationships across all releases
2. **Cross-Version Testing**: Test implementation X against spec Y (where X ≠ Y)
3. **Compatibility Matrix**: Comprehensive N×M matrix of compatibility results
4. **Framework Integration**: Leverage existing CI/CD capability (separate `ol_release` and `release_tags`)

### Expected Outcome

**Systematic cross-version compatibility testing** that validates:
- Forward compatibility (old implementations with new specs)
- Backward compatibility (new implementations with old specs)
- Breaking change detection across version boundaries
- Clear documentation of version compatibility for users

### Community Discussion Value

This proposal is valuable for OpenLineage TSC discussions about:
- Whether cross-version compatibility testing should be a community standard
- How to document and communicate compatibility boundaries
- Balance between testing comprehensiveness and CI/CD resource usage
- User guidance for version upgrade planning