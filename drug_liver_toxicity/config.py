"""Configuration placeholders for a drug-specific liver toxicity study."""

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

# Default concept filters to restrict lookups by OMOP domain and common
# vocabulary/standard-concept constraints. These defaults reduce ambiguous
# string matches; they are intentionally conservative but remain overrideable
# via `CohortConfig` when needed for specific datasets.
DRUG_CONCEPT_FILTERS: Mapping[str, Any] = {
    "domain_id": "Drug",
    "vocabulary_id": ("RxNorm",),
    "standard_concept": "S",
    "invalid_reason": "",
}

LIVER_CONCEPT_FILTERS: Mapping[str, Any] = {
    "domain_id": "Condition",
    "vocabulary_id": ("SNOMED",),
    "standard_concept": "S",
    "invalid_reason": "",
}

MEASUREMENT_CONCEPT_FILTERS: Mapping[str, Any] = {
    "domain_id": "Measurement",
    "vocabulary_id": ("LOINC",),
    "standard_concept": "S",
    "invalid_reason": "",
}


@dataclass
class CohortConfig:
    """Configuration for building a drug exposure cohort."""

    drug_name: str = "duloxetine"
    exclude_prior_liver_disease: bool = True
    exclude_baseline_abnormal_liver_tests: bool = True
    drug_exposure_table: str = "drug_exposure"
    condition_occurrence_table: str = "condition_occurrence"
    measurement_table: str = "measurement"
    person_table: str = "person"
    concept_table: str = "concept"
    concept_ancestor_table: str = "concept_ancestor"
    schema: Optional[str] = None
    project_id: Optional[str] = None
    dataset_id: Optional[str] = None
    drug_concept_ids: Optional[Mapping[str, Any]] = None
    liver_condition_concept_ids: Optional[Mapping[str, Any]] = None
    measurement_concept_ids: Optional[Mapping[str, Any]] = None
    drug_concept_filters: Optional[Mapping[str, Any]] = field(
        default_factory=lambda: dict(DRUG_CONCEPT_FILTERS)
    )
    liver_concept_filters: Optional[Mapping[str, Any]] = field(
        default_factory=lambda: dict(LIVER_CONCEPT_FILTERS)
    )
    measurement_concept_filters: Optional[Mapping[str, Any]] = field(
        default_factory=lambda: dict(MEASUREMENT_CONCEPT_FILTERS)
    )
    index_dataset: Optional[str] = None
    project_dataset: Optional[str] = None


@dataclass
class StudyConfig:
    """Project configuration for a drug exposure and liver toxicity study."""

    drug_name: str = "duloxetine"
    drug_concept_ids: tuple[int, ...] = (123456,)
    followup_days: int = 365
    observation_window_days: int = 365


STUDY = StudyConfig()

# Replace these with project-specific concept IDs or table names.
DRUG_CONCEPT_IDS = {
    STUDY.drug_name: STUDY.drug_concept_ids,
}

LIVER_CONDITION_CONCEPT_IDS = {
    "cirrhosis of liver": 200,
    "inflammatory disease of liver": 201,
    "hepatic failure": 202,
    "chronic liver disease": 204,
}

MED_MEASUREMENT_CONCEPT_IDS = {
    "alt": 300,
    "ast": 301,
    "bilirubin": 302,
    "alp": 303,
    "ggt": 304,
}


MEASUREMENT_CONCEPT_CODES = {
    "alt": ("1742-6", "1743-4", "1744-2", "76625-3", "77144-4"),
    "ast": ("30239-8", "88112-8", "1920-8"),
    "bilirubin": ("1975-2"),
    "alp": ("6768-6"),  # "77141-0", "1783-0",
    "ggt": ("2324-2"),
}


# OMOP concept_name values are usually readable lab names rather than the
# shorthand labels used in the study config. Keep canonical aliases so the
# lookup can match the same lab across both naming conventions.
MEASUREMENT_CONCEPT_ALIASES = {
    "alt": (
        "alt",
        "alanine aminotransferase",
        "alanine aminotransferase [enzyme]",
    ),
    "ast": (
        "ast",
        "aspartate aminotransferase",
        "aspartate aminotransferase [enzyme]",
    ),
    "bilirubin": (
        "bilirubin",
        "total bilirubin",
        "bilirubin.total",
    ),
    "alp": (
        "alp",
        "alkaline phosphatase",
        "alkaline phosphatase [enzyme]",
    ),
    "ggt": (
        "ggt",
        "gamma glutamyl transferase",
        "gamma glutamyl transferase [enzyme]",
    ),
}

# Typical lab upper limits of normal (ULN) used in a first pass.
LAB_ULN = {
    "alt": 40,
    "ast": 40,
    "bilirubin": 1.2,
    "alp": 130,
    "ggt": 50,
}

FOLLOWUP_DAYS = STUDY.followup_days
OBSERVATION_WINDOW_DAYS = STUDY.observation_window_days

# Example table names to be replaced in a real ResearchAllOfUs workflow.
TABLE_NAMES = {
    "drug_exposure": "drug_exposure",
    "measurement": "measurement",
    "condition_occurrence": "condition_occurrence",
    "person": "person",
}
