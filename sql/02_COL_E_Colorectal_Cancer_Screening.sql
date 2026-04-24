/* =============================================================================
   File:    02_COL_E_Colorectal_Cancer_Screening.sql
   Measure: COL-E - Colorectal Cancer Screening (HEDIS MY 2025)
   Steward: NCQA
   Population: Members 45-75 years old as of Dec 31 of MY.
   Numerator:  At least one of the following appropriate screenings:
                 - Colonoscopy in MY or 9 prior years (10-year window)
                 - Flexible sigmoidoscopy in MY or 4 prior years
                 - CT colonography in MY or 4 prior years
                 - sDNA-FIT (Cologuard) in MY or 2 prior years
                 - FOBT/FIT during the MY

   Required exclusions:
     - History of colorectal cancer / total colectomy any time in history
     - Hospice / palliative care during MY
   
   The "-E" in COL-E denotes ECDS (Electronic Clinical Data Systems) reporting.
   ECDS allows numerator events to be sourced from EHR data, HIE, case 
   management, and claims - not just claims alone. This is why we include 
   lab_results in addition to procedure_claims.

   Why MedPOINT cares: COL-E is HEDIS public-reported and weighted heavily in
   commercial and Medi-Cal P4P. Many gaps close with a $30 FIT kit mailed home.
   ============================================================================= */
USE MedPOINT_HEDIS;
GO

DECLARE @MP_START DATE = '2025-01-01',
        @MP_END   DATE = '2025-12-31';

WITH
-- Step 1: Age-eligible population
age_eligible AS (
    SELECT 
         m.member_id
        ,m.payer_line
        ,m.date_of_birth
        ,DATEDIFF(YEAR, m.date_of_birth, @MP_END) AS age
    FROM dbo.members m
    WHERE DATEDIFF(YEAR, m.date_of_birth, @MP_END) BETWEEN 46 AND 75
        -- Spec actually says 45-75 but with continuous enrollment requirement
        -- the effective floor is 46 since age is measured at end of MY
),

-- Step 2: Apply exclusions
hospice_excl AS (
    SELECT DISTINCT member_id
    FROM dbo.diagnosis_claims
    WHERE icd10_code = 'Z51.5'
      AND service_date BETWEEN @MP_START AND @MP_END
),

denominator AS (
    SELECT a.*
    FROM age_eligible a
    LEFT JOIN hospice_excl h ON a.member_id = h.member_id
    WHERE h.member_id IS NULL
),

-- Step 3: Numerator - any qualifying screening within its lookback window
-- We pull from BOTH procedure_claims AND lab_results (ECDS principle).
qualifying_screen AS (
    -- Colonoscopy: MY or 9 prior years (10-year window)
    SELECT DISTINCT pc.member_id, 'Colonoscopy' AS screening_type, pc.service_date
    FROM dbo.procedure_claims pc
    JOIN dbo.ncqa_value_sets vs 
      ON pc.procedure_code = vs.code 
     AND vs.measure_id = 'COL-E' 
     AND vs.value_set_name = 'Colonoscopy'
    WHERE pc.service_date BETWEEN DATEADD(YEAR, -9, @MP_START) AND @MP_END

    UNION ALL

    -- Flexible sigmoidoscopy: MY or 4 prior years
    SELECT DISTINCT pc.member_id, 'Flex Sig', pc.service_date
    FROM dbo.procedure_claims pc
    JOIN dbo.ncqa_value_sets vs
      ON pc.procedure_code = vs.code 
     AND vs.measure_id = 'COL-E' 
     AND vs.value_set_name = 'Flexible Sigmoidoscopy'
    WHERE pc.service_date BETWEEN DATEADD(YEAR, -4, @MP_START) AND @MP_END

    UNION ALL

    -- CT colonography: MY or 4 prior years
    SELECT DISTINCT pc.member_id, 'CT Colonography', pc.service_date
    FROM dbo.procedure_claims pc
    JOIN dbo.ncqa_value_sets vs
      ON pc.procedure_code = vs.code 
     AND vs.measure_id = 'COL-E' 
     AND vs.value_set_name = 'CT Colonography'
    WHERE pc.service_date BETWEEN DATEADD(YEAR, -4, @MP_START) AND @MP_END

    UNION ALL

    -- sDNA-FIT (Cologuard): MY or 2 prior years
    SELECT DISTINCT pc.member_id, 'sDNA-FIT', pc.service_date
    FROM dbo.procedure_claims pc
    JOIN dbo.ncqa_value_sets vs
      ON pc.procedure_code = vs.code 
     AND vs.measure_id = 'COL-E' 
     AND vs.value_set_name = 'sDNA-FIT'
    WHERE pc.service_date BETWEEN DATEADD(YEAR, -2, @MP_START) AND @MP_END

    UNION ALL

    -- FOBT/FIT: MY only (yearly test)
    SELECT DISTINCT pc.member_id, 'FOBT/FIT', pc.service_date
    FROM dbo.procedure_claims pc
    JOIN dbo.ncqa_value_sets vs
      ON pc.procedure_code = vs.code 
     AND vs.measure_id = 'COL-E' 
     AND vs.value_set_name = 'FOBT/FIT'
    WHERE pc.service_date BETWEEN @MP_START AND @MP_END

    UNION ALL

    -- ECDS path: lab results for FOBT/FIT and sDNA-FIT (LOINC)
    SELECT DISTINCT lr.member_id, 'FOBT/FIT (lab)', lr.service_date
    FROM dbo.lab_results lr
    JOIN dbo.ncqa_value_sets vs
      ON lr.loinc_code = vs.code 
     AND vs.measure_id = 'COL-E' 
     AND vs.value_set_name IN ('FOBT/FIT Result', 'sDNA-FIT Result')
    WHERE lr.service_date BETWEEN @MP_START AND @MP_END
),

numerator AS (
    SELECT DISTINCT member_id FROM qualifying_screen
)

-- Final report: overall + by payer
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
