-- 03_baseline_covariates.sql
-- Pull simple baseline covariates for the cohort.

SELECT
  p.person_id,
  p.year_of_birth,
  p.sex_at_birth,
  p.race,
  p.ethnicity,
  p.bmi,
  p.smoking_status
FROM person p
WHERE p.person_id IN (
  SELECT DISTINCT person_id FROM {{cohort_table}}
);
