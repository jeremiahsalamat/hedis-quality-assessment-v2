# HEDIS Quality Assessment v2

A SQL project that calculates five HEDIS measures (COL-E, CCS-E, CBP, EED, AWV) from synthetic claims, EHR, and pharmacy data. Built to practice the kind of quality measurement work that IPAs like MedPOINT Management do for their Medicare Advantage, Medi-Cal, and Commercial lines of business.

## Background

I'm transitioning into healthcare data analytics from store operations. After building a simpler HEDIS project as a first pass at the domain, I wanted a second version that went deeper: real NCQA codes, multiple payer lines, the denominator/exclusion/numerator pattern that every HEDIS measure follows, and a pipeline diagram showing how raw data becomes a report table.

The dataset is synthetic. I generated it to have the right shape (age distributions, HTN prevalence, screening rates, etc.) so the SQL produces rates comparable to published national averages. All diagnosis, procedure, and lab codes used in the measure logic are real NCQA HEDIS MY 2025 codes pulled from public specifications.

## The five measures

| Code  | Name                                | Population       |
|-------|-------------------------------------|------------------|
| COL-E | Colorectal Cancer Screening         | 45-75            |
| CCS-E | Cervical Cancer Screening           | Women 21-64      |
| CBP   | Controlling High Blood Pressure     | 18-85 w/ HTN     |
| EED   | Eye Exam for Patients with Diabetes | 18-75 w/ DM      |
| AWV   | Annual Wellness Visit (Medicare)    | 66+ on MA/MMP    |

### Why the "-E" on some of them

COL-E and CCS-E are reported via NCQA's ECDS (Electronic Clinical Data Systems) standard. ECDS lets numerator events come from structured EHR data (lab results with LOINC codes, HIE feeds) in addition to claims. NCQA has been moving measures to ECDS one at a time. COL went ECDS-only in MY 2024. CCS followed in MY 2025.

EED doesn't carry the "-E" suffix. Its Hybrid Method was retired in MY 2025 in favor of Administrative-only reporting (claims and structured data), not ECDS.

CBP is a bit of a special case. In MY 2025, NCQA added a new ECDS measure called BPC-E (Blood Pressure Control for Patients with Hypertension) that is intended to eventually replace CBP. For now, both coexist: CBP continues with its Hybrid/Admin reporting and the lowest-of-day BP logic, while BPC-E uses ECDS and the most-recent-of-day logic. This project implements the CBP logic since most plans still report both in parallel.

## Repo layout

```
hedis_quality_assessment_v2/
├── README.md
├── generate_data.py          # builds the synthetic dataset
├── validate_queries.py       # runs all 5 measures in DuckDB, prints scorecard
├── data/                     # 9 CSVs
├── sql/                      # SQL Server scripts (CBP, COL-E, CCS-E, EED, AWV)
└── diagrams/                 # pipeline flowchart (SVG + PNG)
```

## How to run it

### SQL Server (main path)

1. Open `sql/00_schema_and_load.sql` in SSMS, run it to create the database and tables.
2. In that same file, uncomment the BULK INSERT block and point it at your local `data/` folder. Run the BULK INSERTs.
3. Run any of the measure scripts (`01_CBP...` through `05_AWV...`).

### DuckDB (quick local validation)

```bash
pip install duckdb pandas
python3 generate_data.py      # regenerates the CSVs (seeded, so deterministic)
python3 validate_queries.py   # runs all 5 measures and prints the scorecard
```

## Sample output

```
CBP (Controlling High Blood Pressure)
  Overall     denom= 539  num= 333  rate= 61.78%
  Commercial  denom= 172  num= 117  rate= 68.02%
  Medi-Cal    denom= 186  num= 106  rate= 56.99%
  Medicare    denom= 111  num=  65  rate= 58.56%
  Medi-Medi   denom=  47  num=  29  rate= 61.70%
  Exchange    denom=  23  num=  16  rate= 69.57%

COL-E   denom=1225  num=591  rate=48.2%
CCS-E   denom= 651  num=414  rate=63.6%
EED     denom= 227  num=173  rate=76.2%
AWV     denom= 849  num=459  rate=54.1%
```

These rates line up with published national HEDIS averages (CBP 60-65%, COL-E 50-56%, CCS 65-70%).

## What I learned building it

- The denominator/exclusion/numerator pattern really is the same for every HEDIS measure once you get past the specific codes. The hard part is the exclusions, not the numerator.
- "Most recent BP" for CBP means the LOWEST systolic and LOWEST diastolic of the most recent day, not just the reading closest to Dec 31. This is the kind of rule that tanks rates if you get it wrong.
- ECDS changes how you think about numerator logic. Instead of only checking claim tables, you UNION in lab results keyed on LOINC.
- Integer division in SQL Server burns you every time. `100 * num / denom` gives zero when both are ints; `100.0 * num / denom` doesn't.
- Continuous enrollment is the gate that comes before every measure. If a member wasn't enrolled the whole year, they shouldn't be in the denominator.

## HEDIS terms used in this repo

- **MY**: Measurement Year. MY 2025 covers Jan 1 - Dec 31, 2025.
- **Continuous enrollment**: member must be enrolled through the whole MY (with a small allowable gap).
- **Eligible population**: members meeting age/sex/event criteria, before exclusions.
- **Required exclusions**: members NCQA says must be removed (hospice, hysterectomy for CCS, etc.).
- **Denominator**: eligible population minus required exclusions.
- **Numerator**: denominator members who actually got the service within the right window.
- **Rate**: `numerator / denominator * 100`. Usually stratified by payer line.
- **STARs**: CMS Medicare Advantage rating program. HEDIS measures feed Stars scores which drive MA bonus payments.
- **P4P**: Pay-for-Performance. Health plans pay IPAs bonus dollars when HEDIS rates hit target tiers.
- **ECDS**: Electronic Clinical Data Systems. NCQA's newer reporting standard that accepts EHR data.

## Data note

All patient data is synthetic. I wrote a Python generator (`generate_data.py`) that creates members, enrollment, claims, vitals, pharmacy, and labs with realistic distributions and foreign key integrity. The NCQA value sets in `ncqa_value_sets.csv` use real published codes from NCQA HEDIS MY 2025 specifications. I used AI assistance for the data generation and SQL scaffolding, then verified the measure logic against NCQA technical specifications and real-world HEDIS tip sheets from multiple plans (Molina, BCBS, Aetna, Health Net).

## Built by

Jeremiah Salamat · [github.com/jeremiahsalamat](https://github.com/jeremiahsalamat)
