"""Build a drug exposure cohort for liver toxicity analysis."""

from __future__ import annotations

from typing import Any, Mapping, Optional

import pandas as pd

from .config import (
    CohortConfig,
    DRUG_CONCEPT_IDS,
    LAB_ULN,
    LIVER_CONDITION_CONCEPT_IDS,
    MED_MEASUREMENT_CONCEPT_IDS,
    STUDY,
)
from .sql_runner import (
    _concept_ids_from_mapping,
    _drop_duplicate_rows,
    _resolve_sql_table_name,
    execute_sql,
)


def build_drug_cohort(
    conn: Any,
    config: Optional[CohortConfig] = None,
    *,
    drug_name: Optional[str] = None,
    exclude_prior_liver_disease: Optional[bool] = None,
    exclude_baseline_abnormal_liver_tests: Optional[bool] = None,
    drug_exposure_table: Optional[str] = None,
    condition_occurrence_table: Optional[str] = None,
    measurement_table: Optional[str] = None,
    person_table: Optional[str] = None,
    concept_table: Optional[str] = None,
    concept_ancestor_table: Optional[str] = None,
    schema: Optional[str] = None,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    drug_concept_ids: Optional[Mapping[str, Any]] = None,
    liver_condition_concept_ids: Optional[Mapping[str, Any]] = None,
    measurement_concept_ids: Optional[Mapping[str, Any]] = None,
) -> pd.DataFrame:
    """Build a cohort using a CohortConfig object or direct arguments.

    Most of the settings are typically supplied in the config object so callers
    only need to pass the connection and optionally a few overrides.
    """
    if config is None:
        config = CohortConfig(
            drug_name=drug_name or STUDY.drug_name,
            exclude_prior_liver_disease=(
                exclude_prior_liver_disease
                if exclude_prior_liver_disease is not None
                else True
            ),
            exclude_baseline_abnormal_liver_tests=(
                exclude_baseline_abnormal_liver_tests
                if exclude_baseline_abnormal_liver_tests is not None
                else True
            ),
            drug_exposure_table=(drug_exposure_table or "drug_exposure"),
            condition_occurrence_table=(
                condition_occurrence_table or "condition_occurrence"
            ),
            measurement_table=(measurement_table or "measurement"),
            person_table=(person_table or "person"),
            concept_table=(concept_table or "concept"),
            concept_ancestor_table=(concept_ancestor_table or "concept_ancestor"),
            schema=schema,
            project_id=project_id,
            dataset_id=dataset_id,
            drug_concept_ids=drug_concept_ids,
            liver_condition_concept_ids=liver_condition_concept_ids,
            measurement_concept_ids=measurement_concept_ids,
        )
    else:
        if drug_name is not None:
            config.drug_name = drug_name
        if exclude_prior_liver_disease is not None:
            config.exclude_prior_liver_disease = exclude_prior_liver_disease
        if exclude_baseline_abnormal_liver_tests is not None:
            config.exclude_baseline_abnormal_liver_tests = (
                exclude_baseline_abnormal_liver_tests
            )
        if drug_exposure_table is not None:
            config.drug_exposure_table = drug_exposure_table
        if condition_occurrence_table is not None:
            config.condition_occurrence_table = condition_occurrence_table
        if measurement_table is not None:
            config.measurement_table = measurement_table
        if person_table is not None:
            config.person_table = person_table
        if concept_table is not None:
            config.concept_table = concept_table
        if concept_ancestor_table is not None:
            config.concept_ancestor_table = concept_ancestor_table
        if schema is not None:
            config.schema = schema
        if project_id is not None:
            config.project_id = project_id
        if dataset_id is not None:
            config.dataset_id = dataset_id
        if drug_concept_ids is not None:
            config.drug_concept_ids = drug_concept_ids
        if liver_condition_concept_ids is not None:
            config.liver_condition_concept_ids = liver_condition_concept_ids
        if measurement_concept_ids is not None:
            config.measurement_concept_ids = measurement_concept_ids

    if conn is None:
        raise ValueError("A database connection or engine is required.")

    if config.drug_concept_ids is None:
        config.drug_concept_ids = DRUG_CONCEPT_IDS
    if config.liver_condition_concept_ids is None:
        config.liver_condition_concept_ids = LIVER_CONDITION_CONCEPT_IDS
    if config.measurement_concept_ids is None:
        config.measurement_concept_ids = MED_MEASUREMENT_CONCEPT_IDS

    drug_filters = config.drug_concept_filters or {}
    liver_filters = config.liver_concept_filters or {}
    measurement_filters = config.measurement_concept_filters or {}

    resolved_drug = _concept_ids_from_mapping(
        conn,
        {
            config.drug_name: config.drug_concept_ids.get(
                config.drug_name, (config.drug_name,)
            )
        },
        concept_table=config.concept_table,
        concept_ancestor_table=config.concept_ancestor_table,
        schema=config.schema,
        project_id=config.project_id,
        dataset_id=config.dataset_id,
        filters=drug_filters,
    )
    drug_concept_id_values = resolved_drug.get(config.drug_name, ())

    resolved_liver = _concept_ids_from_mapping(
        conn,
        config.liver_condition_concept_ids,
        concept_table=config.concept_table,
        concept_ancestor_table=config.concept_ancestor_table,
        schema=config.schema,
        project_id=config.project_id,
        dataset_id=config.dataset_id,
        filters=liver_filters,
    )
    liver_concept_ids = tuple(
        sorted({concept_id for ids in resolved_liver.values() for concept_id in ids})
    )

    resolved_measurement = _concept_ids_from_mapping(
        conn,
        config.measurement_concept_ids,
        concept_table=config.concept_table,
        concept_ancestor_table=config.concept_ancestor_table,
        schema=config.schema,
        project_id=config.project_id,
        dataset_id=config.dataset_id,
        filters=measurement_filters,
    )
    measurement_concept_ids_flat = tuple(
        sorted(
            {concept_id for ids in resolved_measurement.values() for concept_id in ids}
        )
    )

    exposure_table = _resolve_sql_table_name(
        config.drug_exposure_table,
        schema=config.schema,
        project_id=config.project_id,
        dataset_id=config.dataset_id,
    )
    condition_table = _resolve_sql_table_name(
        config.condition_occurrence_table,
        schema=config.schema,
        project_id=config.project_id,
        dataset_id=config.dataset_id,
    )
    measurement_table_name = _resolve_sql_table_name(
        config.measurement_table,
        schema=config.schema,
        project_id=config.project_id,
        dataset_id=config.dataset_id,
    )
    person_table_name = _resolve_sql_table_name(
        config.person_table,
        schema=config.schema,
        project_id=config.project_id,
        dataset_id=config.dataset_id,
    )

    if not drug_concept_id_values:
        return pd.DataFrame(columns=["person_id", "index_date"])

    drug_ids_sql = ", ".join(str(int(value)) for value in drug_concept_id_values)
    exposure_query = f"""
        SELECT person_id, MIN(drug_exposure_start_datetime) AS index_date
        FROM {exposure_table}
        WHERE drug_concept_id IN ({drug_ids_sql})
        GROUP BY person_id
    """
    exposure = execute_sql(conn, exposure_query)
    if exposure.empty:
        return pd.DataFrame(columns=["person_id", "index_date"])

    exposure = _drop_duplicate_rows(
        exposure[["person_id", "index_date"]], ["person_id", "index_date"]
    )
    exposure = (
        exposure.sort_values(["person_id", "index_date"])
        .groupby("person_id", as_index=False)
        .first()
    )
    cohort = exposure.copy()

    if config.exclude_prior_liver_disease and liver_concept_ids:
        liver_ids_sql = ", ".join(str(int(value)) for value in liver_concept_ids)
        prior_liver_query = f"""
            WITH exposed AS (
                SELECT person_id, MIN(index_date) AS min_index_date
                FROM (
                    SELECT person_id,
                           MIN(drug_exposure_start_datetime) AS index_date
                    FROM {exposure_table}
                    WHERE drug_concept_id IN ({drug_ids_sql})
                    GROUP BY person_id
                ) t
                GROUP BY person_id
            )
            SELECT DISTINCT co.person_id
            FROM {condition_table} co
            INNER JOIN exposed e
                ON co.person_id = e.person_id
            WHERE co.condition_concept_id IN ({liver_ids_sql})
              AND co.condition_start_datetime < e.min_index_date
        """
        excluded_people = set(
            execute_sql(conn, prior_liver_query)["person_id"].tolist()
        )
        cohort = cohort[~cohort["person_id"].isin(excluded_people)].copy()

    if config.exclude_baseline_abnormal_liver_tests and measurement_concept_ids_flat:
        lab_ids_sql = ", ".join(
            str(int(value)) for value in measurement_concept_ids_flat
        )
        baseline_query = f"""
            WITH cohort AS (
                SELECT c.person_id, c.index_date
                FROM (
                    SELECT person_id,
                           MIN(drug_exposure_start_datetime) AS index_date
                    FROM {exposure_table}
                    WHERE drug_concept_id IN ({drug_ids_sql})
                    GROUP BY person_id
                ) c
            )
            SELECT m.person_id,
                   m.measurement_datetime,
                   m.measurement_concept_id,
                   m.value_as_number,
                   c.index_date
            FROM {measurement_table_name} m
            INNER JOIN cohort c
                ON m.person_id = c.person_id
            WHERE m.measurement_concept_id IN ({lab_ids_sql})
              AND m.measurement_datetime < c.index_date
        """
        baseline = execute_sql(conn, baseline_query)
        if not baseline.empty:
            abnormal = baseline[
                (
                    (
                        baseline["measurement_concept_id"]
                        == resolved_measurement.get("alt", ())[0]
                        if resolved_measurement.get("alt")
                        else False
                    )
                    & (baseline["value_as_number"] >= 3 * LAB_ULN["alt"])
                )
                | (
                    (
                        baseline["measurement_concept_id"]
                        == resolved_measurement.get("ast", ())[0]
                        if resolved_measurement.get("ast")
                        else False
                    )
                    & (baseline["value_as_number"] >= 3 * LAB_ULN["ast"])
                )
                | (
                    (
                        baseline["measurement_concept_id"]
                        == resolved_measurement.get("bilirubin", ())[0]
                        if resolved_measurement.get("bilirubin")
                        else False
                    )
                    & (baseline["value_as_number"] >= 2 * LAB_ULN["bilirubin"])
                )
            ].copy()
            excluded_people = set(abnormal["person_id"].unique())
            cohort = cohort[~cohort["person_id"].isin(excluded_people)].copy()

    if person_table_name:
        person_query = f"""
            SELECT person_id, year_of_birth, sex_at_birth, race, ethnicity
            FROM {person_table_name}
            WHERE person_id IN (
                SELECT DISTINCT person_id
                FROM (
                    SELECT person_id,
                           MIN(drug_exposure_start_datetime) AS index_date
                    FROM {exposure_table}
                    WHERE drug_concept_id IN ({drug_ids_sql})
                    GROUP BY person_id
                )
            )
        """
        person = execute_sql(conn, person_query)
        if not person.empty:
            cohort = cohort.merge(person, on="person_id", how="left")

    return cohort.reset_index(drop=True)


