/* =============================================================================
   File:    03_CCS_E_Cervical_Cancer_Screening.sql
   Measure: CCS-E - Cervical Cancer Screening (HEDIS MY 2025)
   Steward: NCQA
   Population: Members 21-64 with cervix recommended for routine screening.
   
   Numerator (any of):
     - Cervical cytology (Pap) in MY or 2 prior years (women 21-64)
     - hrHPV test in MY or 4 prior years (women 30-64)
     - Cytology + hrHPV cotesting in MY or 4 prior years (women 30-64)

   Required exclusions:
     - Hysterectomy with no residual cervix (ICD-10 Z90.710 / Q51.5,
       or hysterectomy CPT)
     - Hospice / palliative care during MY
     - Sex assigned at birth = Male (CCS-E uses anatomical inventory, but
       in our claims-based dataset we approximate using sex on file = F)

   Notes on the "-E":
   ------------------
   CCS was renamed CCS-E in MY 2025 when NCQA retired the Administrative
   and Hybrid reporting methods for this measure. Only the ECDS method
   is now used. ECDS lets the numerator pull from EHR data and lab 
   results (LOINC), not just CPT claims.
   ============================================================================= */
USE MedPOINT_HEDIS;
GO

DECLARE @MP_START DATE = '2025-01-01',
        @MP_END   DATE = '2025-12-31';

WITH
-- Step 1: Age + sex eligible
age_eligible AS (
    SELECT 
         m.member_id
        ,m.payer_line
        ,m.sex
        ,m.date_of_birth
        ,DATEDIFF(YEAR, m.date_of_birth, @MP_END) AS age
    FROM dbo.members m
    WHERE m.sex = 'F'
      AND DATEDIFF(YEAR, m.date_of_birth, @MP_END) BETWEEN 24 AND 64
        -- Floor 24 because cytology lookback is 3 years; spec age is 21-64
),

-- Step 2: Exclusions

-- 2a. Hysterectomy (denominator exclusion) - either by procedure or by dx
hysterectomy_excl AS (
    SELECT DISTINCT pc.member_id
    FROM dbo.procedure_claims pc
    JOIN dbo.ncqa_value_sets vs
      ON pc.procedure_code = vs.code 
     AND vs.measure_id = 'CCS-E' 
     AND vs.value_set_name = 'Hysterectomy (Exclusion)'
    UNION
    SELECT DISTINCT dx.member_id
    FROM dbo.diagnosis_claims dx
    WHERE dx.icd10_code IN ('Z90.710', 'Z90.712', 'Q51.5')
),

-- 2b. Hospice during MY
hospice_excl AS (
    SELECT DISTINCT member_id
    FROM dbo.diagnosis_claims
    WHERE icd10_code = 'Z51.5'
      AND service_date BETWEEN @MP_START AND @MP_END
),

denominator AS (
    SELECT a.*
    FROM age_eligible a
    LEFT JOIN hysterectomy_excl hx ON a.member_id = hx.member_id
    LEFT JOIN hospice_excl       hs ON a.member_id = hs.member_id
    WHERE hx.member_id IS NULL
      AND hs.member_id IS NULL
),

-- Step 3: Numerator
qualifying_screen AS (
    -- Cytology (Pap) in MY or 2 prior years - women 21-64
    SELECT DISTINCT pc.member_id, 'Cytology' AS screen_type, pc.service_date
    FROM dbo.procedure_claims pc
    JOIN dbo.ncqa_value_sets vs
      ON pc.procedure_code = vs.code 
     AND vs.measure_id = 'CCS-E' 
     AND vs.value_set_name = 'Cervical Cytology'
    WHERE pc.service_date BETWEEN DATEADD(YEAR, -2, @MP_START) AND @MP_END

    UNION ALL

    -- hrHPV in MY or 4 prior years - women 30-64
    SELECT DISTINCT pc.member_id, 'hrHPV', pc.service_date
    FROM dbo.procedure_claims pc
    JOIN dbo.ncqa_value_sets vs
      ON pc.procedure_code = vs.code 
     AND vs.measure_id = 'CCS-E' 
     AND vs.value_set_name = 'hrHPV Test'
    JOIN dbo.members m ON pc.member_id = m.member_id
    WHERE pc.service_date BETWEEN DATEADD(YEAR, -4, @MP_START) AND @MP_END
      AND DATEDIFF(YEAR, m.date_of_birth, @MP_END) >= 30

    UNION ALL

    -- ECDS path: cytology lab results (LOINC) - even without billed CPT
    SELECT DISTINCT lr.member_id, 'Cytology (lab)', lr.service_date
    FROM dbo.lab_results lr
    JOIN dbo.ncqa_value_sets vs
      ON lr.loinc_code = vs.code 
     AND vs.measure_id = 'CCS-E' 
     AND vs.value_set_name = 'Cervical Cytology Result'
    WHERE lr.service_date BETWEEN DATEADD(YEAR, -2, @MP_START) AND @MP_END

    UNION ALL

    -- ECDS path: hrHPV lab results (LOINC)
    SELECT DISTINCT lr.member_id, 'hrHPV (lab)', lr.service_date
    FROM dbo.lab_results lr
    JOIN dbo.ncqa_value_sets vs
      ON lr.loinc_code = vs.code 
     AND vs.measure_id = 'CCS-E' 
     AND vs.value_set_name = 'hrHPV Result'
    JOIN dbo.members m ON lr.member_id = m.member_id
    WHERE lr.service_date BETWEEN DATEADD(YEAR, -4, @MP_START) AND @MP_END
      AND DATEDIFF(YEAR, m.date_of_birth, @MP_END) >= 30
),

numerator AS (
    SELECT DISTINCT member_id FROM qualifying_screen
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
