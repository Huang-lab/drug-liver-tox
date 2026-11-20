"""Baseline analysis for a drug-specific liver toxicity cohort."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split

# Columns that are derived from the outcome, or identify a person or a date.  A covariate list that
# names one of these would make the model a restatement of the outcome definition.
NOT_COVARIATES = frozenset(
    {
        "liver_toxicity",
        "outcome_date",
        "person_id",
        "index_date",
        "max_alt",
        "max_ast",
        "max_bilirubin",
        "max_alp",
        "first_alt_event_date",
        "first_ast_event_date",
        "first_bili_event_date",
        "first_alp_event_date",
    }
)


def prepare_analysis_dataset(
    cohort: pd.DataFrame, covariates: list[str]
) -> pd.DataFrame:
    """Prepare the outcome and covariate table for modeling.

    Only the outcome and the named covariates are kept: the model sees nothing else.
    """
    missing = [col for col in covariates if col not in cohort.columns]
    if missing:
        raise ValueError(f"Covariates not in the cohort frame: {missing}")
    forbidden = sorted(set(covariates) & NOT_COVARIATES)
    if forbidden:
        raise ValueError(
            f"Covariates derived from the outcome or identifying a person: {forbidden}"
        )

    df = (
        cohort[["liver_toxicity", *covariates]].dropna(subset=["liver_toxicity"]).copy()
    )

    # Anything that is not numeric or boolean is categorical.  Testing for dtype == "object"
    # misses pandas' string dtype, which is the default for text columns from pandas 3.
    categorical_cols = [
        col
        for col in covariates
        if not pd.api.types.is_numeric_dtype(df[col])
        and not pd.api.types.is_bool_dtype(df[col])
    ]
    df = pd.get_dummies(df, columns=categorical_cols, drop_first=True, dtype=float)

    for col in df.columns:
        if col != "liver_toxicity":
            df[col] = df[col].fillna(df[col].median())

    return df


def run_baseline_model(
    cohort: pd.DataFrame,
    covariates: list[str],
    test_size: float = 0.3,
    random_state: int = 42,
) -> dict:
    """Run a simple logistic regression model for the outcome."""
    if not covariates:
        raise ValueError("run_baseline_model needs at least one covariate.")
    df = prepare_analysis_dataset(cohort, covariates)
    y = df["liver_toxicity"]
    X = df.drop(columns=["liver_toxicity"])

    # Drop columns with no usable variability before modeling.
    X = X.loc[:, X.nunique(dropna=True) > 1]
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.dropna(axis=1)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    X_train = X_train.astype(float)
    X_test = X_test.astype(float)
    X_train = sm.add_constant(X_train)
    X_test = sm.add_constant(X_test)

    if X_train.isnull().any().any() or X_test.isnull().any().any():
        raise ValueError("Model matrix still contains missing values.")

    if len(np.unique(y)) < 2:
        return {
            "auc": float("nan"),
            "average_precision": float("nan"),
            "model": None,
        }

    try:
        model = sm.Logit(y_train, X_train).fit(disp=False)
    except (ValueError, np.linalg.LinAlgError):
        return {
            "auc": float("nan"),
            "average_precision": float("nan"),
            "model": None,
        }

    preds = model.predict(X_test)

    metrics = {
        "auc": roc_auc_score(y_test, preds),
        "average_precision": average_precision_score(y_test, preds),
        "model": model,
    }
    return metrics
