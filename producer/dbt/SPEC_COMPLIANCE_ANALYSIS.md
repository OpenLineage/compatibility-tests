# OpenLineage Spec Compliance Analysis

## Current Test Configuration

### Implementation Under Test
- **dbt-openlineage version**: 1.37.0
- **dbt version**: 1.10.11
- **OpenLineage Python client**: 1.37.0

### Spec Version Analysis

#### Main Event Schema
```json
"schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"
```
**Testing against**: OpenLineage Specification **2-0-2**

#### Facet Schema Versions (Mixed!)
```json
// Job Type Facet
"_schemaURL": "https://openlineage.io/spec/facets/2-0-3/JobTypeJobFacet.json#/$defs/JobTypeJobFacet"

// Processing Engine Facet  
"_schemaURL": "https://openlineage.io/spec/facets/1-1-1/ProcessingEngineRunFacet.json#/$defs/ProcessingEngineRunFacet"

// Data Quality Assertions Facet
"_schemaURL": "https://openlineage.io/spec/facets/1-0-1/DataQualityAssertionsDatasetFacet.json#/$defs/DataQualityAssertionsDatasetFacet"
```

**⚠️ FINDING**: We have **mixed facet spec versions**:
- Main event: **2-0-2**
- Some facets: **2-0-3** 
- Some facets: **1-1-1**
- Some facets: **1-0-1**

## Spec Aspects Being Tested

### ✅ Core Event Structure (Spec 2-0-2)
- **eventTime**: ISO 8601 timestamp ✅
- **eventType**: START, COMPLETE, FAIL ✅  
- **producer**: Implementation identification ✅
- **schemaURL**: Spec version reference ✅
- **job**: Job identification and facets ✅
- **run**: Run identification and facets ✅
- **inputs/outputs**: Dataset lineage ✅

### ✅ Required Job Facets
- **jobType**: Integration type (DBT), job type (JOB/TEST), processing type (BATCH) ✅

### ✅ Required Run Facets  
- **dbt_version**: dbt version tracking ✅
- **dbt_run**: Invocation ID tracking ✅
- **processing_engine**: Engine name, version, adapter version ✅
- **parent**: Parent run relationships (for tests) ✅

### ✅ Dataset Facets
- **schema**: Table/view schema definitions ✅
- **dataSource**: Database connection information ✅  
- **columnLineage**: Column-level lineage relationships ✅
- **dataQualityAssertions**: Test results and assertions ✅

### ✅ dbt-Specific Features
- **dbt test events**: Data quality assertion results ✅
- **dbt model events**: Schema and SQL facets ✅
- **Parent/child relationships**: Test → run relationships ✅
- **Column lineage**: Column-level transformation tracking ✅

## Compliance Assessment

### ✅ Fully Compliant Areas
1. **Core event structure** follows OpenLineage 2-0-2 specification exactly
2. **Required fields** are all present and correctly formatted
3. **Event types** use standard START/COMPLETE/FAIL pattern
4. **Dataset lineage** properly represents input/output relationships
5. **dbt integration patterns** follow expected OpenLineage conventions

### ⚠️ Mixed Spec Version Concerns
1. **Facet versioning inconsistency**: Different facets reference different spec versions
2. **Forward compatibility**: Some facets use newer spec versions (2-0-3) than main event (2-0-2)
3. **Backward compatibility**: Some facets use older spec versions (1-1-1, 1-0-1)

### 🔍 Analysis Questions
1. **Is this intentional?** Mixed facet versioning might be by design for backward compatibility
2. **Is this spec-compliant?** Does OpenLineage 2-0-2 allow facets from other spec versions?
3. **Should we validate against multiple specs?** Different facets might need different validation

## Validation Scope

### What We ARE Testing
- ✅ **Event structure compliance** against OpenLineage 2-0-2
- ✅ **Required field presence** and format validation
- ✅ **dbt-specific facet content** and structure
- ✅ **Dataset lineage relationships** accuracy
- ✅ **Column-level lineage** tracking
- ✅ **Data quality assertion** reporting

### What We Are NOT Testing  
- ❌ **Cross-spec version compatibility** (mixed facet versions)
- ❌ **Facet schema validation** (each facet against its own spec version)
- ❌ **Implementation version matrix** (different dbt-ol versions)
- ❌ **Backward compatibility** (events against older spec versions)
- ❌ **Forward compatibility** (events against newer spec versions)

## Recommendations

### 1. Clarify Mixed Spec Versioning
- Research whether mixed facet spec versions are intentional/allowed
- Document the versioning strategy in OpenLineage ecosystem
- Determine if this requires separate validation per facet type

### 2. Expand Validation Scope  
- Add facet-specific schema validation
- Test against multiple spec versions systematically
- Document compatibility boundaries clearly

### 3. Document Current Limitations
- Be explicit about what aspects of spec compliance we validate
- Acknowledge mixed versioning in current implementation
- Set expectations for future enhancements

## Current Test Confidence Level

**HIGH CONFIDENCE**: Core OpenLineage 2-0-2 event structure compliance  
**MEDIUM CONFIDENCE**: dbt-specific facet compliance (mixed spec versions)  
**LOW CONFIDENCE**: Complete spec compliance across all facet versions

## Summary

We are **primarily testing against OpenLineage Specification 2-0-2** using **dbt-openlineage 1.37.0**, but with **mixed facet spec versions** that span from 1-0-1 to 2-0-3. This requires further investigation to determine if this is expected behavior or a validation gap.