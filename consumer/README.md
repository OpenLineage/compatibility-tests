# Consumer tests

## Scenarios

Scenarios directory contains input events defined for use by any consumer to run tests. Each of the scenarios contains:

- directory with event files
- `maintainers.json` file with the list of people responsible for the scenario
- `scenario.md` file with the scenario description containing information about the events that would be useful for the
  consumer scenarios creator to know e.g. which producer created them, what are they representing etc.

## Consumers

Each directory represents a consumer and contains:

- `validator` directory with the validation logic (unlike producers where produced Openlineage events can be validated
  by generic component)
- `mapping.json` file with the mapping between Openlineage events and consumer API entities
- `maintainers.json` file with the list of people responsible for the component
- `scenarios` directory containing scenario directories with following structure:
    - `config.json` file with the scenario configuration
    - `scenario.md` file with description of the scenario
    - `maintainers.json` file with the list of people responsible for the scenario
    - `validation` directory with expected state of consumer API to validate against

#### config

config file contains the metadata of the tests

```json
{
  "tests": [
    {
      "name": "name",
      "path": "path/to/file.json",
      "entity": "entity",
      "tags": {
        "facets": [
          "list",
          "of",
          "supported",
          "facets"
        ],
        "producer": "producer"
      }
    }
  ]
}
```

Each entry in the config file represents a single test. `name`, `path` and `entity` are fields used to identify the
test. The `tags` field is used to specify the different kinds of tags `min_version`, `max_version` are filtering tags,
if the version of OpenLineage used in tests in outside of the range specified by these values, the test will be
skipped. `producer` and `facets` are tags used to define what part of OpenLineage compatibility is being tested i.e.
which facets are supported by the consumer and which producers events are consumable.

#### mapping file

mapping file contains the mapping between Openlineage events and consumer API entities. The structure of the file is as follows:

```json 
{
  "mapped": {
    "core": {
      "eventTime": "Consumer entity representing event time",
      "run.id": "Consumer entity ID",
      "job.name": "part of consumer entity name",
      "job.namespace": "part of consumer entity name",
      ...
    },
    "ExampleFacet": {
      "field1": "Consumer entity field",
      "field2": "Consumer entity field"  
    },
    ...
  },
  "knownUnmapped": {
    "ExampleUnmappedFacet": ["*"],
    ...
  }
}

```


