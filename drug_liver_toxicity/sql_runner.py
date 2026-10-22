"""Database and SQL helpers for OMOP-based cohort extraction."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence

import pandas as pd


def execute_sql(
    conn: Any,
    query: str,
    params: Optional[dict[str, Any]] = None,
) -> pd.DataFrame:
    """Execute a SQL query and return the result as a DataFrame.

    Supports pandas SQLAlchemy connections and BigQuery clients used by
    ResearchAllOfUs OMOP data extracts.
    """
    if hasattr(conn, "query") and hasattr(conn, "project"):
        try:
            job = conn.query(query)
            if hasattr(job, "result"):
                job = job.result()
            if hasattr(job, "to_dataframe"):
                return job.to_dataframe()
            if hasattr(job, "to_arrow"):
                return job.to_arrow().to_pandas()
            if hasattr(job, "rows") and hasattr(job, "schema"):
                return pd.DataFrame(job.result().rows)
        except Exception:
            # BigQuery should not fall back to SQLite/pandas, because a Client
            # object is not a DBAPI connection and will fail with a cursor error.
            # Surface the real BigQuery issue instead of masking it.
            raise

    try:
        return pd.read_sql_query(query, conn, params=params)
    except TypeError:
        if hasattr(conn, "engine"):
            with conn.engine.connect() as connection:
                return pd.read_sql_query(query, connection, params=params)
        raise


def _resolve_sql_table_name(
    table_name: str,
    schema: Optional[str] = None,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
) -> str:
    """Return a fully qualified table reference for SQL or BigQuery."""
    dataset = schema or dataset_id
    pieces = []
    if project_id:
        pieces.append(project_id)
    if dataset:
        pieces.append(dataset)
    if table_name:
        pieces.append(table_name)
    if not pieces:
        return table_name
    return "`" + ".".join(pieces) + "`"


def _quote_sql_literal(value: str) -> str:
    """Escape a string for placement inside SQL quoted literals."""
    return value.replace("'", "''")


def _sql_name_list(values: Sequence[str]) -> str:
    """Build a BigQuery-safe list of string literals."""
    return ", ".join(f"LOWER('{_quote_sql_literal(v)}')" for v in values)


def resolve_concept_ids(
    conn: Any,
    concept_names: Sequence[str] | str,
    *,
    concept_table: str = "concept",
    concept_ancestor_table: str = "concept_ancestor",
    schema: Optional[str] = None,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    include_descendants: bool = True,
    vocabulary_id: Optional[Sequence[str] | str] = None,
    domain_id: Optional[Sequence[str] | str] = None,
    concept_class_id: Optional[Sequence[str] | str] = None,
    standard_concept: Optional[str] = None,
    invalid_reason: Optional[str] = None,
) -> dict[str, tuple[int, ...]]:
    """Resolve OMOP concept IDs from concept names.

    Additional OMOP metadata filters can be supplied to avoid ambiguous
    string matches, such as vocabulary_id, domain_id,
    concept_class_id, standard_concept, and invalid_reason.
    """
    if isinstance(concept_names, str):
        concept_names = [concept_names]
    if isinstance(vocabulary_id, str):
        vocabulary_id = [vocabulary_id]
    if isinstance(domain_id, str):
        domain_id = [domain_id]
    if isinstance(concept_class_id, str):
        concept_class_id = [concept_class_id]

    clean_names = [
        name.strip() for name in concept_names if isinstance(name, str) and name.strip()
    ]
    if not clean_names:
        return {}

    names = list(dict.fromkeys(clean_names))
    name_list = _sql_name_list(names)
    concept_table_name = _resolve_sql_table_name(
        concept_table,
        schema=schema,
        project_id=project_id,
        dataset_id=dataset_id,
    )
    ancestor_table_name = _resolve_sql_table_name(
        concept_ancestor_table,
        schema=schema,
        project_id=project_id,
        dataset_id=dataset_id,
    )

    filter_clauses = []
    if vocabulary_id:
        vocab_values = ", ".join(
            f"'{_quote_sql_literal(str(v))}'" for v in vocabulary_id
        )
        filter_clauses.append(f"c.vocabulary_id IN ({vocab_values})")
    if domain_id:
        domain_values = ", ".join(f"'{_quote_sql_literal(str(v))}'" for v in domain_id)
        filter_clauses.append(f"c.domain_id IN ({domain_values})")
    if concept_class_id:
        class_values = ", ".join(
            f"'{_quote_sql_literal(str(v))}'" for v in concept_class_id
        )
        filter_clauses.append(f"c.concept_class_id IN ({class_values})")

    if standard_concept is not None:
        standard_sql = (
            "LOWER(COALESCE(c.standard_concept, '')) = "
            f"'{_quote_sql_literal(str(standard_concept).lower())}'"
        )
        filter_clauses.append(standard_sql)
    if invalid_reason is not None:
        invalid_sql = (
            "LOWER(COALESCE(c.invalid_reason, '')) = "
            f"'{_quote_sql_literal(str(invalid_reason).lower())}'"
        )
        filter_clauses.append(invalid_sql)

    where_clause = "\n        AND ".join(filter_clauses)
    where_sql = f"\n        AND {where_clause}" if where_clause else ""

    direct_query = f"""
        SELECT DISTINCT c.concept_name, c.concept_id
        FROM {concept_table_name} c
        WHERE LOWER(c.concept_name) IN ({name_list})
        {where_sql}
    """
    direct_df = execute_sql(conn, direct_query)
    if direct_df.empty:
        resolved: dict[str, tuple[int, ...]] = {name: () for name in names}
    else:
        resolved = {
            name: tuple(
                sorted(
                    {
                        int(v)
                        for v in direct_df.loc[
                            direct_df["concept_name"].str.lower() == name.lower(),
                            "concept_id",
                        ]
                    }
                )
            )
            for name in names
        }

    if not include_descendants:
        return resolved

    ancestor_query = f"""
        WITH seed_concepts AS (
            SELECT DISTINCT c.concept_id, c.concept_name
            FROM {concept_table_name} c
            WHERE LOWER(c.concept_name) IN ({name_list})
            {where_sql}
        )
        SELECT DISTINCT sc.concept_name, ca.descendant_concept_id AS concept_id
        FROM {ancestor_table_name} ca
        INNER JOIN seed_concepts sc
            ON ca.ancestor_concept_id = sc.concept_id
        WHERE ca.descendant_concept_id IS NOT NULL
    """
    ancestor_df = execute_sql(conn, ancestor_query)
    if not ancestor_df.empty:
        for name in names:
            ancestor_ids = {
                int(v)
                for v in ancestor_df.loc[
                    ancestor_df["concept_name"].str.lower() == name.lower(),
                    "concept_id",
                ]
            }
            merged = set(resolved.get(name, ())) | ancestor_ids
            resolved[name] = tuple(sorted(merged))

    return resolved


def _coerce_concept_values(values: Iterable[Any]) -> list[int | str]:
    """Normalize a concept mapping into direct IDs or concept names."""
    if values is None:
        return []

    if isinstance(values, (str, int, float)):
        return [values]

    if isinstance(values, (list, tuple, set)):
        normalized: list[int | str] = []
        for value in values:
            if isinstance(value, (list, tuple, set)):
                normalized.extend(_coerce_concept_values(value))
            elif isinstance(value, str):
                normalized.append(value)
            elif value is not None:
                normalized.append(int(value))
        return normalized

    try:
        iterator = list(values)
    except TypeError:
        return [values]

    normalized = []
    for value in iterator:
        if isinstance(value, (list, tuple, set)):
            normalized.extend(_coerce_concept_values(value))
        elif isinstance(value, str):
            normalized.append(value)
        elif value is not None:
            normalized.append(int(value))
    return normalized


def _concept_ids_from_mapping(
    conn: Any,
    concept_mapping: Mapping[str, Any],
    *,
    concept_table: str = "concept",
    concept_ancestor_table: str = "concept_ancestor",
    schema: Optional[str] = None,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    filters: Optional[Mapping[str, Any]] = None,
) -> dict[str, tuple[int, ...]]:
    """Resolve concept IDs for a mapping of labels -> concept names/IDs."""
    resolved: dict[str, tuple[int, ...]] = {}
    concept_filters = filters or {}
    for label, values in concept_mapping.items():
        normalized_values = _coerce_concept_values(values)
        if not normalized_values:
            resolved[label] = ()
            continue

        names = [v for v in normalized_values if isinstance(v, str)]
        explicit_ids = [
            int(v) for v in normalized_values if isinstance(v, (int, float))
        ]

        if names:
            lookup = resolve_concept_ids(
                conn,
                names,
                concept_table=concept_table,
                concept_ancestor_table=concept_ancestor_table,
                schema=schema,
                project_id=project_id,
                dataset_id=dataset_id,
                vocabulary_id=concept_filters.get("vocabulary_id"),
                domain_id=concept_filters.get("domain_id"),
                concept_class_id=concept_filters.get("concept_class_id"),
                standard_concept=concept_filters.get("standard_concept"),
                invalid_reason=concept_filters.get("invalid_reason"),
            )
            resolved[label] = tuple(
                sorted({concept_id for ids in lookup.values() for concept_id in ids})
            )
        elif explicit_ids:
            resolved[label] = tuple(sorted(set(explicit_ids)))
        else:
            resolved[label] = ()

    return resolved


def _drop_duplicate_rows(
    frame: pd.DataFrame,
    subset: Sequence[str],
) -> pd.DataFrame:
    return (
        frame.drop_duplicates(subset=subset).sort_values(subset).reset_index(drop=True)
    )