def build_cohort_from_sql_tables(
    conn: Any,
    *,
    drug_name: str = STUDY.drug_name,
    exclude_prior_liver_disease: bool = True,
    exclude_baseline_abnormal_liver_tests: bool = True,
    project_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    schema: Optional[str] = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Backward-compatible wrapper for the SQL-backed cohort builder."""
    return build_drug_cohort(
        conn,
        drug_name=drug_name,
        exclude_prior_liver_disease=exclude_prior_liver_disease,
        exclude_baseline_abnormal_liver_tests=exclude_baseline_abnormal_liver_tests,
        project_id=project_id,
        dataset_id=dataset_id,
        schema=schema,
        **kwargs,
    )


# Backward compatibility with the older dataframe-based API.
def build_drug_cohort_from_dataframes(
    drug_exposure: pd.DataFrame,
    condition_occurrence: pd.DataFrame,
    measurement: pd.DataFrame,
    person: Optional[pd.DataFrame] = None,
    drug_name: str = STUDY.drug_name,
    exclude_prior_liver_disease: bool = True,
    exclude_baseline_abnormal_liver_tests: bool = True,
) -> pd.DataFrame:
    """Legacy dataframe implementation retained as a compatibility fallback."""
    concept_ids = set(DRUG_CONCEPT_IDS.get(drug_name, ()))

    exposure = drug_exposure[drug_exposure["drug_concept_id"].isin(concept_ids)].copy()
    if exposure.empty:
        return pd.DataFrame(columns=["person_id", "index_date"])

    exposure = exposure.rename(columns={"drug_exposure_start_datetime": "index_date"})
    exposure = (
        exposure[["person_id", "index_date"]]
        .drop_duplicates()
        .sort_values(["person_id", "index_date"])
    )
    exposure = exposure.groupby("person_id", as_index=False).first()

    cohort = exposure.copy()

    if exclude_prior_liver_disease:
        prior_liver = condition_occurrence[
            condition_occurrence["condition_concept_id"].isin(
                set(LIVER_CONDITION_CONCEPT_IDS.values())
            )
        ].copy()
        prior_liver = prior_liver[
            prior_liver["condition_start_datetime"] < cohort["index_date"].min()
        ]
        excluded_people = set(prior_liver["person_id"].unique())
        cohort = cohort[~cohort["person_id"].isin(excluded_people)].copy()

    if exclude_baseline_abnormal_liver_tests:
        lab_concepts = set(MED_MEASUREMENT_CONCEPT_IDS.values())
        baseline = measurement[
            measurement["measurement_concept_id"].isin(lab_concepts)
        ].copy()
        baseline = baseline.merge(
            cohort[["person_id", "index_date"]], on="person_id", how="inner"
        )
        baseline = baseline[baseline["measurement_datetime"] < baseline["index_date"]]

        abnormal = baseline[
            (
                (
                    baseline["measurement_concept_id"]
                    == MED_MEASUREMENT_CONCEPT_IDS["alt"]
                )
                & (baseline["value_as_number"] >= 3 * LAB_ULN["alt"])
            )
            | (
                (
                    baseline["measurement_concept_id"]
                    == MED_MEASUREMENT_CONCEPT_IDS["ast"]
                )
                & (baseline["value_as_number"] >= 3 * LAB_ULN["ast"])
            )
            | (
                (
                    baseline["measurement_concept_id"]
                    == MED_MEASUREMENT_CONCEPT_IDS["bilirubin"]
                )
                & (baseline["value_as_number"] >= 2 * LAB_ULN["bilirubin"])
            )
        ].copy()
        excluded_people = set(abnormal["person_id"].unique())
        cohort = cohort[~cohort["person_id"].isin(excluded_people)].copy()

    if person is not None and not person.empty:
        person = person[
            ["person_id", "year_of_birth", "sex_at_birth", "race", "ethnicity"]
        ].copy()
        cohort = cohort.merge(person, on="person_id", how="left")

    return cohort.reset_index(drop=True)
