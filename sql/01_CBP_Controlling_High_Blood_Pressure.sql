/* =============================================================================
   File:    01_CBP_Controlling_High_Blood_Pressure.sql
   Measure: CBP - Controlling High Blood Pressure (HEDIS MY 2025)
   Steward: NCQA
   Population: Members 18-85 with hypertension diagnosis.
   Numerator:  Members whose most recent BP during the measurement year is 
               <140/90 mm Hg (both systolic AND diastolic must qualify).
   Reporting:  Administrative + Hybrid (we use Administrative here).

   Denominator method:
     Two outpatient/telehealth/e-visit visits with HTN diagnosis (I10) on
     different dates of service between Jan 1 of the year prior to the 
     measurement period and June 30 of the measurement period.

   Required exclusions:
     - Hospice / palliative care any time during MY (ICD-10 Z51.5)
     - Members in long-term care (not modeled here)
     - Members who died during MY (not modeled here)

   Why MedPOINT cares: CBP is a Medicare STAR triple-weighted measure. 
     A 1% movement in CBP can swing IPA pay-for-performance bonuses 
     significantly because hypertension prevalence is so high.
   ============================================================================= */
USE MedPOINT_HEDIS;
GO

DECLARE @MP_START DATE = '2025-01-01',
        @MP_END   DATE = '2025-12-31',
        @DX_WINDOW_START DATE = '2024-01-01',
        @DX_WINDOW_END   DATE = '2025-06-30';

WITH 
-- Step 1: Identify members with at least 2 HTN diagnoses on different dates
-- in the look-back window. This is the event/diagnosis criterion.
htn_population AS (
    SELECT 
         m.member_id
        ,m.payer_line
        ,m.date_of_birth
        ,DATEDIFF(YEAR, m.date_of_birth, @MP_END) AS age
    FROM dbo.members m
    JOIN dbo.diagnosis_claims dx 
      ON dx.member_id = m.member_id
    WHERE dx.icd10_code = 'I10'
      AND dx.service_date BETWEEN @DX_WINDOW_START AND @DX_WINDOW_END
    GROUP BY 
         m.member_id
        ,m.payer_line
        ,m.date_of_birth
    HAVING COUNT(DISTINCT dx.service_date) >= 2
),

-- Step 2: Apply age requirement (18-85 as of Dec 31 of MY)
age_eligible AS (
    SELECT *
    FROM htn_population
    WHERE age BETWEEN 18 AND 85
),

-- Step 3: Apply required exclusions (hospice/palliative during MY)
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

-- Step 4: Identify the most recent BP reading during the MY for each
-- denominator member. Note: HEDIS rules say if multiple readings same day,
-- use the LOWEST systolic and LOWEST diastolic of the day. We approximate
-- by taking the MIN within service_date.
bp_per_day AS (
    SELECT 
         v.member_id
        ,v.service_date
        ,MIN(v.systolic_bp)  AS sys_low
        ,MIN(v.diastolic_bp) AS dia_low
    FROM dbo.vital_signs v
    JOIN denominator d ON v.member_id = d.member_id
    WHERE v.service_date BETWEEN @MP_START AND @MP_END
    GROUP BY v.member_id, v.service_date
),

most_recent_bp AS (
    SELECT 
         member_id
        ,service_date
        ,sys_low
        ,dia_low
        ,ROW_NUMBER() OVER (
            PARTITION BY member_id 
            ORDER BY service_date DESC
         ) AS rn
    FROM bp_per_day
),

-- Step 5: Numerator - representative BP <140/90
numerator AS (
    SELECT member_id
    FROM most_recent_bp
    WHERE rn = 1
      AND sys_low < 140
      AND dia_low < 90
)

-- ===== Final report ==========================================================
-- Overall rate
SELECT 
     'Overall' AS stratification
    ,COUNT(DISTINCT d.member_id)                                      AS denominator
    ,COUNT(DISTINCT n.member_id)                                      AS numerator
    ,CAST(100.0 * COUNT(DISTINCT n.member_id) 
          / NULLIF(COUNT(DISTINCT d.member_id), 0) AS DECIMAL(5,2))   AS rate_pct
FROM denominator d
LEFT JOIN numerator n ON d.member_id = n.member_id

UNION ALL

-- By payer line (this is what an IPA quality team actually reviews)
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
