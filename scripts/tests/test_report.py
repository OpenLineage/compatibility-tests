from report import Report, Scenario, Test as ReportTest

TAGS = {"facets": ["sql"], "lineage_level": {"bigquery": ["dataset"]}}


def scenario(*tests):
    return Scenario.simplified("s", list(tests))


def make_test(name, status, tags=None):
    return ReportTest(name, status, "semantics", "openlineage", [] if status == "SUCCESS" else ["detail"], tags or {})


def report(*tests, component_version="1.0.0", ol="1.40.0"):
    return Report.from_dict([{
        "name": "p", "component_type": "producer", "component_version": component_version,
        "openlineage_version": ol, "scenarios": [scenario(*tests).to_dict()]}])


def test_skipped_and_warning_keep_the_scenario_green():
    assert scenario(make_test("a", "SUCCESS"), make_test("semantics", "WARNING")).status == "SUCCESS"
    assert scenario(make_test("a", "SUCCESS"), make_test("semantics", "SKIPPED")).status == "SUCCESS"
    assert scenario(make_test("a", "FAILURE"), make_test("semantics", "SKIPPED")).status == "FAILURE"


def test_skipped_and_warning_are_not_new_failures():
    new = report(make_test("a", "SUCCESS"), make_test("semantics", "WARNING"))
    assert new.get_new_failures(None).to_dict() == []


def test_skipped_and_warning_are_not_counted_in_tag_summaries():
    summary = report(make_test("a", "SUCCESS", TAGS), make_test("semantics", "WARNING", TAGS),
                     make_test("skipped", "SKIPPED", {"facets": ["other"]})).get_producer_tag_summary()
    [producer] = summary
    assert producer.component_versions["1.0.0"]["1.40.0"]["facets"] == {"sql"}


def test_round_trip_keeps_new_statuses():
    original = report(make_test("a", "SUCCESS"), make_test("semantics", "SKIPPED"))
    assert Report.from_dict(original.to_dict()).to_dict() == original.to_dict()
