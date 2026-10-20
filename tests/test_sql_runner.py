import os
import sys
import pandas as pd

# Ensure repo root is on sys.path for imports when running pytest from tests/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load sql_runner directly to avoid importing package-level modules that pull in
# heavy compiled dependencies during test collection.
import importlib.util

_sql_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "drug_liver_toxicity", "sql_runner.py"
    )
)
spec = importlib.util.spec_from_file_location("sql_runner", _sql_path)
sr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sr)


def test_resolve_sql_table_name_variants():
    assert sr._resolve_sql_table_name("person") == "`person`"
    assert sr._resolve_sql_table_name("person", schema="s") == "`s.person`"
    assert (
        sr._resolve_sql_table_name("person", project_id="p", dataset_id="d")
        == "`p.d.person`"
    )
    # schema takes precedence over dataset_id
    assert (
        sr._resolve_sql_table_name("person", schema="s", dataset_id="d") == "`s.person`"
    )


def test_quote_and_name_list():
    assert sr._quote_sql_literal("O'Brian") == "O''Brian"
    assert sr._sql_name_list(["A", "b"]) == "LOWER('A'), LOWER('b')"


def test_coerce_concept_values():
    vals = [1, "aspirin", [2, "ibuprofen"], None, (3,)]
    coerced = sr._coerce_concept_values(vals)
    # Expect ints converted, strings preserved, nested flattened
    assert set(coerced) == {1, 2, 3, "aspirin", "ibuprofen"}


def test_resolve_concept_ids_direct_and_descendants(monkeypatch):
    # Prepare a fake execute_sql to return controlled DataFrames
    def fake_execute_sql(conn, query, params=None):
        q = query.lower()
        if ("from `concept`" in q or "from concept" in q) and (
            "descendant_concept_id" not in q
        ):
            # direct match: two ids
            return pd.DataFrame(
                {
                    "concept_name": ["aspirin", "aspirin"],
                    "concept_id": [111, 222],
                }
            )
        if (
            "from `concept_ancestor`" in q
            or "from concept_ancestor" in q
            or "descendant_concept_id" in q
        ):
            return pd.DataFrame(
                {
                    "concept_name": ["aspirin"],
                    "concept_id": [333],
                }
            )
        return pd.DataFrame()

    monkeypatch.setattr(sr, "execute_sql", fake_execute_sql)

    resolved = sr.resolve_concept_ids(
        None,
        "aspirin",
        concept_table="concept",
        concept_ancestor_table="concept_ancestor",
        include_descendants=True,
    )
    assert "aspirin" in resolved
    # Should include direct ids 111,222 and descendant 333
    assert tuple(sorted(resolved["aspirin"])) == (111, 222, 333)


def test_resolve_concept_ids_no_match(monkeypatch):
    def fake_execute_sql(conn, query, params=None):
        return pd.DataFrame()

    monkeypatch.setattr(sr, "execute_sql", fake_execute_sql)
    resolved = sr.resolve_concept_ids(
        None,
        ["nope"],
        concept_table="concept",
        concept_ancestor_table="concept_ancestor",
    )
    assert resolved == {"nope": ()}


def test_concept_ids_from_mapping_with_explicit_and_names(monkeypatch):
    captured = {}

    def fake_resolve(conn, names, **kwargs):
        captured["names"] = names
        captured["kwargs"] = kwargs
        return {"aspirin": (101,), "ibuprofen": (202,)}

    monkeypatch.setattr(sr, "resolve_concept_ids", fake_resolve)

    mapping = {"drug": [1, "aspirin", (2, "ibuprofen")]}
    result = sr._concept_ids_from_mapping(None, mapping)
    assert "drug" in result
    # Implementation returns only resolved ids when names are present
    assert tuple(sorted(result["drug"])) == (101, 202)


def test_concept_ids_from_mapping_forwards_filters(monkeypatch):
    recorded = {}

    def fake_resolve(conn, names, **kwargs):
        recorded.update(kwargs)
        return {n: (999,) for n in names}

    monkeypatch.setattr(sr, "resolve_concept_ids", fake_resolve)

    mapping = {"x": ["foo"]}
    filters = {
        "vocabulary_id": "V",
        "domain_id": ["D"],
        "concept_class_id": "C",
        "standard_concept": "S",
        "invalid_reason": None,
    }
    res = sr._concept_ids_from_mapping(None, mapping, filters=filters)
    assert res["x"] == (999,)
    assert recorded.get("vocabulary_id") == filters["vocabulary_id"]
    assert recorded.get("domain_id") == filters["domain_id"]
    assert recorded.get("concept_class_id") == filters["concept_class_id"]
    assert recorded.get("standard_concept") == filters["standard_concept"]
    assert recorded.get("invalid_reason") == filters["invalid_reason"]


def test_concept_ids_from_mapping_empty_values():
    res = sr._concept_ids_from_mapping(None, {"a": []})
    assert res == {"a": ()}
