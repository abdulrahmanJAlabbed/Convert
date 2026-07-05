"""Data import/export quality: round-trips must preserve values exactly."""
import csv
import json

import pytest

from engines import data
from core import capabilities


def test_csv_json_csv_roundtrip(fixtures, tmp_path, nullconsole):
    j = tmp_path / "a.json"
    c = tmp_path / "a.csv"
    data.csv_to_json(fixtures["csv"], nullconsole, output_path=j)
    data.json_to_csv(j, nullconsole, output_path=c)
    rows = list(csv.DictReader(c.open()))
    assert rows == [{"name": "Alice", "score": "90"}, {"name": "Bob", "score": "85"}]


@pytest.mark.skipif(not capabilities.can("data_yaml"), reason="PyYAML missing")
def test_json_yaml_json_roundtrip(fixtures, tmp_path, nullconsole):
    y = tmp_path / "a.yaml"
    j = tmp_path / "a.json"
    data.json_to_yaml(fixtures["json"], nullconsole, output_path=y)
    data.yaml_to_json(y, nullconsole, output_path=j)
    obj = json.loads(j.read_text())
    assert obj == [{"name": "Alice", "score": 90}, {"name": "Bob", "score": 85}]


def test_xml_to_json_preserves_attributes_and_values(fixtures, tmp_path, nullconsole):
    o = tmp_path / "x.json"
    data.xml_to_json(fixtures["xml"], nullconsole, output_path=o)
    obj = json.loads(o.read_text())
    items = obj["root"]["item"]
    assert [i["@id"] for i in items] == ["1", "2"]
    assert [i["#text"] for i in items] == ["A", "B"]


def test_json_minify_is_smaller_and_valid(fixtures, tmp_path, nullconsole):
    o = tmp_path / "m.json"
    data.json_minify(fixtures["json"], nullconsole, output_path=o)
    text = o.read_text()
    assert " " not in text and json.loads(text)  # compact + still valid
