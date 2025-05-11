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

def get_sorted_facets(summary):
    f = [f for v in summary.component_versions.values() for vv in v.values() for f in vv.get('facets', [])]
    facets = set(f)
    desired_order = ["run_event", "jobType", "parent", "dataSource", "processing_engine", "sql", "symlinks",
                     "schema", "columnLineage", "gcp_dataproc_spark", "gcp_lineage", "spark_properties"]
    sorted_in_order = sorted([item for item in facets if item in desired_order], key=desired_order.index)
    sorted_out_of_order = sorted(item for item in facets if item not in desired_order)
    return sorted_in_order + sorted_out_of_order


def sanitize(name):
    return name.replace(" ", "_").replace("/", "_").replace(".", "_")


def normalize_label(name: str) -> str:
    return " ".join(word.capitalize() for word in name.replace("_", " ").split())


def write_category_json(path: Path, label: str, position: int):
    path.mkdir(parents=True, exist_ok=True)
    content = {
        "label": label,
        "position": position
    }
    with open(path / "_category_.json", "w") as f:
        json.dump(content, f, indent=2)


def write_markdown(path: Path, filename: str, label: str, content_parts, position: int = 1):
    path.mkdir(parents=True, exist_ok=True)
    full_file = path / f"{filename}.md"
    with open(full_file, "w") as f:
        f.write(f"---\nsidebar_position: {position}\ntitle: {label}\n---\n\n")
        for section_title, content in content_parts:
            f.write(f"## {section_title}\n{content}\n\n")
    print(f"Written: {full_file}")


def fill_facet_table(d, facets):
    table_data = []
    for key in sorted(d.keys(), key=lambda x: tuple(map(int, x.split(".")))):
        value = d[key]
        row = {'openlineage version': key}
        for facet in facets:
            row[facet] = '+' if 'facets' in value and facet in value['facets'] else '-'
        table_data.append(row)
    table = markdown_table(table_data)
    table.set_params(row_sep="markdown", quote=False)
    return table.get_markdown()


def fill_inputs_table(d):
    table_data = []
    seen = set()
    for value in d.values():
        for producer in value.get('inputs', []):
            if producer:
                normalized = normalize_label(producer)
                if normalized not in seen:
                    table_data.append({'Producer': normalized, 'Status': '+'})
                    seen.add(normalized)
    table_data = sorted(table_data, key=lambda x: x['Producer'])
    if table_data:
        table = markdown_table(table_data)
        table.set_params(row_sep="markdown", quote=False)
        return table.get_markdown()
    return ""



def fill_lineage_level_table(d):
    table_data = []
    for key in sorted(d.keys(), key=lambda x: tuple(map(int, x.split(".")))):
        value = d[key]
        for datasource, levels in value.get('lineage_levels', {}).items():
            row = {'Datasource': datasource}
            for level in ['dataset', 'column', 'transformation']:
                row[level.capitalize()] = '+' if level in levels else '-'
            table_data.append(row)
    if table_data:
        table = markdown_table(table_data)
        table.set_params(row_sep="markdown", quote=False)
        return table.get_markdown()
    return ""


def process_components(summaries, output_dir, is_producer, offset):
    for idx, summary in enumerate(summaries):
        label = normalize_label(summary.name)
        component_id = sanitize(summary.name)

        is_unversioned = list(summary.component_versions.keys()) == [""]

        if is_unversioned:
            # Flat structure for unversioned component
            ol_versions = summary.component_versions[""]
            facets_data = {}
            inputs_data = {}

            for ol_version, data in ol_versions.items():
                if 'facets' in data:
                    facets_data[ol_version] = data
                if 'inputs' in data:
                    inputs_data[ol_version] = data

            content_parts = []
            if facets_data:
                sorted_facets = get_sorted_facets(summary)
                content_parts.append(("Facets", fill_facet_table(facets_data, sorted_facets)))
            if inputs_data:
                content_parts.append(("Producer Inputs", fill_inputs_table(inputs_data)))

            if content_parts:
                write_markdown(
                    path=output_dir,
                    filename=component_id,
                    label=label,
                    content_parts=content_parts,
                    position=idx+offset
                )
        else:
            # Nested structure with _category_.json for versioned components
            base_path = output_dir / component_id
            write_category_json(base_path, label, idx + offset)
            comp_idx = 1
            for component_version in sorted(summary.component_versions.keys(), key=lambda x: tuple(map(int, x.split(".")))):
                ol_versions = summary.component_versions[component_version]

                facets = {}
                inputs = {}
                lineage = {}

                for ol_version, data in ol_versions.items():
                    if 'facets' in data:
                        facets[ol_version] = data
                    if not is_producer and 'inputs' in data:
                        inputs[ol_version] = data
                    if is_producer and 'lineage_levels' in data:
                        lineage[ol_version] = data

                content_parts = []
                if facets:
                    sorted_facets = get_sorted_facets(summary)
                    content_parts.append(("Facets", fill_facet_table(facets, sorted_facets)))
                if not is_producer and inputs:
                    content_parts.append(("Producer Inputs", fill_inputs_table(inputs)))
                if is_producer and lineage:
                    content_parts.append(("Lineage Levels", fill_lineage_level_table(lineage)))

                if content_parts:
                    write_markdown(
                        path=base_path,
                        filename=component_version,
                        label=component_version,
                        content_parts=content_parts,
                        position=comp_idx
                    )
                    comp_idx += 1
    return offset + len(summaries)



def generate_facets_by_openlineage_version_table(summaries):
    data_by_version = {}
    for summary in summaries:
        component_base_name = normalize_label(str(summary.name) or "<Unnamed>")
        for comp_version, ol_versions in summary.component_versions.items():
            for ol_version, values in ol_versions.items():
                if 'facets' not in values:
                    continue
                full_component_name = f"{component_base_name} ({comp_version})" if comp_version else component_base_name
                data_by_version.setdefault(ol_version, {}).setdefault(full_component_name, set()).update(
                    values['facets'])

    all_facets = {facet for components in data_by_version.values() for facets in components.values() for facet in facets}
    facet_list = sorted(all_facets)

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



def write_ol_version_summaries(consumer_summary, producer_summary, output_dir):
    consumer_by_version = generate_facets_by_openlineage_version_table(consumer_summary)
    producer_by_version = generate_facets_by_openlineage_version_table(producer_summary)

    summary_base = output_dir / "openlineage_versions"

    all_versions = sorted(set(consumer_by_version.keys()) | set(producer_by_version.keys()))

    for idx, version in enumerate(all_versions, start=1):
        version_path = summary_base / version
        write_category_json(version_path, f"OpenLineage {version}", idx)

        if version in consumer_by_version:
            write_markdown(
                version_path,
                filename="consumer_summary",
                label=f"Consumer Summary",
                content_parts=[("Facets", consumer_by_version[version])],
                position=1
            )

        if version in producer_by_version:
            write_markdown(
                version_path,
                filename="producer_summary",
                label=f"Producer Summary",
                content_parts=[("Facets", producer_by_version[version])],
                position=2
            )


def main():
    report_path, target_path = get_arguments()
    target_path.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'r') as f:
        report = Report.from_dict(json.load(f))

    consumer_summary = report.get_consumer_tag_summary()
    producer_summary = report.get_producer_tag_summary()
    offset = 3
    offset = process_components(consumer_summary, target_path, is_producer=False, offset = offset)
    process_components(producer_summary, target_path, is_producer=True, offset = offset)
    write_ol_version_summaries(consumer_summary, producer_summary, target_path)


if __name__ == "__main__":
    main()
