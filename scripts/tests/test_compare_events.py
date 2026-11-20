from compare_events import diff

UNORDERED = "{{ unordered_list(result, 'transformations') }}"


def test_unordered_list_matches_in_any_order():
    expected = {UNORDERED: [{"subtype": "GROUP_BY"}, {"subtype": "SORT"}]}
    result = {"transformations": [{"subtype": "SORT", "type": "INDIRECT"}, {"subtype": "GROUP_BY", "type": "INDIRECT"}]}
    assert diff(expected, result) == []


def test_unordered_list_reports_a_missing_element():
    expected = {UNORDERED: [{"subtype": "GROUP_BY"}, {"subtype": "SORT"}]}
    result = {"transformations": [{"subtype": "SORT"}, {"subtype": "FILTER"}]}
    assert diff(expected, result) == ["In .transformations.[0], no matching elements"]


def test_plain_lists_stay_ordered():
    expected = {"transformations": [{"subtype": "GROUP_BY"}, {"subtype": "SORT"}]}
    result = {"transformations": [{"subtype": "SORT"}, {"subtype": "GROUP_BY"}]}
    assert len(diff(expected, result)) == 2
