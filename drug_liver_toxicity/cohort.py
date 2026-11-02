"""Build a drug exposure cohort for liver toxicity analysis."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

import pandas as pd

from .config import (
    CohortConfig,
    DRUG_CONCEPT_IDS,
    LAB_ULN,
    LIVER_CONDITION_CONCEPT_IDS,
    MED_MEASUREMENT_CONCEPT_IDS,
    STUDY,
)
from .drug_concepts import resolve_drug_concept_ids_for_name
from .sql_runner import (
    _coerce_concept_values,
    _concept_ids_from_mapping,
    _drop_duplicate_rows,
    _resolve_sql_table_name,
    execute_sql,
)
from .study_concepts import (
    resolve_lab_measurement_concept_ids,
    resolve_liver_condition_concept_ids,
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
) -> Tuple[
    pd.DataFrame,
    pd.DataFrame,
    Mapping[str, int],
]:
    """Build a cohort using a CohortConfig object or direct arguments.

    Most of the settings are typically supplied in the config object so callers
    only need to pass the connection and optionally a few overrides.
    """
    stats = {}
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

    liver_filters = config.liver_concept_filters or {}
    measurement_filters = config.measurement_concept_filters or {}

    drug_concept_value_set = config.drug_concept_ids.get(config.drug_name, ())
    if drug_concept_value_set:
        if isinstance(drug_concept_value_set, (str, int, float)):
            raw_ids = (drug_concept_value_set,)
        else:
            raw_ids = tuple(drug_concept_value_set)
        resolved_drug = {
            config.drug_name: tuple(
                sorted({int(value) for value in raw_ids if value is not None})
            )
        }
    else:
        drug_df = resolve_drug_concept_ids_for_name(
            conn,
            config.drug_name,
            concept_table=config.concept_table,
            concept_ancestor_table=config.concept_ancestor_table,
            schema=config.schema,
            project_id=config.project_id,
            dataset_id=config.dataset_id,
        )
        resolved_drug = {
            config.drug_name: tuple(
                sorted(
                    {int(value) for value in drug_df["concept_id"].dropna().tolist()}
                )
            )
        }
    drug_concept_id_values = list(resolved_drug.get(config.drug_name, ()))

    liver_concept_value_set = config.liver_condition_concept_ids
    if liver_concept_value_set:
        if isinstance(liver_concept_value_set, dict):
            resolved_liver = _concept_ids_from_mapping(
                conn,
                liver_concept_value_set,
                concept_table=config.concept_table,
                concept_ancestor_table=config.concept_ancestor_table,
                schema=config.schema,
                project_id=config.project_id,
                dataset_id=config.dataset_id,
                filters=liver_filters,
            )
        else:
            resolved_liver = {
                "liver_condition": tuple(
                    sorted(
                        {
                            int(value)
                            for value in liver_concept_value_set
                            if value is not None
                        }
                    )
                )
            }
    else:
        resolved_liver_df = resolve_liver_condition_concept_ids(
            conn,
            concept_table=config.concept_table,
            concept_ancestor_table=config.concept_ancestor_table,
            schema=config.schema,
            project_id=config.project_id,
            dataset_id=config.dataset_id,
        )
        resolved_liver = {
            "liver_condition": tuple(
                sorted(
                    {
                        int(value)
                        for value in resolved_liver_df["concept_id"].dropna().tolist()
                    }
                )
            )
        }
    liver_concept_ids = tuple(
        sorted({concept_id for ids in resolved_liver.values() for concept_id in ids})
    )

    measurement_concept_value_set = config.measurement_concept_ids
    if measurement_concept_value_set:
        if isinstance(measurement_concept_value_set, dict):
            resolved_measurement = _concept_ids_from_mapping(
                conn,
                measurement_concept_value_set,
                concept_table=config.concept_table,
                concept_ancestor_table=config.concept_ancestor_table,
                schema=config.schema,
                project_id=config.project_id,
                dataset_id=config.dataset_id,
                filters=measurement_filters,
            )
        else:
            resolved_measurement = {
                "measurement": tuple(
                    sorted(
                        {
                            int(value)
                            for value in measurement_concept_value_set
                            if value is not None
                        }
                    )
                )
            }
        measurement_concept_ids_flat = list(
            sorted(
                {
                    concept_id
                    for ids in resolved_measurement.values()
                    for concept_id in ids
                }
            )
        )
    else:
        resolved_measurement_df = resolve_lab_measurement_concept_ids(
            conn,
            concept_table=config.concept_table,
            concept_ancestor_table=config.concept_ancestor_table,
            schema=config.schema,
            project_id=config.project_id,
            dataset_id=config.dataset_id,
        )
        measurement_concept_ids_flat = list(
            sorted(
                {
                    int(value)
                    for value in resolved_measurement_df["concept_id"].dropna().tolist()
                }
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
    concept_table_name = _resolve_sql_table_name(
        config.concept_table,
        schema=config.schema,
        project_id=config.project_id,
        dataset_id=config.dataset_id,
    )

    if not drug_concept_id_values:
        return (
            pd.DataFrame(columns=["person_id", "index_date"]),
            {},
            pd.DataFrame(columns=["lab_name", "concept_id"]),
        )

    drug_ids_sql = ", ".join(str(int(value)) for value in drug_concept_id_values)
    exposure_query = f"""
        SELECT person_id, MIN(drug_exposure_start_datetime) AS index_date
        FROM {exposure_table}
        WHERE drug_concept_id IN ({drug_ids_sql})
        GROUP BY person_id
    """
    exposure = execute_sql(conn, exposure_query)
    if exposure.empty:
        return (
            pd.DataFrame(columns=["person_id", "index_date"]),
            {},
            pd.DataFrame(columns=["lab_name", "concept_id"]),
        )

    exposure = _drop_duplicate_rows(
        exposure[["person_id", "index_date"]], ["person_id", "index_date"]
    )
    exposure = (
        exposure.sort_values(["person_id", "index_date"])
        .groupby("person_id", as_index=False)
        .first()
    )
    cohort = exposure.copy()
    stats["exposed"] = len(cohort)

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

    stats["after_prior_liver_dx"] = len(cohort)
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
                   m.measurement_date,
                   m.measurement_concept_id,
                   m.value_as_number,
                   m.unit_concept_id,
                   coalesce(uc.concept_name, 'Missing') AS unit_name,
                   m.range_low,
                   m.range_high,
                   c.index_date
            FROM {measurement_table_name} m
            INNER JOIN cohort c
                ON m.person_id = c.person_id
            LEFT JOIN {concept_table_name} uc
                ON m.unit_concept_id = uc.concept_id
            WHERE m.measurement_concept_id IN ({lab_ids_sql})
              AND m.value_as_number IS NOT NULL
        """
        baseline = execute_sql(conn, baseline_query)
        if not baseline.empty:
            baseline = baseline.merge(
                resolved_measurement_df[["lab_name", "concept_id"]],
                left_on="measurement_concept_id",
                right_on="concept_id",
                how="left",
            )
            bl_group = (
                baseline.groupby(
                    ["lab_name", "concept_id", "unit_name"], as_index=False
                )
                .agg(
                    rcount=("value_as_number", "size"),
                    min_val=("value_as_number", "min"),
                    max_val=("value_as_number", "max"),
                    avg_val=("value_as_number", "mean"),
                )
                .sort_values(["lab_name", "rcount"], ascending=[True, False])
            )
            abnormal = baseline[
                (
                    (baseline["lab_name"] == "ast")
                    & (
                        (
                            (baseline["index_date"] > baseline["measurement_datetime"])
                            & (baseline["value_as_number"] >= 3 * LAB_ULN["ast"])
                        )
                        | (
                            ~baseline["unit_name"]
                            .str.lower()
                            .isin(
                                [
                                    "unit per liter",
                                    "no matching concept",
                                    "missing",
                                    "iu/l",
                                    "international unit per liter",
                                    "u/l",
                                ]
                            )
                        )
                    )
                )
                | (
                    (baseline["lab_name"] == "alt")
                    & (
                        (
                            (baseline["index_date"] > baseline["measurement_datetime"])
                            & (baseline["value_as_number"] >= 3 * LAB_ULN["alt"])
                        )
                        | (
                            ~baseline["unit_name"]
                            .str.lower()
                            .isin(
                                [
                                    "unit per liter",
                                    "no matching concept",
                                    "unit per liter",
                                    "missing",
                                    "iu/l",
                                    "international unit per liter",
                                    "u/l",
                                ]
                            )
                        )
                    )
                )
                | (
                    (baseline["lab_name"] == "bilirubin")
                    & (
                        (
                            (baseline["index_date"] > baseline["measurement_datetime"])
                            & (baseline["value_as_number"] >= 2 * LAB_ULN["bilirubin"])
                        )
                        | (
                            ~baseline["unit_name"]
                            .str.lower()
                            .isin(
                                [
                                    "milligram per deciliter",
                                    "no matching concept",
                                    "missing",
                                ]
                            )
                        )
                    )
                )
            ].copy()
            excluded_people = set(abnormal["person_id"].unique())
            cohort = cohort[~cohort["person_id"].isin(excluded_people)].copy()
    stats["after_abnormal_liver_tests"] = len(cohort)

    if person_table_name:
        person_query = f"""
            SELECT
                p.person_id,
                p.year_of_birth,
                sg.concept_name AS sex_at_birth,
                rc.concept_name AS race,
                ec.concept_name AS ethnicity
            FROM {person_table_name} p
            LEFT JOIN {concept_table_name} sg
                ON p.gender_concept_id = sg.concept_id
            LEFT JOIN {concept_table_name} rc
                ON p.race_concept_id = rc.concept_id
            LEFT JOIN {concept_table_name} ec
                ON p.ethnicity_concept_id = ec.concept_id
            WHERE p.person_id IN (
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
        measurement_cohort_query = f"""
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
                   m.measurement_date,
                   m.measurement_concept_id,
                   m.value_as_number,
                   m.unit_concept_id,
                   coalesce(uc.concept_name, 'Missing') AS unit_name,
                   m.range_low,
                   m.range_high,
                   c.index_date
            FROM {measurement_table_name} m
            INNER JOIN cohort c
                ON m.person_id = c.person_id
            LEFT JOIN {concept_table_name} uc
                ON m.unit_concept_id = uc.concept_id
            WHERE m.measurement_concept_id IN ({lab_ids_sql})
              AND m.value_as_number IS NOT NULL
        """
        measurement_cohort = execute_sql(conn, measurement_cohort_query)
        measurement_cohort = measurement_cohort.merge(
            resolved_measurement_df[["lab_name", "concept_id"]],
            left_on="measurement_concept_id",
            right_on="concept_id",
            how="left",
        )

    return (
        cohort.reset_index(drop=True),
        measurement_cohort.reset_index(drop=True),
        stats,
    )


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
