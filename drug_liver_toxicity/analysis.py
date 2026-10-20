"""Baseline analysis for a drug-specific liver toxicity cohort."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split


def prepare_analysis_dataset(
    cohort: pd.DataFrame, covariates: list[str]
) -> pd.DataFrame:
    """Prepare the outcome and covariate table for modeling."""
    df = cohort.copy()
    df = df.dropna(subset=["liver_toxicity"]).copy()

    categorical_cols = [col for col in covariates if df[col].dtype == "object"]
    df = pd.get_dummies(df, columns=categorical_cols, drop_first=True)

    numeric_cols = list(df.select_dtypes(include="number").columns)
    for col in numeric_cols:
        df[col] = df[col].fillna(df[col].median())

    return df


def run_baseline_model(
    cohort: pd.DataFrame,
    covariates: list[str],
    test_size: float = 0.3,
    random_state: int = 42,
) -> dict:
    """Run a simple logistic regression model for the outcome."""
    df = prepare_analysis_dataset(cohort, covariates)
    y = df["liver_toxicity"]
    pred_cols = [
        c
        for c in df.columns
        if c not in {"liver_toxicity", "outcome_date"}
        and pd.api.types.is_numeric_dtype(df[c])
    ]
    X = df[pred_cols]

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
