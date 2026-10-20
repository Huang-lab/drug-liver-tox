-- 01_build_exposure_cohort.sql
-- Build a drug exposure cohort for a target drug.
-- This is a template for OMOP-style data and should be adapted to your schema.

WITH target_drug_concepts AS (
  SELECT concept_id
  FROM concept
  WHERE concept_id IN (
    -- Replace with actual target drug concept IDs
    123456,
    234567
  )
),
exposed_patients AS (
  SELECT
    de.person_id,
    MIN(de.drug_exposure_start_datetime) AS index_date
  FROM drug_exposure de
  JOIN target_drug_concepts tdc
    ON de.drug_concept_id = tdc.concept_id
  WHERE de.drug_exposure_start_datetime IS NOT NULL
  GROUP BY de.person_id
),
prior_liver_disease AS (
  SELECT DISTINCT person_id
  FROM condition_occurrence co
  WHERE co.condition_start_datetime < (
    SELECT MIN(index_date) FROM exposed_patients
  )
    AND co.condition_concept_id IN (
      -- cirrhosis, hepatitis, chronic liver disease concept IDs
      200, 201, 202, 203, 204
    )
),
final_cohort AS (
  SELECT e.person_id, e.index_date
  FROM exposed_patients e
  LEFT JOIN prior_liver_disease pld
    ON e.person_id = pld.person_id
  WHERE pld.person_id IS NULL
)
SELECT *
FROM final_cohort;
