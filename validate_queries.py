"""
Validates all 5 HEDIS measure queries against the synthetic data and prints
a single consolidated scorecard.

This is the same logic that will run in SSMS - translated to DuckDB's slightly
different date syntax so we can run it locally without SQL Server.
"""
import duckdb

con = duckdb.connect()
for t in ["members", "enrollment", "diagnosis_claims", "procedure_claims",
          "vital_signs", "pharmacy", "lab_results", "providers", "ncqa_value_sets"]:
    con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_csv_auto('data/{t}.csv')")

# ---------- CBP -----------------------------------------------------
cbp = con.execute("""
WITH htn_population AS (
    SELECT m.member_id, m.payer_line, m.date_of_birth,
           DATEDIFF('year', m.date_of_birth::DATE, '2025-12-31'::DATE) AS age
    FROM members m
    JOIN diagnosis_claims dx ON dx.member_id = m.member_id
    WHERE dx.icd10_code = 'I10'
      AND dx.service_date BETWEEN '2024-01-01' AND '2025-06-30'
    GROUP BY m.member_id, m.payer_line, m.date_of_birth
    HAVING COUNT(DISTINCT dx.service_date) >= 2
),
age_eligible AS (SELECT * FROM htn_population WHERE age BETWEEN 18 AND 85),
hospice_excl AS (
    SELECT DISTINCT member_id FROM diagnosis_claims
    WHERE icd10_code = 'Z51.5' AND service_date BETWEEN '2025-01-01' AND '2025-12-31'
),
denom AS (
    SELECT a.* FROM age_eligible a
    LEFT JOIN hospice_excl h ON a.member_id = h.member_id
    WHERE h.member_id IS NULL
),
bp_per_day AS (
    SELECT v.member_id, v.service_date,
           MIN(v.systolic_bp) AS sys_low, MIN(v.diastolic_bp) AS dia_low
    FROM vital_signs v JOIN denom d ON v.member_id = d.member_id
    WHERE v.service_date BETWEEN '2025-01-01' AND '2025-12-31'
    GROUP BY v.member_id, v.service_date
),
most_recent AS (
    SELECT member_id, sys_low, dia_low,
           ROW_NUMBER() OVER (PARTITION BY member_id ORDER BY service_date DESC) AS rn
    FROM bp_per_day
),
num AS (SELECT member_id FROM most_recent WHERE rn = 1 AND sys_low < 140 AND dia_low < 90)
SELECT 'CBP' AS measure, 'Overall' AS strat,
       COUNT(DISTINCT d.member_id) AS denom,
       COUNT(DISTINCT n.member_id) AS num,
       ROUND(100.0 * COUNT(DISTINCT n.member_id) / NULLIF(COUNT(DISTINCT d.member_id),0), 2) AS rate
FROM denom d LEFT JOIN num n ON d.member_id = n.member_id
UNION ALL
SELECT 'CBP', d.payer_line, COUNT(DISTINCT d.member_id), COUNT(DISTINCT n.member_id),
       ROUND(100.0 * COUNT(DISTINCT n.member_id) / NULLIF(COUNT(DISTINCT d.member_id),0), 2)
FROM denom d LEFT JOIN num n ON d.member_id = n.member_id
GROUP BY d.payer_line
""").df()

