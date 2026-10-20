-- 02_define_liver_toxicity.sql
-- Define a liver toxicity phenotype using ALT, AST, bilirubin, and ALP.

WITH cohort AS (
  SELECT person_id, index_date
  FROM {{cohort_table}}
),
lab_values AS (
  SELECT
    c.person_id,
    c.index_date,
    m.measurement_datetime,
    m.measurement_concept_id,
    m.value_as_number
  FROM cohort c
  JOIN measurement m
    ON c.person_id = m.person_id
  WHERE m.measurement_datetime >= c.index_date
    AND m.measurement_datetime <= DATEADD(day, 365, c.index_date)
    AND m.measurement_concept_id IN (
      300, 301, 302, 303 -- ALT, AST, bilirubin, ALP
    )
),
lab_summary AS (
  SELECT
    person_id,
    index_date,
    MAX(CASE WHEN measurement_concept_id = 300 THEN value_as_number END) AS max_alt,
    MAX(CASE WHEN measurement_concept_id = 301 THEN value_as_number END) AS max_ast,
    MAX(CASE WHEN measurement_concept_id = 302 THEN value_as_number END) AS max_bilirubin,
    MAX(CASE WHEN measurement_concept_id = 303 THEN value_as_number END) AS max_alp
  FROM lab_values
  GROUP BY person_id, index_date
)
SELECT
  c.person_id,
  c.index_date,
  CASE
    WHEN (ls.max_alt >= 3 * 40 OR ls.max_ast >= 3 * 40)
      OR ls.max_bilirubin >= 2 * 1.2
      OR (ls.max_alp > 130 AND ls.max_bilirubin >= 2 * 1.2)
      THEN 1
    ELSE 0
  END AS liver_toxicity
FROM cohort c
LEFT JOIN lab_summary ls
  ON c.person_id = ls.person_id
 AND c.index_date = ls.index_date;
