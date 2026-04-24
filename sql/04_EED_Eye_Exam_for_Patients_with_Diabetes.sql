/* =============================================================================
   File:    04_EED_Eye_Exam_for_Patients_with_Diabetes.sql
   Measure: EED - Eye Exam for Patients with Diabetes (HEDIS MY 2025)
   Steward: NCQA
   Population: Members 18-75 with diabetes (Type 1 or Type 2).
   
   Numerator: A retinal/dilated eye exam by an eye care professional in MY,
              OR a NEGATIVE retinal exam in the year prior (CPT II 2023F).
              The negative-prior-year option is unique to EED and reflects 
              that members without retinopathy can safely defer screening.

   Denominator method (two paths):
     1. Claim/encounter: 2+ outpatient diabetes diagnoses on different dates
        in MY or year prior, OR
     2. Pharmacy: 1+ diabetes diagnosis AND 1+ insulin/oral hypoglycemic fill

   Required exclusions:
     - Gestational diabetes / steroid-induced diabetes (only)
     - Hospice / palliative care during MY
     - Members 66+ in long-term care (not modeled)

   Note on the Hybrid retirement:
   ------------------------------
   In HEDIS MY 2025, NCQA retired the Hybrid Method for EED. It is now 
   Administrative-only, meaning all numerator events come from claims/EHR 
   structured data. No more chart chases for diabetic eye exams.
   ============================================================================= */
USE MedPOINT_HEDIS;
GO

DECLARE @MP_START DATE = '2025-01-01',
        @MP_END   DATE = '2025-12-31',
        @LB_START DATE = '2024-01-01';   -- year prior to MY

WITH
-- Step 1: Diabetes denominator - claim/encounter path
dm_via_claims AS (
    SELECT m.member_id
    FROM dbo.members m
    JOIN dbo.diagnosis_claims dx ON dx.member_id = m.member_id
    JOIN dbo.ncqa_value_sets vs 
      ON dx.icd10_code = vs.code
     AND vs.measure_id = 'EED'
     AND vs.value_set_name = 'Diabetes Diagnosis'
    WHERE dx.service_date BETWEEN @LB_START AND @MP_END
      AND dx.claim_type = 'Outpatient'
    GROUP BY m.member_id
    HAVING COUNT(DISTINCT dx.service_date) >= 2
),

-- Step 1b: Diabetes denominator - pharmacy path 
-- (1+ DM diagnosis AND 1+ diabetes med dispensing event)
dm_via_pharmacy AS (
    SELECT DISTINCT rx.member_id
    FROM dbo.pharmacy rx
    JOIN dbo.diagnosis_claims dx 
      ON rx.member_id = dx.member_id
    JOIN dbo.ncqa_value_sets vs
      ON dx.icd10_code = vs.code
     AND vs.measure_id = 'EED'
     AND vs.value_set_name = 'Diabetes Diagnosis'
    WHERE rx.fill_date BETWEEN @LB_START AND @MP_END
      AND dx.service_date BETWEEN @LB_START AND @MP_END
      -- In real spec, NDC must be in Diabetes Medications value set;
      -- our pharmacy table only contains diabetes meds so any fill counts here
),

dm_population AS (
    SELECT member_id FROM dm_via_claims
    UNION
    SELECT member_id FROM dm_via_pharmacy
),

-- Step 2: Age (18-75)
age_eligible AS (
    SELECT 
         m.member_id
        ,m.payer_line
        ,m.date_of_birth
        ,DATEDIFF(YEAR, m.date_of_birth, @MP_END) AS age
    FROM dbo.members m
    JOIN dm_population dp ON m.member_id = dp.member_id
    WHERE DATEDIFF(YEAR, m.date_of_birth, @MP_END) BETWEEN 18 AND 75
),

-- Step 3: Exclusions

-- 3a. Gestational/steroid-induced diabetes ONLY (member has these but no other DM dx)
gestational_only AS (
    SELECT m.member_id
    FROM dbo.members m
    LEFT JOIN dbo.diagnosis_claims dx_real
      ON m.member_id = dx_real.member_id
     AND dx_real.icd10_code IN (
         SELECT code FROM dbo.ncqa_value_sets 
         WHERE measure_id = 'EED' AND value_set_name = 'Diabetes Diagnosis'
     )
    JOIN dbo.diagnosis_claims dx_excl
      ON m.member_id = dx_excl.member_id
     AND dx_excl.icd10_code IN ('O24.4', 'E09.9')   -- gestational, drug-induced
    WHERE dx_real.member_id IS NULL  -- no real DM dx
),

hospice_excl AS (
    SELECT DISTINCT member_id
    FROM dbo.diagnosis_claims
    WHERE icd10_code = 'Z51.5'
      AND service_date BETWEEN @MP_START AND @MP_END
),

denominator AS (
    SELECT a.*
    FROM age_eligible a
    LEFT JOIN gestational_only g ON a.member_id = g.member_id
    LEFT JOIN hospice_excl     h ON a.member_id = h.member_id
    WHERE g.member_id IS NULL
      AND h.member_id IS NULL
),

-- Step 4: Numerator
-- 4a. Retinal eye exam during MY by an eye care professional
exam_in_my AS (
    SELECT DISTINCT pc.member_id
    FROM dbo.procedure_claims pc
    JOIN dbo.ncqa_value_sets vs
      ON pc.procedure_code = vs.code
     AND vs.measure_id = 'EED'
     AND vs.value_set_name = 'Retinal Eye Exam'
    JOIN dbo.providers prv 
      ON pc.provider_id = prv.provider_id
     AND prv.specialty IN ('Ophthalmology', 'Optometry')
    WHERE pc.service_date BETWEEN @MP_START AND @MP_END
),

-- 4b. Negative retinal exam in PRIOR year (CPT II 2023F)
neg_prior_year AS (
    SELECT DISTINCT pc.member_id
    FROM dbo.procedure_claims pc
    WHERE pc.procedure_code = '2023F'
      AND pc.service_date BETWEEN @LB_START AND DATEADD(DAY, -1, @MP_START)
),

numerator AS (
    SELECT member_id FROM exam_in_my
    UNION
    SELECT member_id FROM neg_prior_year
)

SELECT 
     'Overall' AS stratification
    ,COUNT(DISTINCT d.member_id)                                      AS denominator
    ,COUNT(DISTINCT n.member_id)                                      AS numerator
    ,CAST(100.0 * COUNT(DISTINCT n.member_id) 
          / NULLIF(COUNT(DISTINCT d.member_id), 0) AS DECIMAL(5,2))   AS rate_pct
FROM denominator d
LEFT JOIN numerator n ON d.member_id = n.member_id

UNION ALL

SELECT 
     d.payer_line
    ,COUNT(DISTINCT d.member_id)
    ,COUNT(DISTINCT n.member_id)
    ,CAST(100.0 * COUNT(DISTINCT n.member_id) 
          / NULLIF(COUNT(DISTINCT d.member_id), 0) AS DECIMAL(5,2))
FROM denominator d
LEFT JOIN numerator n ON d.member_id = n.member_id
GROUP BY d.payer_line
ORDER BY stratification;
