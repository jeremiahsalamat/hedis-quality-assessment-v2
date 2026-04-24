/* =============================================================================
   File:    05_AWV_Annual_Wellness_Visit.sql
   Measure: AWV - Annual Wellness Visit Completion Rate
   Steward: CMS (operational measure, not NCQA-published)
   
   IMPORTANT CONTEXT:
   ------------------
   AWV is NOT a formal NCQA HEDIS measure. It is a Medicare Part B preventive 
   benefit (HCPCS G0438 initial, G0439 subsequent) that IPAs like MedPOINT 
   track internally because:

     1. The AWV is the single best opportunity to CLOSE HEDIS gaps all at once
        (BP capture, cancer screening referrals, depression screening, fall risk,
        advance care planning, SDOH).
     2. AWV completion drives HCC (risk-adjustment) coding accuracy - a primary
        revenue lever for Medicare Advantage risk-bearing entities.
     3. CMS has proposed AWV-related measures for Star Ratings, and many MA
        plans include it in their P4P scorecards for delegated IPAs.

   This query mirrors the logic an IPA would use to report AWV completion to
   its Medicare Advantage health plan partners.

   Population: Members 66+ enrolled in Medicare Advantage (MA) or Medi-Medi (MMP)
               continuously during the measurement year.
               (66+ because Year 1 Medicare members may only be eligible for
               IPPE G0402, not AWV.)

   Numerator: At least one AWV (G0438 OR G0439) during the MY.

   Required exclusions:
     - Hospice/palliative during MY
     - Members who had the IPPE (G0402) in the last 12 months
       (They are not yet eligible for AWV.)
   ============================================================================= */
USE MedPOINT_HEDIS;
GO

-- =============================================================================
-- Part 1: AWV completion rate (overall + by payer line)
-- =============================================================================
DECLARE @MP_START DATE = '2025-01-01',
        @MP_END   DATE = '2025-12-31';

WITH
-- Step 1: MA / Medi-Medi members age 66+ as of Dec 31
age_eligible AS (
    SELECT 
         m.member_id
        ,m.payer_line
        ,m.date_of_birth
        ,DATEDIFF(YEAR, m.date_of_birth, @MP_END) AS age
    FROM dbo.members m
    WHERE m.payer_line IN ('MA', 'MMP')
      AND DATEDIFF(YEAR, m.date_of_birth, @MP_END) >= 66
),

-- Step 2: Exclude members who had the IPPE (G0402) in the last 12 months,
-- because they are not yet AWV-eligible (can't bill G0438 within 12mo of IPPE).
ippe_recent AS (
    SELECT DISTINCT pc.member_id
    FROM dbo.procedure_claims pc
    WHERE pc.procedure_code = 'G0402'
      AND pc.service_date BETWEEN DATEADD(MONTH, -12, @MP_START) AND @MP_END
),

-- Step 3: Hospice exclusion
hospice_excl AS (
    SELECT DISTINCT member_id
    FROM dbo.diagnosis_claims
    WHERE icd10_code = 'Z51.5'
      AND service_date BETWEEN @MP_START AND @MP_END
),

denominator AS (
    SELECT a.*
    FROM age_eligible a
    LEFT JOIN ippe_recent   i ON a.member_id = i.member_id
    LEFT JOIN hospice_excl  h ON a.member_id = h.member_id
    WHERE i.member_id IS NULL
      AND h.member_id IS NULL
),

-- Step 4: Numerator - AWV billed during MY
awv_done AS (
    SELECT DISTINCT pc.member_id
    FROM dbo.procedure_claims pc
    WHERE pc.procedure_code IN ('G0438', 'G0439')
      AND pc.service_date BETWEEN @MP_START AND @MP_END
)

-- Overall + by payer report
SELECT 
     'Overall' AS stratification
    ,COUNT(DISTINCT d.member_id)                                      AS denominator
    ,COUNT(DISTINCT n.member_id)                                      AS numerator
    ,CAST(100.0 * COUNT(DISTINCT n.member_id) 
          / NULLIF(COUNT(DISTINCT d.member_id), 0) AS DECIMAL(5,2))   AS rate_pct
FROM denominator d
LEFT JOIN awv_done n ON d.member_id = n.member_id

UNION ALL

SELECT 
     d.payer_line
    ,COUNT(DISTINCT d.member_id)
    ,COUNT(DISTINCT n.member_id)
    ,CAST(100.0 * COUNT(DISTINCT n.member_id) 
          / NULLIF(COUNT(DISTINCT d.member_id), 0) AS DECIMAL(5,2))
FROM denominator d
LEFT JOIN awv_done n ON d.member_id = n.member_id
GROUP BY d.payer_line
ORDER BY stratification;
GO

-- =============================================================================
-- Part 2: Supplemental - AWV visit-type breakdown
-- Initial (G0438) vs Subsequent (G0439) among members who completed an AWV
-- =============================================================================
DECLARE @MP_START2 DATE = '2025-01-01',
        @MP_END2   DATE = '2025-12-31';

WITH awv_type AS (
    SELECT 
         pc.member_id
        ,MAX(CASE WHEN pc.procedure_code = 'G0438' THEN 1 ELSE 0 END) AS had_initial
        ,MAX(CASE WHEN pc.procedure_code = 'G0439' THEN 1 ELSE 0 END) AS had_subsequent
    FROM dbo.procedure_claims pc
    WHERE pc.procedure_code IN ('G0438', 'G0439')
      AND pc.service_date BETWEEN @MP_START2 AND @MP_END2
    GROUP BY pc.member_id
)
SELECT 
     'Initial AWV only (G0438)'      AS awv_category
    ,SUM(CASE WHEN t.had_initial = 1 AND t.had_subsequent = 0 THEN 1 ELSE 0 END) AS n_members
FROM awv_type t
UNION ALL
SELECT 'Subsequent AWV only (G0439)',
       SUM(CASE WHEN t.had_initial = 0 AND t.had_subsequent = 1 THEN 1 ELSE 0 END)
FROM awv_type t
UNION ALL
SELECT 'Both initial + subsequent in MY',
       SUM(CASE WHEN t.had_initial = 1 AND t.had_subsequent = 1 THEN 1 ELSE 0 END)
FROM awv_type t;
