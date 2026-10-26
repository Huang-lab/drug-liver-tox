"""OMOP concept resolution helpers for study conditions and labs."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from .config import (
    LIVER_CONDITION_CONCEPT_IDS,
    MEASUREMENT_CONCEPT_ALIASES,
    MEASUREMENT_CONCEPT_CODES,
    MED_MEASUREMENT_CONCEPT_IDS,
)
from .sql_runner import _resolve_sql_table_name, execute_sql


def _condition_sql_template(
    *,
    concept_table_name: str,
    concept_ancestor_table_name: str,
    condition_name: str,
) -> str:
    """Return the SQL used to resolve concept IDs for a named condition."""
    value = condition_name.strip()
    if not value:
        raise ValueError("condition_name must be a non-empty string.")
    liver_concept_names = list(LIVER_CONDITION_CONCEPT_IDS.keys())

    return f"""
        SELECT DISTINCT cd.concept_name, cd.concept_id, cd.concept_class_id
        FROM {concept_table_name} c
        JOIN {concept_ancestor_table_name} ca
          ON c.concept_id = ca.ancestor_concept_id
        JOIN {concept_table_name} cd
          ON ca.descendant_concept_id = cd.concept_id
        WHERE LOWER(c.concept_name) in unnest({liver_concept_names})
          AND c.domain_id = 'Condition'
          AND c.vocabulary_id = 'SNOMED'
          AND c.standard_concept = 'S'
          AND COALESCE(c.invalid_reason, '') = ''
    """


def _measurement_sql_template(
    *,
    concept_table_name: str,
    concept_ancestor_table_name: str,
    measurement_name: str,
) -> str:
    """Return SQL used to resolve concept IDs for a lab measurement."""
    value = measurement_name.strip()
    if not value:
        raise ValueError("measurement_name must be a non-empty string.")

    measurement_codes = MEASUREMENT_CONCEPT_CODES.get(value.lower(), (value.lower(),))
    measurement_codes_sql = ", ".join(f"'{n}'" for n in measurement_codes)

    return f"""
        SELECT DISTINCT cd.concept_name, cd.concept_id, cd.concept_class_id
        FROM {concept_table_name} c
        JOIN {concept_ancestor_table_name} ca
          ON c.concept_id = ca.ancestor_concept_id
        JOIN {concept_table_name} cd
          ON ca.descendant_concept_id = cd.concept_id
        WHERE LOWER(c.concept_code) in ({measurement_codes_sql})
          AND c.domain_id = 'Measurement'
          AND c.vocabulary_id = 'LOINC'
          AND c.standard_concept = 'S'
          AND COALESCE(c.invalid_reason, '') = ''
    """


def resolve_liver_condition_concept_ids_for_name(
    conn: Any,
    condition_name: str,
    *,
    concept_table: str = "concept",
    concept_ancestor_table: str = "concept_ancestor",
    schema: Optional[str] = None,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
) -> pd.DataFrame:
    """Resolve concept IDs for a single liver condition concept name."""
    if not condition_name or not condition_name.strip():
        raise ValueError("condition_name must be a non-empty string.")

    concept_table_name = _resolve_sql_table_name(
        concept_table,
        schema=schema,
        project_id=project_id,
        dataset_id=dataset_id,
    )
    concept_ancestor_table_name = _resolve_sql_table_name(
        concept_ancestor_table,
        schema=schema,
        project_id=project_id,
        dataset_id=dataset_id,
    )

    sql = _condition_sql_template(
        concept_table_name=concept_table_name,
        concept_ancestor_table_name=concept_ancestor_table_name,
        condition_name=condition_name,
    )
    return execute_sql(conn, sql)


def resolve_lab_measurement_concept_ids_for_name(
    conn: Any,
    measurement_name: str,
    *,
    concept_table: str = "concept",
    concept_ancestor_table: str = "concept_ancestor",
    schema: Optional[str] = None,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
) -> pd.DataFrame:
    """Resolve concept IDs for a single lab measurement concept name."""
    if not measurement_name or not measurement_name.strip():
        raise ValueError("measurement_name must be a non-empty string.")

    concept_table_name = _resolve_sql_table_name(
        concept_table,
        schema=schema,
        project_id=project_id,
        dataset_id=dataset_id,
    )
    concept_ancestor_table_name = _resolve_sql_table_name(
        concept_ancestor_table,
        schema=schema,
        project_id=project_id,
        dataset_id=dataset_id,
    )

    sql = _measurement_sql_template(
        concept_table_name=concept_table_name,
        concept_ancestor_table_name=concept_ancestor_table_name,
        measurement_name=measurement_name,
    )
    return execute_sql(conn, sql)


def resolve_liver_condition_concept_ids(
    conn: Any,
    condition_name: Optional[str] = None,
    *,
    concept_table: str = "concept",
    concept_ancestor_table: str = "concept_ancestor",
    schema: Optional[str] = None,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
) -> pd.DataFrame:
    """Resolve liver condition concept IDs from the config names."""
    names = [condition_name] if condition_name else list(LIVER_CONDITION_CONCEPT_IDS)
    frames = []
    for name in names:
        if name is None:
            continue
        frames.append(
            resolve_liver_condition_concept_ids_for_name(
                conn,
                str(name),
                concept_table=concept_table,
                concept_ancestor_table=concept_ancestor_table,
                schema=schema,
                project_id=project_id,
                dataset_id=dataset_id,
            )
        )
    if not frames:
        return pd.DataFrame(columns=["concept_name", "concept_id", "concept_class_id"])
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def resolve_lab_measurement_concept_ids(
    conn: Any,
    measurement_name: Optional[str] = None,
    *,
    concept_table: str = "concept",
    concept_ancestor_table: str = "concept_ancestor",
    schema: Optional[str] = None,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
) -> pd.DataFrame:
    """Resolve lab measurement concept IDs from config names."""
    names = (
        [measurement_name] if measurement_name else list(MED_MEASUREMENT_CONCEPT_IDS)
    )
    frames = []
    for name in names:
        if name is None:
            continue
        frames.append(
            resolve_lab_measurement_concept_ids_for_name(
                conn,
                str(name),
                concept_table=concept_table,
                concept_ancestor_table=concept_ancestor_table,
                schema=schema,
                project_id=project_id,
                dataset_id=dataset_id,
            )
        )
    if not frames:
        return pd.DataFrame(columns=["concept_name", "concept_id", "concept_class_id"])
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames, ignore_index=True).drop_duplicates()


__all__ = [
    "resolve_lab_measurement_concept_ids",
    "resolve_lab_measurement_concept_ids_for_name",
    "resolve_liver_condition_concept_ids",
    "resolve_liver_condition_concept_ids_for_name",
]
