import numpy as np
import pandas as pd
import pytest

from drug_liver_toxicity.analysis import prepare_analysis_dataset, run_baseline_model
from drug_liver_toxicity.phenotype import define_liver_toxicity_outcome


def noise_cohort(n=600, seed=7, string_dtype=False):
    """Covariates are generated independently of the outcome, so a model that sees only them cannot beat chance."""
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.08).astype(int)
    max_alt = np.where(y == 1, rng.uniform(150, 400, n), rng.uniform(15, 80, n))
    sex = rng.choice(["F", "M"], n)
    frame = pd.DataFrame(
        {
            "person_id": np.arange(n),
            "year_of_birth": rng.integers(1940, 2001, n),
            "sex_at_birth": pd.Series(sex, dtype="string" if string_dtype else object),
            "max_alt": max_alt,
            "liver_toxicity": y,
        }
    )
    return frame


def test_the_model_sees_only_the_named_covariates():
    out = run_baseline_model(
        noise_cohort(), covariates=["year_of_birth", "sex_at_birth"]
    )
    assert list(out["model"].params.index) == [
        "const",
        "year_of_birth",
        "sex_at_birth_M",
    ]


def test_noise_covariates_do_not_beat_chance_even_when_outcome_defining_columns_are_in_the_frame():
    out = run_baseline_model(
        noise_cohort(), covariates=["year_of_birth", "sex_at_birth"]
    )
    assert out["auc"] < 0.75  # the leaky version reports 1.0 on this frame


def test_a_covariate_derived_from_the_outcome_is_refused():
    with pytest.raises(ValueError, match="derived from the outcome"):
        run_baseline_model(noise_cohort(), covariates=["year_of_birth", "max_alt"])


def test_a_person_identifier_is_refused_as_a_covariate():
    with pytest.raises(ValueError, match="identifying a person"):
        prepare_analysis_dataset(noise_cohort(), ["person_id"])


def test_a_covariate_missing_from_the_frame_is_an_error():
    with pytest.raises(ValueError, match="not in the cohort frame"):
        prepare_analysis_dataset(noise_cohort(), ["ethnicity"])


def test_no_covariates_is_an_error_not_a_model_of_nothing():
    with pytest.raises(ValueError, match="at least one covariate"):
        run_baseline_model(noise_cohort(), covariates=[])


@pytest.mark.parametrize("string_dtype", [False, True])
def test_text_covariates_are_encoded_whatever_their_dtype(string_dtype):
    df = prepare_analysis_dataset(
        noise_cohort(string_dtype=string_dtype), ["year_of_birth", "sex_at_birth"]
    )
    assert "sex_at_birth_M" in df.columns
    assert "sex_at_birth" not in df.columns


def test_missing_numeric_covariates_are_imputed_with_the_median():
    frame = noise_cohort()
    frame.loc[0, "year_of_birth"] = np.nan
    df = prepare_analysis_dataset(frame, ["year_of_birth"])
    assert df["year_of_birth"].notna().all()
    assert df.loc[0, "year_of_birth"] == frame["year_of_birth"].median()


def test_rows_without_an_outcome_are_dropped():
    frame = noise_cohort()
    frame["liver_toxicity"] = frame["liver_toxicity"].astype(float)
    frame.loc[:9, "liver_toxicity"] = np.nan
    assert len(prepare_analysis_dataset(frame, ["year_of_birth"])) == len(frame) - 10


def test_every_column_the_outcome_step_adds_is_refused_as_a_covariate():
    """Tie the refused list to what define_liver_toxicity_outcome really adds to the frame."""
    index = pd.Timestamp("2020-01-01")
    cohort = pd.DataFrame(
        {"person_id": [1, 2], "index_date": index, "year_of_birth": [1970, 1980]}
    )
    labs = pd.DataFrame(
        {
            "person_id": [1, 1, 1, 1, 2, 2, 2, 2],
            "index_date": index,
            "measurement_datetime": index + pd.Timedelta(days=30),
            "lab_name": ["alt", "ast", "bilirubin", "alp"] * 2,
            "value_as_number": [250.0, 200.0, 3.0, 400.0, 20.0, 20.0, 0.5, 80.0],
        }
    )
    out = define_liver_toxicity_outcome(cohort, labs, outcome_window_days=365)
    added = [col for col in out.columns if col not in cohort.columns]
    assert {"liver_toxicity", "outcome_date", "max_alt", "first_alt_event_date"} <= set(
        added
    )
    for name in added:
        with pytest.raises(ValueError):
            prepare_analysis_dataset(out, ["year_of_birth", name])
