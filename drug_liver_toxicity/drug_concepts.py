"""OMOP concept resolution helpers for drug names."""

from __future__ import annotations

from typing import Any, Callable, Optional

import pandas as pd

from .sql_runner import _resolve_sql_table_name, execute_sql


def _drug_sql_template(
    *,
    concept_table_name: str,
    concept_ancestor_table_name: str,
    drug_name: str,
) -> str:
    """Return the SQL used to resolve concept IDs for a named drug."""
    drug_pattern = drug_name.strip()
    if not drug_pattern:
        raise ValueError("drug_name must be a non-empty string.")

    return f"""
        SELECT DISTINCT cd.concept_name, cd.concept_id, cd.concept_class_id
        FROM {concept_table_name} c
        JOIN {concept_ancestor_table_name} ca
          ON c.concept_id = ca.ancestor_concept_id
        JOIN {concept_table_name} cd
          ON ca.descendant_concept_id = cd.concept_id
        WHERE LOWER(c.concept_name) LIKE '%{drug_pattern.lower()}%'
          AND c.domain_id = 'Drug'
          AND c.vocabulary_id = 'RxNorm'
          AND c.concept_class_id = 'Ingredient'
          AND c.standard_concept = 'S'
    """


def _get_drug_sql_by_name(
    drug_name: str,
    *,
    concept_table_name: str,
    concept_ancestor_table_name: str,
) -> str:
    """Look up the appropriate SQL pattern for a drug name.

    The current lookup is intentionally generic so that a new drug name can
    be handled by the same template with only the name substituted. The
    mapping can be expanded later for drug-specific exceptions if needed.
    """
    sql_lookup: dict[str, Callable[..., str]] = {
        "duloxetine": lambda: _drug_sql_template(
            concept_table_name=concept_table_name,
            concept_ancestor_table_name=concept_ancestor_table_name,
            drug_name=drug_name,
        ),
    }

    key = drug_name.strip().lower()
    template = sql_lookup.get(
        key,
        lambda: _drug_sql_template(
            concept_table_name=concept_table_name,
            concept_ancestor_table_name=concept_ancestor_table_name,
            drug_name=drug_name,
        ),
    )
    return template()


def resolve_drug_concept_ids_for_name(
    conn: Any,
    drug_name: str,
    *,
    concept_table: str = "concept",
    concept_ancestor_table: str = "concept_ancestor",
    schema: Optional[str] = None,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
) -> pd.DataFrame:
    """Resolve concept IDs for the supplied drug name.

    This follows the OMOP ingredient-based approach and traverses the concept
    ancestor graph to retrieve descendant drug concepts.
    """
    if not drug_name or not drug_name.strip():
        raise ValueError("drug_name must be a non-empty string.")

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

    sql = _get_drug_sql_by_name(
        drug_name,
        concept_table_name=concept_table_name,
        concept_ancestor_table_name=concept_ancestor_table_name,
    )
    return execute_sql(conn, sql)


def resolve_drug_concept_ids(
    conn: Any,
    drug_name: str = "duloxetine",
    *,
    concept_table: str = "concept",
    concept_ancestor_table: str = "concept_ancestor",
    schema: Optional[str] = None,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
) -> pd.DataFrame:
    """Backward-compatible wrapper for resolving a drug's concept IDs."""
    return resolve_drug_concept_ids_for_name(
        conn,
        drug_name,
        concept_table=concept_table,
        concept_ancestor_table=concept_ancestor_table,
        schema=schema,
        project_id=project_id,
        dataset_id=dataset_id,
    )


__all__ = [
    "resolve_drug_concept_ids",
    "resolve_drug_concept_ids_for_name",
]