# ---------- COL-E ----------------------------------------------------
col = con.execute("""
WITH age_eligible AS (
    SELECT m.member_id, m.payer_line
    FROM members m
    WHERE DATEDIFF('year', m.date_of_birth::DATE, '2025-12-31'::DATE) BETWEEN 46 AND 75
),
hospice_excl AS (
    SELECT DISTINCT member_id FROM diagnosis_claims
    WHERE icd10_code = 'Z51.5' AND service_date BETWEEN '2025-01-01' AND '2025-12-31'
),
denom AS (
    SELECT a.* FROM age_eligible a
    LEFT JOIN hospice_excl h ON a.member_id = h.member_id
    WHERE h.member_id IS NULL
),
qual AS (
    SELECT DISTINCT pc.member_id FROM procedure_claims pc
    JOIN ncqa_value_sets vs ON pc.procedure_code = vs.code 
      AND vs.measure_id = 'COL-E' AND vs.value_set_name = 'Colonoscopy'
    WHERE pc.service_date >= '2016-01-01'
    UNION
    SELECT DISTINCT pc.member_id FROM procedure_claims pc
    JOIN ncqa_value_sets vs ON pc.procedure_code = vs.code
      AND vs.measure_id = 'COL-E' AND vs.value_set_name = 'Flexible Sigmoidoscopy'
    WHERE pc.service_date >= '2021-01-01'
    UNION
    SELECT DISTINCT pc.member_id FROM procedure_claims pc
    JOIN ncqa_value_sets vs ON pc.procedure_code = vs.code
      AND vs.measure_id = 'COL-E' AND vs.value_set_name = 'CT Colonography'
    WHERE pc.service_date >= '2021-01-01'
    UNION
    SELECT DISTINCT pc.member_id FROM procedure_claims pc
    JOIN ncqa_value_sets vs ON pc.procedure_code = vs.code
      AND vs.measure_id = 'COL-E' AND vs.value_set_name = 'sDNA-FIT'
    WHERE pc.service_date >= '2023-01-01'
    UNION
    SELECT DISTINCT pc.member_id FROM procedure_claims pc
    JOIN ncqa_value_sets vs ON pc.procedure_code = vs.code
      AND vs.measure_id = 'COL-E' AND vs.value_set_name = 'FOBT/FIT'
    WHERE pc.service_date BETWEEN '2025-01-01' AND '2025-12-31'
    UNION
    SELECT DISTINCT lr.member_id FROM lab_results lr
    JOIN ncqa_value_sets vs ON lr.loinc_code = vs.code
      AND vs.measure_id = 'COL-E' 
      AND vs.value_set_name IN ('FOBT/FIT Result','sDNA-FIT Result')
    WHERE lr.service_date BETWEEN '2025-01-01' AND '2025-12-31'
)
SELECT 'COL-E' AS measure, 'Overall' AS strat,
       COUNT(DISTINCT d.member_id) AS denom,
       COUNT(DISTINCT q.member_id) AS num,
       ROUND(100.0 * COUNT(DISTINCT q.member_id) / NULLIF(COUNT(DISTINCT d.member_id),0), 2) AS rate
FROM denom d LEFT JOIN qual q ON d.member_id = q.member_id
UNION ALL
SELECT 'COL-E', d.payer_line, COUNT(DISTINCT d.member_id), COUNT(DISTINCT q.member_id),
       ROUND(100.0 * COUNT(DISTINCT q.member_id) / NULLIF(COUNT(DISTINCT d.member_id),0), 2)
FROM denom d LEFT JOIN qual q ON d.member_id = q.member_id
GROUP BY d.payer_line
""").df()

# ---------- CCS-E ---------------------------------------------------
ccs = con.execute("""
WITH age_eligible AS (
    SELECT m.member_id, m.payer_line, m.date_of_birth,
           DATEDIFF('year', m.date_of_birth::DATE, '2025-12-31'::DATE) AS age
    FROM members m
    WHERE m.sex = 'F' AND DATEDIFF('year', m.date_of_birth::DATE, '2025-12-31'::DATE) BETWEEN 24 AND 64
),
hyst_excl AS (
    SELECT DISTINCT pc.member_id FROM procedure_claims pc
    JOIN ncqa_value_sets vs ON pc.procedure_code = vs.code
      AND vs.measure_id = 'CCS-E' AND vs.value_set_name = 'Hysterectomy (Exclusion)'
    UNION
    SELECT DISTINCT member_id FROM diagnosis_claims
    WHERE icd10_code IN ('Z90.710','Z90.712','Q51.5')
),
hospice_excl AS (
    SELECT DISTINCT member_id FROM diagnosis_claims
    WHERE icd10_code = 'Z51.5' AND service_date BETWEEN '2025-01-01' AND '2025-12-31'
),
denom AS (
    SELECT a.* FROM age_eligible a
    LEFT JOIN hyst_excl hx ON a.member_id = hx.member_id
    LEFT JOIN hospice_excl hs ON a.member_id = hs.member_id
    WHERE hx.member_id IS NULL AND hs.member_id IS NULL
),
qual AS (
    SELECT DISTINCT pc.member_id FROM procedure_claims pc
    JOIN ncqa_value_sets vs ON pc.procedure_code = vs.code
      AND vs.measure_id = 'CCS-E' AND vs.value_set_name = 'Cervical Cytology'
    WHERE pc.service_date >= '2023-01-01'
    UNION
    SELECT DISTINCT pc.member_id FROM procedure_claims pc
    JOIN ncqa_value_sets vs ON pc.procedure_code = vs.code
      AND vs.measure_id = 'CCS-E' AND vs.value_set_name = 'hrHPV Test'
    JOIN members m ON pc.member_id = m.member_id
    WHERE pc.service_date >= '2021-01-01'
      AND DATEDIFF('year', m.date_of_birth::DATE, '2025-12-31'::DATE) >= 30
    UNION
    SELECT DISTINCT lr.member_id FROM lab_results lr
    JOIN ncqa_value_sets vs ON lr.loinc_code = vs.code
      AND vs.measure_id = 'CCS-E' AND vs.value_set_name = 'Cervical Cytology Result'
    WHERE lr.service_date >= '2023-01-01'
    UNION
    SELECT DISTINCT lr.member_id FROM lab_results lr
    JOIN ncqa_value_sets vs ON lr.loinc_code = vs.code
      AND vs.measure_id = 'CCS-E' AND vs.value_set_name = 'hrHPV Result'
    JOIN members m ON lr.member_id = m.member_id
    WHERE lr.service_date >= '2021-01-01'
      AND DATEDIFF('year', m.date_of_birth::DATE, '2025-12-31'::DATE) >= 30
)
SELECT 'CCS-E' AS measure, 'Overall' AS strat,
       COUNT(DISTINCT d.member_id) AS denom,
       COUNT(DISTINCT q.member_id) AS num,
       ROUND(100.0 * COUNT(DISTINCT q.member_id) / NULLIF(COUNT(DISTINCT d.member_id),0), 2) AS rate
FROM denom d LEFT JOIN qual q ON d.member_id = q.member_id
UNION ALL
SELECT 'CCS-E', d.payer_line, COUNT(DISTINCT d.member_id), COUNT(DISTINCT q.member_id),
       ROUND(100.0 * COUNT(DISTINCT q.member_id) / NULLIF(COUNT(DISTINCT d.member_id),0), 2)
FROM denom d LEFT JOIN qual q ON d.member_id = q.member_id
GROUP BY d.payer_line
""").df()

