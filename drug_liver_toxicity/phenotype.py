"""Define liver toxicity phenotypes for a drug exposure cohort."""

from __future__ import annotations

import pandas as pd

from .config import FOLLOWUP_DAYS, LAB_ULN


def define_liver_toxicity_outcome(
    cohort: pd.DataFrame,
    lab_df: pd.DataFrame,
    outcome_window_days: int = FOLLOWUP_DAYS,
    strict_mode: bool = False,
) -> pd.DataFrame:
    """Create a person-level outcome flag for liver toxicity."""
    lab_df = lab_df[
        (lab_df["measurement_datetime"] >= lab_df["index_date"])
        & (
            lab_df["measurement_datetime"]
            <= lab_df["index_date"] + pd.Timedelta(days=outcome_window_days)
        )
    ].copy()

    lab_summary = (
        lab_df.groupby(["person_id", "index_date"], group_keys=False)
        .apply(
            lambda g: _summarize_lab_values(g),
            include_groups=False,
        )
        .reset_index()
    )

    cohort_out = cohort.merge(
        lab_summary,
        on=["person_id", "index_date"],
        how="left",
    )

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

    cohort_out["outcome_date"] = cohort_out.apply(
        lambda row: _determine_outcome_date(row, strict_mode=strict_mode),
        axis=1,
    )

    return cohort_out


def _determine_outcome_date(
    row: pd.Series,
    strict_mode: bool,
) -> pd.Timestamp | None:
    """Return first date that met the toxicity rule."""
    if row["liver_toxicity"] != 1:
        return None

    alt_date = row["first_alt_event_date"]
    ast_date = row["first_ast_event_date"]
    bili_date = row["first_bili_event_date"]
    alp_date = row["first_alp_event_date"]

    if strict_mode:
        if pd.notna(alt_date) and pd.notna(bili_date):
            return max(alt_date, bili_date)
        return None

    candidate_dates: list[pd.Timestamp] = []
    if pd.notna(alt_date):
        candidate_dates.append(alt_date)
    if pd.notna(ast_date):
        candidate_dates.append(ast_date)
    if pd.notna(bili_date):
        candidate_dates.append(bili_date)
    if pd.notna(alp_date) and pd.notna(bili_date):
        candidate_dates.append(max(alp_date, bili_date))

    if not candidate_dates:
        return None
    return min(candidate_dates)


def _summarize_lab_values(
    group: pd.DataFrame,
) -> pd.Series:
    """Return values and first threshold-crossing dates per patient."""
    alt = group.loc[group["lab_name"] == "alt"]
    ast = group.loc[group["lab_name"] == "ast"]
    bilirubin = group.loc[group["lab_name"] == "bilirubin"]
    alp = group.loc[group["lab_name"] == "alp"]

    result = {
        "max_alt": alt["value_as_number"].max(),
        "max_ast": ast["value_as_number"].max(),
        "max_bilirubin": bilirubin["value_as_number"].max(),
        "max_alp": alp["value_as_number"].max(),
        "first_alt_event_date": alt.loc[
            alt["value_as_number"] >= 3 * LAB_ULN["alt"],
            "measurement_datetime",
        ].min(),
        "first_ast_event_date": ast.loc[
            ast["value_as_number"] >= 3 * LAB_ULN["ast"],
            "measurement_datetime",
        ].min(),
        "first_bili_event_date": bilirubin.loc[
            bilirubin["value_as_number"] >= 2 * LAB_ULN["bilirubin"],
            "measurement_datetime",
        ].min(),
        "first_alp_event_date": alp.loc[
            alp["value_as_number"] > LAB_ULN["alp"],
            "measurement_datetime",
        ].min(),
    }
    return pd.Series(result)
