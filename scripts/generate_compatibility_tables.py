import argparse
import json
from pathlib import Path

from report import Report
from py_markdown_table.markdown_table import markdown_table


def get_arguments():
    parser = argparse.ArgumentParser(description="Generate Markdown reports from lineage summary.")
    parser.add_argument('--report', type=str, required=True, help="Path to JSON report file")
    parser.add_argument('--target', type=str, required=True, help="Output directory for markdown files")
    args = parser.parse_args()
    return Path(args.report), Path(args.target)


def sanitize_filename(name):
    return name.replace(" ", "_").replace("/", "_")


def sanitize_version(version):
    return version.replace(" ", "_").replace("/", "_").replace(".", "_")


def ensure_output_dir(path: Path):
    if path.exists() and not path.is_dir():
        raise ValueError(f"Target path '{path}' exists but is not a directory.")
    path.mkdir(parents=True, exist_ok=True)


def write_component_version_file(output_dir, component_name, version, content_parts):
    suffix = "" if version == "" else f"_{sanitize_version(version)}"
    filename = f"{sanitize_filename(component_name)}{suffix}.md"
    full_path = output_dir / filename

    with open(full_path, "w") as f:
        f.write(f"# Report for {component_name} {version}\n\n")
        for title, content in content_parts:
            f.write(f"## {title}\n{content}\n\n")

    print(f"Written: {full_path}")


def get_sorted_facets(data):
    f = [f for v in data.component_versions.values() for vv in v.values() for f in vv.get('facets', [])]
    facets = set(f)
    desired_order = ["run_event", "jobType", "parent", "dataSource", "processing_engine", "sql", "symlinks",
                     "schema", "columnLineage", "gcp_dataproc_spark", "gcp_lineage", "spark_properties"]
    sorted_in_order = sorted([item for item in facets if item in desired_order], key=desired_order.index)
    sorted_out_of_order = sorted(item for item in facets if item not in desired_order)
    return sorted_in_order + sorted_out_of_order


def fill_facet_table(d, facets):
    table_data = []
    for key, value in d.items():
        row = {'openlineage version': key}
        for facet in facets:
            row[facet] = '+' if 'facets' in value and facet in value['facets'] else '-'
        table_data.append(row)
    table = markdown_table(table_data)
    table.set_params(row_sep="markdown", quote=False)
    return table.get_markdown()


def generate_consumer_facets_table(data):
    facets = get_sorted_facets(data)
    return {k: fill_facet_table(v, facets) for k, v in data.component_versions.items()}


def generate_producer_facets_table(data):
    facets = get_sorted_facets(data)
    return {k: fill_facet_table(v, facets) for k, v in data.component_versions.items()}


def fill_inputs_table(d):
    table_data = []
    for value in d.values():
        if 'inputs' in value:
            for producer in value['inputs']:
                if producer:
                    table_data.append({'Producer': producer, 'Status': '+'})
    if table_data:
        table = markdown_table(table_data)
        table.set_params(row_sep="markdown", quote=False)
        return table.get_markdown()
    return None


def generate_producers_table(data):
    return {k: vv for k, v in data.component_versions.items() if (vv := fill_inputs_table(v)) is not None}


def fill_lineage_level_table(d):
    table_data = []
    for value in d.values():
        if 'lineage_levels' in value:
            for datasource, levels in value['lineage_levels'].items():
                row = {'Datasource': datasource}
                for level in ['dataset', 'column', 'transformation']:
                    row[level.capitalize()] = '+' if level in levels else '-'
                table_data.append(row)
    if table_data:
        table = markdown_table(table_data)
        table.set_params(row_sep="markdown", quote=False)
        return table.get_markdown()
    return None


def generate_lineage_table(data):
    return {k: fill_lineage_level_table(v) for k, v in data.component_versions.items()}