# ---------- EED ------------------------------------------------------
eed = con.execute("""
WITH dm_via_claims AS (
    SELECT m.member_id FROM members m
    JOIN diagnosis_claims dx ON dx.member_id = m.member_id
    JOIN ncqa_value_sets vs ON dx.icd10_code = vs.code
      AND vs.measure_id = 'EED' AND vs.value_set_name = 'Diabetes Diagnosis'
    WHERE dx.service_date BETWEEN '2024-01-01' AND '2025-12-31'
      AND dx.claim_type = 'Outpatient'
    GROUP BY m.member_id
    HAVING COUNT(DISTINCT dx.service_date) >= 2
),
dm_via_pharmacy AS (
    SELECT DISTINCT rx.member_id FROM pharmacy rx
    JOIN diagnosis_claims dx ON rx.member_id = dx.member_id
    JOIN ncqa_value_sets vs ON dx.icd10_code = vs.code
      AND vs.measure_id = 'EED' AND vs.value_set_name = 'Diabetes Diagnosis'
    WHERE rx.fill_date BETWEEN '2024-01-01' AND '2025-12-31'
      AND dx.service_date BETWEEN '2024-01-01' AND '2025-12-31'
),
dm_pop AS (SELECT member_id FROM dm_via_claims UNION SELECT member_id FROM dm_via_pharmacy),
age_elig AS (
    SELECT m.member_id, m.payer_line FROM members m
    JOIN dm_pop dp ON m.member_id = dp.member_id
    WHERE DATEDIFF('year', m.date_of_birth::DATE, '2025-12-31'::DATE) BETWEEN 18 AND 75
),
hospice_excl AS (
    SELECT DISTINCT member_id FROM diagnosis_claims
    WHERE icd10_code = 'Z51.5' AND service_date BETWEEN '2025-01-01' AND '2025-12-31'
),
denom AS (
    SELECT a.* FROM age_elig a 
    LEFT JOIN hospice_excl h ON a.member_id = h.member_id
    WHERE h.member_id IS NULL
),
exam_in_my AS (
    SELECT DISTINCT pc.member_id FROM procedure_claims pc
    JOIN ncqa_value_sets vs ON pc.procedure_code = vs.code
      AND vs.measure_id = 'EED' AND vs.value_set_name = 'Retinal Eye Exam'
    JOIN providers prv ON pc.provider_id = prv.provider_id
      AND prv.specialty IN ('Ophthalmology','Optometry')
    WHERE pc.service_date BETWEEN '2025-01-01' AND '2025-12-31'
),
neg_prior AS (
    SELECT DISTINCT member_id FROM procedure_claims
    WHERE procedure_code = '2023F'
      AND service_date BETWEEN '2024-01-01' AND '2024-12-31'
),
qual AS (SELECT member_id FROM exam_in_my UNION SELECT member_id FROM neg_prior)
SELECT 'EED' AS measure, 'Overall' AS strat,
       COUNT(DISTINCT d.member_id) AS denom,
       COUNT(DISTINCT q.member_id) AS num,
       ROUND(100.0 * COUNT(DISTINCT q.member_id) / NULLIF(COUNT(DISTINCT d.member_id),0), 2) AS rate
FROM denom d LEFT JOIN qual q ON d.member_id = q.member_id
UNION ALL
SELECT 'EED', d.payer_line, COUNT(DISTINCT d.member_id), COUNT(DISTINCT q.member_id),
       ROUND(100.0 * COUNT(DISTINCT q.member_id) / NULLIF(COUNT(DISTINCT d.member_id),0), 2)
FROM denom d LEFT JOIN qual q ON d.member_id = q.member_id
GROUP BY d.payer_line
""").df()

