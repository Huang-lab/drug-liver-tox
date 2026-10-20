# Drug Liver Toxicity Starter Project

This repository contains a starter workflow for building a drug-exposure cohort and testing whether liver toxicity is associated with a target drug, genetic variation, or protein biomarkers.

## Project layout

- `drug_liver_toxicity/` — reusable Python package for cohort building, phenotype definition, and baseline modeling
- `drug_liver_toxicity_notebook.ipynb` — a notebook entry point
- `sql/` — SQL templates for OMOP-style extraction logic
- `pyproject.toml` — editable install configuration

## Configuration

Edit the study metadata in `drug_liver_toxicity/config.py`:

- `STUDY.drug_name`
- `STUDY.drug_concept_ids`
- `FOLLOWUP_DAYS`
- `LAB_ULN`

This keeps the code generic enough to be reused with other drugs.

## Typical workflow

1. Define the target drug concept set.
2. Build the exposed cohort.
3. Exclude baseline liver disease and abnormal liver tests.
4. Define the liver toxicity outcome.
5. Add covariates and run a baseline model.
6. Merge genetic or protein data.
7. Validate findings across sensitivity analyses.

## Example usage

```python
from drug_liver_toxicity.cohort import build_drug_cohort
from drug_liver_toxicity.phenotype import define_liver_toxicity_outcome
from drug_liver_toxicity.analysis import run_baseline_model
```

## Notes

- Replace placeholder concept IDs with the appropriate values from your study schema.
- The initial workflow is intentionally broad and conservative to support later genetic/protein discovery work.
- The notebook and modules are meant to be extended, not treated as final production-ready analysis code.
