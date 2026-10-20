"""Define liver toxicity phenotypes for a drug exposure cohort."""

from __future__ import annotations

import pandas as pd

from .config import FOLLOWUP_DAYS, LAB_ULN, MED_MEASUREMENT_CONCEPT_IDS


def define_liver_toxicity_outcome(
    cohort: pd.DataFrame,
    measurement: pd.DataFrame,
    outcome_window_days: int = FOLLOWUP_DAYS,
    strict_mode: bool = False,
) -> pd.DataFrame:
    """Create a person-level outcome flag for liver toxicity."""
    req_concepts = set(MED_MEASUREMENT_CONCEPT_IDS.values())
    lab_df = measurement[
        measurement["measurement_concept_id"].isin(req_concepts)
    ].copy()
    lab_df = lab_df.merge(
        cohort[["person_id", "index_date"]], on="person_id", how="inner"
    )
    lab_df = lab_df[
        (lab_df["measurement_datetime"] >= lab_df["index_date"])
        & (
            lab_df["measurement_datetime"]
            <= lab_df["index_date"] + pd.Timedelta(days=outcome_window_days)
        )
    ].copy()

    lab_summary = (
        lab_df.groupby(["person_id", "index_date"], group_keys=False)
        .apply(_summarize_lab_values, include_groups=False)
        .reset_index()
    )

    cohort_out = cohort.merge(lab_summary, on=["person_id", "index_date"], how="left")

    if strict_mode:
        cohort_out["liver_toxicity"] = (
            (cohort_out["max_alt"] >= 3 * LAB_ULN["alt"])
            & (cohort_out["max_bilirubin"] >= 2 * LAB_ULN["bilirubin"])
        ).astype(int)
    else:
        cohort_out["liver_toxicity"] = (
            (
                (cohort_out["max_alt"] >= 3 * LAB_ULN["alt"])
                | (cohort_out["max_ast"] >= 3 * LAB_ULN["ast"])
            )
            | (cohort_out["max_bilirubin"] >= 2 * LAB_ULN["bilirubin"])
            | (
                (cohort_out["max_alp"] > LAB_ULN["alp"])
                & (cohort_out["max_bilirubin"] >= 2 * LAB_ULN["bilirubin"])
            )
        ).astype(int)

    cohort_out["outcome_date"] = pd.NaT
    mask = cohort_out["liver_toxicity"] == 1
    cols = [
        "first_alt_event_date",
        "first_ast_event_date",
        "first_bili_event_date",
        "first_alp_event_date",
    ]
    cohort_out.loc[mask, "outcome_date"] = cohort_out.loc[mask, cols].min(axis=1)

    return cohort_out


def _summarize_lab_values(group: pd.DataFrame) -> pd.Series:
    """Return the largest observed lab outcome per patient per index date."""
    result = {
        "max_alt": group.loc[
            group["measurement_concept_id"] == MED_MEASUREMENT_CONCEPT_IDS["alt"],
            "value_as_number",
        ].max(),
        "max_ast": group.loc[
            group["measurement_concept_id"] == MED_MEASUREMENT_CONCEPT_IDS["ast"],
            "value_as_number",
        ].max(),
        "max_bilirubin": group.loc[
            group["measurement_concept_id"] == MED_MEASUREMENT_CONCEPT_IDS["bilirubin"],
            "value_as_number",
        ].max(),
        "max_alp": group.loc[
            group["measurement_concept_id"] == MED_MEASUREMENT_CONCEPT_IDS["alp"],
            "value_as_number",
        ].max(),
        "first_alt_event_date": group.loc[
            group["measurement_concept_id"] == MED_MEASUREMENT_CONCEPT_IDS["alt"],
            "measurement_datetime",
        ].min(),
        "first_ast_event_date": group.loc[
            group["measurement_concept_id"] == MED_MEASUREMENT_CONCEPT_IDS["ast"],
            "measurement_datetime",
        ].min(),
        "first_bili_event_date": group.loc[
            group["measurement_concept_id"] == MED_MEASUREMENT_CONCEPT_IDS["bilirubin"],
            "measurement_datetime",
        ].min(),
        "first_alp_event_date": group.loc[
            group["measurement_concept_id"] == MED_MEASUREMENT_CONCEPT_IDS["alp"],
            "measurement_datetime",
        ].min(),
    }
    return pd.Series(result)