# ---------- AWV ------------------------------------------------------
awv = con.execute("""
WITH age_elig AS (
    SELECT m.member_id, m.payer_line FROM members m
    WHERE m.payer_line IN ('MA','MMP')
      AND DATEDIFF('year', m.date_of_birth::DATE, '2025-12-31'::DATE) >= 66
),
ippe_recent AS (
    SELECT DISTINCT member_id FROM procedure_claims
    WHERE procedure_code = 'G0402' 
      AND service_date BETWEEN '2024-01-01' AND '2025-12-31'
),
hospice_excl AS (
    SELECT DISTINCT member_id FROM diagnosis_claims
    WHERE icd10_code = 'Z51.5' AND service_date BETWEEN '2025-01-01' AND '2025-12-31'
),
denom AS (
    SELECT a.* FROM age_elig a
    LEFT JOIN ippe_recent i ON a.member_id = i.member_id
    LEFT JOIN hospice_excl h ON a.member_id = h.member_id
    WHERE i.member_id IS NULL AND h.member_id IS NULL
),
awv_done AS (
    SELECT DISTINCT member_id FROM procedure_claims
    WHERE procedure_code IN ('G0438','G0439')
      AND service_date BETWEEN '2025-01-01' AND '2025-12-31'
)
SELECT 'AWV' AS measure, 'Overall' AS strat,
       COUNT(DISTINCT d.member_id) AS denom,
       COUNT(DISTINCT n.member_id) AS num,
       ROUND(100.0 * COUNT(DISTINCT n.member_id) / NULLIF(COUNT(DISTINCT d.member_id),0), 2) AS rate
FROM denom d LEFT JOIN awv_done n ON d.member_id = n.member_id
UNION ALL
SELECT 'AWV', d.payer_line, COUNT(DISTINCT d.member_id), COUNT(DISTINCT n.member_id),
       ROUND(100.0 * COUNT(DISTINCT n.member_id) / NULLIF(COUNT(DISTINCT d.member_id),0), 2)
FROM denom d LEFT JOIN awv_done n ON d.member_id = n.member_id
GROUP BY d.payer_line
""").df()

import pandas as pd
all_results = pd.concat([cbp, col, ccs, eed, awv], ignore_index=True)

# Format the scorecard
print("=" * 75)
print(" MedPOINT IPA - HEDIS MY 2025 Scorecard (Synthetic Data)")
print("=" * 75)
for measure in ['CBP', 'COL-E', 'CCS-E', 'EED', 'AWV']:
    m_data = all_results[all_results['measure'] == measure]
    print(f"\n{measure}:")
    for _, r in m_data.iterrows():
        strat = str(r['strat']).ljust(10)
        denom = int(r['denom']) if pd.notna(r['denom']) else 0
        num = int(r['num']) if pd.notna(r['num']) else 0
        rate = r['rate'] if pd.notna(r['rate']) else 0.0
        print(f"  {strat}  denom={denom:>5}  num={num:>5}  rate={rate:>6.2f}%")
print("\n" + "=" * 75)

# Save as CSV for the docs
all_results.to_csv('/home/claude/hedis_v2/data/scorecard_results.csv', index=False)
print("\nScorecard saved to data/scorecard_results.csv")
