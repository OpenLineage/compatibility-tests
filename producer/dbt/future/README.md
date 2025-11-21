# Future Enhancements for dbt Producer Compatibility Testing

This directory contains **design documents** for enhanced compatibility testing capabilities.

## 🚧 Status: Design Phase

⚠️ **Important**: These are design documents for community discussion, not implemented features.

**Purpose**: Document future enhancement possibilities relevant to OpenLineage TSC discussions about:
- Cross-version compatibility testing (implementation version X against specification version Y)
- Comprehensive compatibility matrix validation
- Forward/backward compatibility requirements

## Critical Distinction: Implementation vs Specification Versions

### Implementation Version (Git Tag)
- Version of the openlineage-dbt Python package (e.g., 1.23.0, 1.30.0, 1.37.0)
- The **code** that implements the OpenLineage integration
- What gets installed: `pip install openlineage-dbt==1.30.0`
- Found in: `integration/dbt/setup.py` (`__version__ = "1.30.0"`)

### Specification Version (Schema Version)
- Version of the OpenLineage JSON schema (e.g., 2-0-2, 2-0-1, 1-1-1)
- The **event structure** that validators check against
- Found in: `spec/OpenLineage.json` (`"$id": "https://openlineage.io/spec/2-0-2/OpenLineage.json"`)
- Multiple implementation versions may bundle the same spec version

### Example: Version Relationship
```
Git Tag 1.23.0 (implementation) → bundles spec 2-0-2
Git Tag 1.30.0 (implementation) → bundles spec 2-0-2 (same spec!)
```

**Key Insight**: Implementation and specification versions are **conceptually different** but currently **locked together** in testing.

## Current Framework Capability Analysis

### What CI/CD Framework Already Does
The framework in `.github/workflows/producer_dbt.yml` + `versions.json` supports:
- ✅ **Multi-implementation testing**: Different implementation versions via matrix strategy
- ✅ **Per-version validation**: Each implementation validated against its bundled spec
- ⚠️ **Locked version testing**: Implementation version X → validated against spec from X

Example from workflow:
```yaml
pip install openlineage-dbt==${{ inputs.ol_release }}  # Implementation version
release_tags: ${{ inputs.ol_release }}                 # Spec version (same!)
```

### What Framework COULD Do (But Doesn't)
The validation action accepts separate parameters:
- `ol_release`: Implementation version to install
- `release_tags`: Spec version(s) to validate against

Could test: Implementation 1.30.0 against spec 2-0-2 from tag 1.37.0

## Future Enhancement: Cross-Version Compatibility Testing

### What It Would Provide
- Test implementation version X against specification version Y (where X ≠ Y)
- Forward compatibility: Old implementation (1.30.0) → newer spec (from 1.37.0)
- Backward compatibility: New implementation (1.37.0) → older spec (from 1.30.0)
- Comprehensive N×M compatibility matrix documentation
- Systematic validation of cross-version scenarios

### Why This Matters
- Spec versions evolve independently from implementation releases
- Multiple implementations may bundle the same spec (e.g., 1.23.0 and 1.30.0 both have spec 2-0-2)
- Need to verify: Does implementation X produce events valid against spec Y?
- Users need guidance on version upgrade paths and compatibility boundaries

### Implementation Approach
See `MULTI_SPEC_ANALYSIS.md` for detailed analysis of:
- Current framework limitations (locked version testing)
- Proposed cross-version testing scenarios
- Version mapping research requirements
- Example compatibility matrix

**Estimated Implementation Effort:** 4-8 hours
**Key Requirement**: Research and document implementation→spec version mappings

## Future Enhancement: Automated Cross-Version Matrix Testing

### What It Would Provide
- Automated testing of all implementation × specification combinations
- Virtual environment management per implementation version
- Complete N×M compatibility matrix with clear pass/fail results
- Integration with existing CI/CD framework via enhanced versions.json

### Example Compatibility Matrix
| Implementation | Spec 2-0-2 (1.37.0) | Spec 2-0-2 (1.30.0) | Spec 2-0-1 |
|----------------|---------------------|---------------------|------------|
| 1.37.0         | ✅ Native          | ✅ Compatible       | ✅ Backward|
| 1.30.0         | ✅ Forward         | ✅ Native          | ❓ Unknown |
| 1.23.0         | ✅ Forward         | ✅ Forward         | ❓ Unknown |

### Implementation Details
See `MULTI_SPEC_ANALYSIS.md` for comprehensive analysis including:
- Framework configuration options for cross-version matrix
- Virtual environment management considerations
- Compatibility matrix structure and interpretation

**Estimated Implementation Effort:** 30-50 hours
**Prerequisite**: Version mapping research (which implementations bundle which specs)

## Current Production Feature

The current production-ready dbt producer compatibility test is in the parent directory:
- `../run_dbt_tests.sh` - Single-spec dbt compatibility test (OpenLineage 2-0-2)
- `../README.md` - Production documentation and specification coverage analysis

## TSC Discussion Value

These designs address key questions relevant to OpenLineage community discussions:

1. **Implementation vs Specification Versioning**: 
   - Current testing locks implementation and spec versions together
   - Should we test cross-version compatibility (implementation X against spec Y)?
   - How do we document which implementations bundle which specs?

2. **Compatibility Requirements**: 
   - Forward compatibility: Will old implementations work with new specs?
   - Backward compatibility: Will new implementations work with old specs?
   - What constitutes "adequate" compatibility across version boundaries?

3. **Testing Standards**: 
   - Should the community require systematic cross-version validation?
   - How comprehensive should compatibility matrices be?
   - What combinations are critical vs. nice-to-have?

4. **Framework Enhancement**: 
   - Current CI/CD framework CAN support cross-version testing via separate `ol_release` and `release_tags`
   - Not currently utilized (both parameters set to same value)
   - Could enable this capability with minimal framework changes

The prototype code and analysis documents provide concrete examples for these architectural discussions.

## Implementation Priority

1. **High Priority**: Version mapping research (document implementation→spec relationships)
2. **Medium Priority**: Cross-version compatibility testing (leverage existing framework capability)
3. **Lower Priority**: Automated N×M matrix testing (requires comprehensive research)

These enhancements would extend the existing framework without breaking current functionality.