def generate_facets_by_openlineage_version_table(summaries):
    data_by_version = {}
    for summary in summaries:
        component_base_name = str(summary.name) or "<Unnamed>"
        for comp_version, ol_versions in summary.component_versions.items():
            for ol_version, values in ol_versions.items():
                if 'facets' not in values:
                    continue
                full_component_name = f"{component_base_name} ({comp_version})" if comp_version else component_base_name
                data_by_version.setdefault(ol_version, {}).setdefault(full_component_name, set()).update(values['facets'])

    all_facets = {facet for components in data_by_version.values() for facets in components.values() for facet in facets}
    facet_list = get_sorted_facets_from_set(all_facets)

    result = {}
    for ol_version, components in data_by_version.items():
        table_data = []
        for component_name, component_facets in components.items():
            row = {"Component (Version)": component_name}
            for facet in facet_list:
                row[facet] = '+' if facet in component_facets else '-'
            table_data.append(row)
        table = markdown_table(table_data)
        table.set_params(row_sep="markdown", quote=False)
        result[ol_version] = table.get_markdown()
    return result


def get_sorted_facets_from_set(facets):
    desired_order = ["run_event", "jobType", "parent", "dataSource", "processing_engine", "sql", "symlinks",
                     "schema", "columnLineage", "gcp_dataproc_spark", "gcp_lineage", "spark_properties"]
    sorted_in_order = sorted([item for item in facets if item in desired_order], key=desired_order.index)
    sorted_out_of_order = sorted(item for item in facets if item not in desired_order)
    return sorted_in_order + sorted_out_of_order


def process_consumers(consumer_tag_summary, output_dir):
    for s in consumer_tag_summary:
        consumer_facets = generate_consumer_facets_table(s)
        producer_inputs = generate_producers_table(s)
        for version, facets_table in consumer_facets.items():
            parts = []
            if facets_table:
                parts.append(("Consumer Facets", facets_table))
            if version in producer_inputs and producer_inputs[version]:
                parts.append(("Producer Inputs", producer_inputs[version]))
            if parts:
                write_component_version_file(output_dir, s.name, version, parts)


def process_producers(producer_tag_summary, output_dir):
    for s in producer_tag_summary:
        lineage_tables = generate_lineage_table(s)
        producer_facets = generate_producer_facets_table(s)
        all_versions = set(lineage_tables.keys()).union(producer_facets.keys())
        for version in all_versions:
            parts = []
            if version in lineage_tables and lineage_tables[version]:
                parts.append(("Lineage Levels", lineage_tables[version]))
            if version in producer_facets and producer_facets[version]:
                parts.append(("Producer Facets", producer_facets[version]))
            if parts:
                write_component_version_file(output_dir, s.name, version, parts)


def write_version_summaries(consumer_summary, producer_summary, output_dir):
    consumer_by_version = generate_facets_by_openlineage_version_table(consumer_summary)
    producer_by_version = generate_facets_by_openlineage_version_table(producer_summary)

    for version, table in consumer_by_version.items():
        filename = output_dir / f"openlineage_{sanitize_version(version)}_consumer.md"
        with open(filename, "w") as f:
            f.write(f"# Consumer Facets Summary for OpenLineage Version {version}\n\n{table}\n")
        print(f"Written: {filename}")

    for version, table in producer_by_version.items():
        filename = output_dir / f"openlineage_{sanitize_version(version)}_producer.md"
        with open(filename, "w") as f:
            f.write(f"# Producer Facets Summary for OpenLineage Version {version}\n\n{table}\n")
        print(f"Written: {filename}")


def main():
    report_path, target_path = get_arguments()
    ensure_output_dir(target_path)

    with open(report_path, 'r') as f:
        report = Report.from_dict(json.load(f))

    consumer_summary = report.get_consumer_tag_summary()
    producer_summary = report.get_producer_tag_summary()

    process_consumers(consumer_summary, target_path)
    process_producers(producer_summary, target_path)
    write_version_summaries(consumer_summary, producer_summary, target_path)


if __name__ == "__main__":
    main()