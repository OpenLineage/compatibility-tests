# Future Enhancements for dbt Producer Compatibility Testing

This directory contains **future enhancement designs** for the dbt producer compatibility test framework.

## Current Status: Design Phase Only

⚠️ **These are design documents and prototypes, not production-ready features.**

## Future Enhancement: Multi-Spec Testing

### What It Would Provide
- Test same implementation against multiple OpenLineage spec versions
- Forward/backward compatibility validation
- Spec-version-aware event files and reports

### Files
- `run_multi_spec_tests.sh` - Multi-spec test runner (prototype)
- `MULTI_SPEC_TESTING.md` - Design document and usage guide

**Estimated Implementation Effort:** 4-8 hours

## Future Enhancement: Multi-Implementation Testing  

### What It Would Provide
- Test different dbt-openlineage versions against different specs
- Virtual environment management per implementation
- Complete N×M compatibility matrix

### Files
- `run_true_multi_spec_tests.sh` - Multi-implementation test runner (prototype)
- `MULTI_SPEC_ANALYSIS.md` - Analysis of implementation vs specification testing

**Estimated Implementation Effort:** 30-50 hours

## Current Production Feature

The current production-ready dbt producer compatibility test is in the parent directory:
- `../run_dbt_tests.sh` - Single-spec dbt compatibility test
- `../README.md` - Production documentation

## Implementation Priority

1. **High Priority:** Multi-spec testing (same implementation, different specs)
2. **Lower Priority:** Multi-implementation testing (different versions, requires research)

These enhancements would extend the existing framework without breaking current functionality.