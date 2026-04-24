"""
Synthetic HEDIS dataset generator for MedPOINT-style IPA.

Generates 9 interconnected CSV files representing:
- Members enrolled across multiple payer lines
- Providers (PCPs and specialists)
- Enrollment history (continuous enrollment is critical for HEDIS)
- Diagnosis claims (ICD-10) 
- Procedure claims (CPT/HCPCS)
- Lab results (LOINC)
- Pharmacy fills
- Vital signs (BP readings)
- Reference: NCQA value sets

Designed to support 5 HEDIS measures: COL-E, CCS-E, CBP, EED, AWV
All codes are REAL NCQA-published codes from MY 2025/2026 specs.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)  # reproducible
OUT = Path("/home/claude/hedis_v2/data")
OUT.mkdir(parents=True, exist_ok=True)

# Measurement period: MY 2025 (Jan 1 - Dec 31, 2025)
MP_START = date(2025, 1, 1)
MP_END = date(2025, 12, 31)
LOOKBACK_START = date(2015, 1, 1)  # 10 years for colonoscopy lookback

# ------------------------------------------------------------------
# REAL NCQA VALUE SETS (subset, sufficient for the project)
# ------------------------------------------------------------------

# Hypertension diagnoses (Essential HTN value set)
ICD10_HTN = ["I10"]

# Diabetes diagnoses (Diabetes value set, abbreviated)
ICD10_DM = [
    "E11.9",   # Type 2 DM without complications - most common
    "E11.65",  # Type 2 DM with hyperglycemia
    "E11.21",  # Type 2 DM with diabetic nephropathy
    "E11.22",  # Type 2 DM with CKD
    "E10.9",   # Type 1 DM without complications
    "E11.40",  # Type 2 DM with neuropathy
    "E11.319", # Type 2 DM with unspec retinopathy
]

# Diabetes exclusions (gestational/steroid-induced)
ICD10_DM_EXCL = ["O24.4", "E09.9"]  # Gestational, drug-induced

# CRC screening procedures (CPT) - Colonoscopy / FIT / sDNA
CPT_COLONOSCOPY = ["44388", "44389", "44392", "44394", "45378", "45380", "45384", "45385", "45388"]
CPT_FOBT = ["82270", "82274"]  # gFOBT, FIT
CPT_SDNA_FIT = ["81528"]       # Cologuard
CPT_FLEX_SIG = ["45330", "45331", "45333", "45338", "45346"]
CPT_CT_COLON = ["74261", "74262", "74263"]
LOINC_FOBT = ["12503-9", "14563-1", "14564-9", "14565-6"]  # FIT/FOBT results
LOINC_SDNA = ["77353-1"]       # sDNA-FIT result

# Cervical cancer screening (CCS-E)
CPT_CYTOLOGY = ["88141", "88142", "88143", "88147", "88148", "88150",
                "88152", "88153", "88164", "88165", "88166", "88167",
                "88174", "88175"]
CPT_HRHPV = ["87624", "87625"]
LOINC_CERVICAL_CYTOLOGY = ["10524-7", "18500-9", "19762-4", "19764-0", "19765-7", "33717-0"]
LOINC_HPV = ["59263-4", "59264-2", "71431-1", "75694-0", "77379-6", "77399-4", "77400-0"]

# Cervical cancer exclusion (hysterectomy with no residual cervix)
ICD10_HYST = ["Z90.710", "Z90.712", "Q51.5"]
CPT_HYST = ["51925", "56308", "57540", "57545", "57550", "57555", "57556",
            "58150", "58152", "58200", "58210", "58240", "58260", "58262",
            "58263", "58267", "58270", "58275", "58280", "58285", "58290",
            "58291", "58292", "58293", "58294", "58548", "58550", "58552",
            "58553", "58554", "58570", "58571", "58572", "58573"]

# Diabetic eye exam (EED)
CPT_RETINAL_EXAM = ["67028", "67030", "67031", "67036", "67039", "67040",
                    "67041", "67042", "67043", "67101", "67105", "67107",
                    "67108", "67110", "67113", "67121", "67141", "67145",
                    "67208", "67210", "67218", "67220", "67221", "67227",
                    "67228", "92002", "92004", "92012", "92014", "92018",
                    "92019", "92134", "92201", "92202", "92225", "92226",
                    "92227", "92228", "92229", "92230", "92235", "92240",
                    "92250", "92260", "99203", "99204", "99205", "99213",
                    "99214", "99215", "99242", "99243", "99244", "99245"]
CPT_II_EYE = ["2022F", "2023F", "2024F", "2025F", "2026F", "2033F"]  # CPT II codes
LOINC_RETINAL = ["32451-7", "71484-0"]

# BP CPT II codes (CBP measure)
CPT_II_BP_SYS_LT_140 = ["3074F", "3075F"]   # systolic <130, 130-139
CPT_II_BP_DIA_LT_90 = ["3078F", "3079F"]    # diastolic <80, 80-89
CPT_II_BP_SYS_GE_140 = ["3077F"]            # systolic >=140
CPT_II_BP_DIA_GE_90 = ["3080F"]             # diastolic >=90
LOINC_BP_SYS = "8480-6"
LOINC_BP_DIA = "8462-4"

# Annual Wellness Visit (HCPCS)
HCPCS_AWV = ["G0438", "G0439"]  # initial / subsequent
HCPCS_IPPE = ["G0402"]           # Welcome to Medicare

# Outpatient visit codes (used as event criteria for many measures)
CPT_OUTPATIENT = ["99202", "99203", "99204", "99205",
                  "99211", "99212", "99213", "99214", "99215",
                  "99381", "99382", "99383", "99384", "99385", "99386", "99387",
                  "99391", "99392", "99393", "99394", "99395", "99396", "99397"]

# Hospice / Palliative (universal exclusion)
ICD10_HOSPICE = ["Z51.5"]
HCPCS_HOSPICE = ["G9054", "G9473", "G9474", "Q5001", "Q5002", "Q5003",
                 "Q5004", "Q5005", "Q5006", "Q5007", "Q5008", "Q5009", "Q5010"]

# Diabetes meds (insulin / hypoglycemic for diabetes denominator via pharmacy)
NDC_DIABETES_MED = [
    ("0002-7510-01", "Insulin Glargine 100 U/mL"),
    ("0173-0717-01", "Metformin 500mg"),
    ("0173-0719-13", "Metformin 1000mg"),
    ("0006-0117-31", "Sitagliptin 100mg"),
    ("0024-5851-30", "Empagliflozin 10mg"),
    ("0078-0526-15", "Semaglutide 0.5mg/dose"),
]

# ------------------------------------------------------------------
# PROVIDER POOL
# ------------------------------------------------------------------
PROVIDER_SPECIALTIES = [
    ("Family Medicine", "PCP"),
    ("Internal Medicine", "PCP"),
    ("Geriatrics", "PCP"),
    ("Gastroenterology", "Specialist"),
    ("OB/GYN", "Specialist"),
    ("Ophthalmology", "Specialist"),
    ("Optometry", "Specialist"),
    ("Cardiology", "Specialist"),
    ("Endocrinology", "Specialist"),
]

LAST_NAMES = ["Nguyen", "Garcia", "Johnson", "Patel", "Kim", "Smith", "Lopez",
              "Chen", "Williams", "Singh", "Hernandez", "Martinez", "Wong",
              "Khan", "Davis", "Brown", "Anderson", "Thompson", "Lee", "Sharma"]
FIRST_NAMES_F = ["Maria", "Linda", "Priya", "Aisha", "Jennifer", "Sarah", "Emily",
                 "Mei", "Rosa", "Fatima", "Anna", "Grace", "Olivia", "Sophia"]
FIRST_NAMES_M = ["David", "Michael", "James", "Carlos", "Hiroshi", "Robert",
                 "Daniel", "Wei", "Juan", "Ahmed", "John", "William", "Noah", "Liam"]

def generate_providers(n=50):
    providers = []
    for i in range(1, n + 1):
        spec, role = random.choice(PROVIDER_SPECIALTIES)
        first = random.choice(FIRST_NAMES_F + FIRST_NAMES_M)
        last = random.choice(LAST_NAMES)
        providers.append({
            "provider_id": f"PRV{i:04d}",
            "npi": f"1{random.randint(100000000, 999999999)}",
            "first_name": first,
            "last_name": last,
            "specialty": spec,
            "provider_type": role,
            "active_flag": "Y",
        })
    return providers

# ------------------------------------------------------------------
# MEMBER POPULATION
# ------------------------------------------------------------------
PAYER_LINES = [
    ("COMM", "Commercial HMO", 0.30),
    ("MCAL", "Medi-Cal Managed Care", 0.30),
    ("MA",   "Medicare Advantage", 0.25),
    ("MMP",  "Medi-Medi (D-SNP)", 0.10),
    ("EXCH", "Covered California", 0.05),
]

def weighted_payer():
    r = random.random()
    cum = 0.0
    for code, name, w in PAYER_LINES:
        cum += w
        if r <= cum:
            return code
    return PAYER_LINES[-1][0]

def random_dob_for_age(age, ref=MP_END):
    yrs = ref - timedelta(days=age * 365 + random.randint(0, 364))
    return yrs

def generate_members(n=2500):
    members = []
    for i in range(1, n + 1):
        payer = weighted_payer()
        # Age targeted to populate measure denominators
        if payer in ("MA", "MMP"):
            age = random.randint(66, 89)
        else:
            # spread across ages so we hit CCS (21-64), CBP (18-85), COL (45-75), EED (18-75)
            age = random.choices(
                [random.randint(18, 20), random.randint(21, 44),
                 random.randint(45, 64), random.randint(65, 75)],
                weights=[0.05, 0.40, 0.40, 0.15]
            )[0]

        sex = random.choices(["F", "M"], weights=[0.55, 0.45])[0]
        first = random.choice(FIRST_NAMES_F if sex == "F" else FIRST_NAMES_M)
        last = random.choice(LAST_NAMES)
        dob = random_dob_for_age(age)

        # Race/ethnicity (rough LA County distribution)
        race_eth = random.choices(
            ["Hispanic", "White", "Asian", "Black", "Other", "Unknown"],
            weights=[0.48, 0.26, 0.15, 0.07, 0.03, 0.01]
        )[0]

        # PCP assignment (PCP only)
        members.append({
            "member_id": f"MBR{i:06d}",
            "first_name": first,
            "last_name": last,
            "date_of_birth": dob.isoformat(),
            "sex": sex,
            "race_ethnicity": race_eth,
            "payer_line": payer,
            "primary_language": random.choices(
                ["English", "Spanish", "Tagalog", "Vietnamese", "Korean", "Mandarin", "Armenian"],
                weights=[0.45, 0.35, 0.05, 0.05, 0.04, 0.03, 0.03]
            )[0],
            "zip_code": random.choice(["91367", "91364", "91335", "91406", "91411",
                                       "90004", "90019", "90029", "91201", "91331"]),
        })
    return members

# ------------------------------------------------------------------
# ENROLLMENT (continuous enrollment is the gateway to all HEDIS measures)
# ------------------------------------------------------------------
def generate_enrollment(members, providers):
    pcps = [p for p in providers if p["provider_type"] == "PCP"]
    enrollment = []
    eid = 1
    for m in members:
        # 85% have continuous coverage all of MY 2025
        if random.random() < 0.85:
            start = MP_START - timedelta(days=random.randint(180, 1800))
            end = MP_END + timedelta(days=random.randint(0, 365))
        else:
            # gap or partial enrollment - will fail continuous enrollment check
            start = date(2025, random.randint(2, 8), random.randint(1, 28))
            end = MP_END
        pcp = random.choice(pcps)
        enrollment.append({
            "enrollment_id": f"ENR{eid:07d}",
            "member_id": m["member_id"],
            "payer_line": m["payer_line"],
            "coverage_start_date": start.isoformat(),
            "coverage_end_date": end.isoformat(),
            "pcp_provider_id": pcp["provider_id"],
        })
        eid += 1
    return enrollment

# ------------------------------------------------------------------
# DIAGNOSIS CLAIMS
# ------------------------------------------------------------------
def random_date_in(start, end):
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))

def generate_diagnosis_claims(members, providers):
    """
    Assign diagnoses such that:
    - ~30% of adults 18-85 have HTN (drives CBP)
    - ~10% of adults 18-75 have DM (drives EED)
    - small % of women have hysterectomy (CCS exclusion)
    - small % have hospice/palliative (universal exclusion)
    """
    pcps = [p for p in providers if p["provider_type"] == "PCP"]
    specs = [p for p in providers if p["provider_type"] == "Specialist"]
    claims = []
    cid = 1

    for m in members:
        age = (MP_END - date.fromisoformat(m["date_of_birth"])).days // 365

        # HTN
        if 18 <= age <= 85 and random.random() < 0.30:
            # Need >=2 outpatient visits with HTN dx for CBP denominator
            for _ in range(random.choice([2, 2, 3, 4])):
                dx_date = random_date_in(date(2024, 1, 1), MP_END)
                claims.append({
                    "claim_id": f"DX{cid:08d}",
                    "member_id": m["member_id"],
                    "provider_id": random.choice(pcps)["provider_id"],
                    "service_date": dx_date.isoformat(),
                    "icd10_code": random.choice(ICD10_HTN),
                    "claim_type": "Outpatient",
                    "place_of_service": "11",
                })
                cid += 1

        # Diabetes
        if 18 <= age <= 75 and random.random() < 0.12:
            # Need 2+ diabetes dx OR 1 dx + diabetes med (we'll add the med later)
            for _ in range(random.choice([1, 2, 2, 3])):
                dx_date = random_date_in(date(2024, 1, 1), MP_END)
                claims.append({
                    "claim_id": f"DX{cid:08d}",
                    "member_id": m["member_id"],
                    "provider_id": random.choice(pcps + specs)["provider_id"],
                    "service_date": dx_date.isoformat(),
                    "icd10_code": random.choice(ICD10_DM),
                    "claim_type": "Outpatient",
                    "place_of_service": "11",
                })
                cid += 1

        # Hysterectomy diagnosis (CCS-E exclusion) - rare
        if m["sex"] == "F" and age >= 35 and random.random() < 0.04:
            dx_date = random_date_in(date(2018, 1, 1), MP_END)
            claims.append({
                "claim_id": f"DX{cid:08d}",
                "member_id": m["member_id"],
                "provider_id": random.choice(specs)["provider_id"],
                "service_date": dx_date.isoformat(),
                "icd10_code": random.choice(ICD10_HYST),
                "claim_type": "Outpatient",
                "place_of_service": "11",
            })
            cid += 1

        # Hospice (universal exclusion) - very rare
        if age >= 65 and random.random() < 0.02:
            dx_date = random_date_in(MP_START, MP_END)
            claims.append({
                "claim_id": f"DX{cid:08d}",
                "member_id": m["member_id"],
                "provider_id": random.choice(pcps)["provider_id"],
                "service_date": dx_date.isoformat(),
                "icd10_code": random.choice(ICD10_HOSPICE),
                "claim_type": "Outpatient",
                "place_of_service": "11",
            })
            cid += 1

        # Background outpatient visits (gives most members visit history)
        # Weighted to mimic real primary care claim distributions.
        n_visits = random.choices([0, 1, 2, 3, 4, 5], weights=[0.05, 0.15, 0.25, 0.25, 0.20, 0.10])[0]
        for _ in range(n_visits):
            dx_date = random_date_in(MP_START, MP_END)
            bg_code = random.choices(
                [
                    "Z00.00",   # General adult exam w/o abnormal findings
                    "Z23",      # Encounter for immunization
                    "J06.9",    # Acute URI, unspecified
                    "J20.9",    # Acute bronchitis
                    "J45.909",  # Unspecified asthma, uncomplicated
                    "K21.9",    # GERD without esophagitis
                    "K59.00",   # Constipation, unspecified
                    "M54.50",   # Low back pain, unspecified
                    "M25.511",  # Pain in right shoulder
                    "M79.3",    # Panniculitis, unspecified
                    "M17.11",   # Osteoarthritis of right knee
                    "R51.9",    # Headache, unspecified
                    "R10.9",    # Unspecified abdominal pain
                    "R05.9",    # Cough, unspecified
                    "R07.9",    # Chest pain, unspecified
                    "R53.83",   # Other fatigue
                    "N39.0",    # UTI, site not specified
                    "E78.5",    # Hyperlipidemia, unspecified
                    "E66.9",    # Obesity, unspecified
                    "F41.9",    # Anxiety disorder, unspecified
                    "F32.9",    # Major depressive disorder, single episode
                    "G47.00",   # Insomnia, unspecified
                    "H52.13",   # Myopia, bilateral
                    "L70.0",    # Acne vulgaris
                    "H66.90",   # Otitis media, unspecified
                ],
                weights=[
                    8, 3, 9, 5, 4, 7, 3, 8, 4, 2, 5,    # Z00 through M17 
                    6, 6, 5, 4, 4,                       # R51 through R53
                    4, 7, 6, 6, 5, 4, 3, 2, 3            # N39 through H66
                ]
            )[0]
            claims.append({
                "claim_id": f"DX{cid:08d}",
                "member_id": m["member_id"],
                "provider_id": random.choice(pcps)["provider_id"],
                "service_date": dx_date.isoformat(),
                "icd10_code": bg_code,
                "claim_type": "Outpatient",
                "place_of_service": "11",
            })
            cid += 1

    return claims

# ------------------------------------------------------------------
# PROCEDURE CLAIMS (CPT/HCPCS)
# ------------------------------------------------------------------
def generate_procedure_claims(members, providers, dx_claims):
    """
    Generate procedures for screenings and AWVs.
    Compliance rates roughly mirror national HEDIS averages so the queries
    produce realistic results (CCS ~60%, COL ~55%, EED ~65%, CBP ~60%, AWV ~50%).
    """
    pcps = [p for p in providers if p["provider_type"] == "PCP"]
    gi = [p for p in providers if p["specialty"] == "Gastroenterology"]
    obgyn = [p for p in providers if p["specialty"] == "OB/GYN"]
    eyes = [p for p in providers if p["specialty"] in ("Ophthalmology", "Optometry")]

    # Index members by id for quick lookup
    dm_members = set()
    htn_members = set()
    hyst_members = set()
    hospice_members = set()
    for c in dx_claims:
        if c["icd10_code"] in ICD10_DM:
            dm_members.add(c["member_id"])
        if c["icd10_code"] in ICD10_HTN:
            htn_members.add(c["member_id"])
        if c["icd10_code"] in ICD10_HYST:
            hyst_members.add(c["member_id"])
        if c["icd10_code"] in ICD10_HOSPICE:
            hospice_members.add(c["member_id"])

    procs = []
    pid = 1

    for m in members:
        age = (MP_END - date.fromisoformat(m["date_of_birth"])).days // 365
        mid = m["member_id"]

        # ---- COL-E: Colorectal Cancer Screening (45-75) ----
        if 45 <= age <= 75 and mid not in hospice_members:
            r = random.random()
            if r < 0.30:
                # Colonoscopy in last 10 years
                proc_date = random_date_in(LOOKBACK_START, MP_END)
                procs.append({
                    "procedure_id": f"PR{pid:08d}",
                    "member_id": mid,
                    "provider_id": random.choice(gi)["provider_id"],
                    "service_date": proc_date.isoformat(),
                    "code_system": "CPT",
                    "procedure_code": random.choice(CPT_COLONOSCOPY),
                    "place_of_service": "22",
                })
                pid += 1
            elif r < 0.45:
                # FIT/FOBT in measurement year
                proc_date = random_date_in(MP_START, MP_END)
                procs.append({
                    "procedure_id": f"PR{pid:08d}",
                    "member_id": mid,
                    "provider_id": random.choice(pcps)["provider_id"],
                    "service_date": proc_date.isoformat(),
                    "code_system": "CPT",
                    "procedure_code": random.choice(CPT_FOBT),
                    "place_of_service": "11",
                })
                pid += 1
            elif r < 0.52:
                # sDNA-FIT (Cologuard) in last 3 years
                proc_date = random_date_in(date(2023, 1, 1), MP_END)
                procs.append({
                    "procedure_id": f"PR{pid:08d}",
                    "member_id": mid,
                    "provider_id": random.choice(pcps)["provider_id"],
                    "service_date": proc_date.isoformat(),
                    "code_system": "CPT",
                    "procedure_code": CPT_SDNA_FIT[0],
                    "place_of_service": "11",
                })
                pid += 1

        # ---- CCS-E: Cervical Cancer Screening (21-64, female) ----
        if m["sex"] == "F" and 21 <= age <= 64 and mid not in hyst_members and mid not in hospice_members:
            r = random.random()
            if r < 0.40 and age >= 30:
                # hrHPV in last 5 years
                proc_date = random_date_in(date(2021, 1, 1), MP_END)
                procs.append({
                    "procedure_id": f"PR{pid:08d}",
                    "member_id": mid,
                    "provider_id": random.choice(obgyn + pcps)["provider_id"],
                    "service_date": proc_date.isoformat(),
                    "code_system": "CPT",
                    "procedure_code": random.choice(CPT_HRHPV),
                    "place_of_service": "11",
                })
                pid += 1
            elif r < 0.65:
                # Cytology in last 3 years
                proc_date = random_date_in(date(2023, 1, 1), MP_END)
                procs.append({
                    "procedure_id": f"PR{pid:08d}",
                    "member_id": mid,
                    "provider_id": random.choice(obgyn + pcps)["provider_id"],
                    "service_date": proc_date.isoformat(),
                    "code_system": "CPT",
                    "procedure_code": random.choice(CPT_CYTOLOGY),
                    "place_of_service": "11",
                })
                pid += 1

        # ---- EED: Eye Exam for Patients with Diabetes ----
        if mid in dm_members and 18 <= age <= 75 and mid not in hospice_members:
            r = random.random()
            if r < 0.55:
                # Eye exam in MY
                proc_date = random_date_in(MP_START, MP_END)
                procs.append({
                    "procedure_id": f"PR{pid:08d}",
                    "member_id": mid,
                    "provider_id": random.choice(eyes)["provider_id"],
                    "service_date": proc_date.isoformat(),
                    "code_system": "CPT",
                    "procedure_code": random.choice(CPT_RETINAL_EXAM),
                    "place_of_service": "11",
                })
                pid += 1
            elif r < 0.70:
                # Negative retinal exam in prior year (also numerator-compliant)
                proc_date = random_date_in(date(2024, 1, 1), date(2024, 12, 31))
                procs.append({
                    "procedure_id": f"PR{pid:08d}",
                    "member_id": mid,
                    "provider_id": random.choice(eyes)["provider_id"],
                    "service_date": proc_date.isoformat(),
                    "code_system": "CPT-II",
                    "procedure_code": "2023F",  # Negative retinal exam
                    "place_of_service": "11",
                })
                pid += 1

        # ---- AWV: Annual Wellness Visit (Medicare/Medi-Medi) ----
        if m["payer_line"] in ("MA", "MMP") and age >= 66 and mid not in hospice_members:
            if random.random() < 0.55:
                proc_date = random_date_in(MP_START, MP_END)
                procs.append({
                    "procedure_id": f"PR{pid:08d}",
                    "member_id": mid,
                    "provider_id": random.choice(pcps)["provider_id"],
                    "service_date": proc_date.isoformat(),
                    "code_system": "HCPCS",
                    "procedure_code": random.choice(HCPCS_AWV),
                    "place_of_service": "11",
                })
                pid += 1

        # Universal: hysterectomy procedures (CCS exclusion, alt path)
        if mid in hyst_members and random.random() < 0.6:
            proc_date = random_date_in(date(2018, 1, 1), MP_END)
            procs.append({
                "procedure_id": f"PR{pid:08d}",
                "member_id": mid,
                "provider_id": random.choice(obgyn)["provider_id"],
                "service_date": proc_date.isoformat(),
                "code_system": "CPT",
                "procedure_code": random.choice(CPT_HYST),
                "place_of_service": "22",
            })
            pid += 1

    return procs

# ------------------------------------------------------------------
# VITAL SIGNS (for CBP)
# ------------------------------------------------------------------
def generate_vitals(members, dx_claims):
    """
    Generate BP readings for HTN members.
    ~62% will have most-recent reading <140/90 (numerator compliant).
    """
    pcps_with_visit = {}
    for c in dx_claims:
        if c["icd10_code"] in ICD10_HTN:
            pcps_with_visit.setdefault(c["member_id"], []).append(c)

    vitals = []
    vid = 1
    for mid, dx_list in pcps_with_visit.items():
        # 1-4 BP readings per HTN member during MY
        n_readings = random.randint(1, 4)
        # Decide if member is "controlled" (most recent <140/90)
        controlled = random.random() < 0.62
        readings_dates = sorted([random_date_in(MP_START, MP_END) for _ in range(n_readings)])

        for i, d in enumerate(readings_dates):
            is_last = (i == len(readings_dates) - 1)
            if is_last and controlled:
                sys_bp = random.randint(110, 138)
                dia_bp = random.randint(65, 88)
            elif is_last and not controlled:
                sys_bp = random.randint(140, 168)
                dia_bp = random.randint(85, 100)
            else:
                sys_bp = random.randint(120, 160)
                dia_bp = random.randint(75, 95)

            vitals.append({
                "vital_id": f"VT{vid:08d}",
                "member_id": mid,
                "service_date": d.isoformat(),
                "loinc_systolic": LOINC_BP_SYS,
                "systolic_bp": sys_bp,
                "loinc_diastolic": LOINC_BP_DIA,
                "diastolic_bp": dia_bp,
                "provider_id": dx_list[0]["provider_id"],
                "place_of_service": "11",
            })
            vid += 1
    return vitals

# ------------------------------------------------------------------
# PHARMACY (diabetes meds + a few hypertensives for realism)
# ------------------------------------------------------------------
def generate_pharmacy(members, dx_claims):
    dm_members = {c["member_id"] for c in dx_claims if c["icd10_code"] in ICD10_DM}
    pharmacy = []
    rxid = 1
    # 70% of DM members get at least one diabetes med (also creates additional
    # pharmacy-data path into diabetes denominator for members with only 1 dx)
    for mid in dm_members:
        if random.random() < 0.70:
            n_fills = random.randint(2, 8)
            ndc, name = random.choice(NDC_DIABETES_MED)
            for _ in range(n_fills):
                fill_date = random_date_in(date(2024, 6, 1), MP_END)
                pharmacy.append({
                    "rx_id": f"RX{rxid:08d}",
                    "member_id": mid,
                    "fill_date": fill_date.isoformat(),
                    "ndc_code": ndc,
                    "drug_name": name,
                    "days_supply": random.choice([30, 30, 60, 90]),
                    "quantity": random.choice([30, 60, 90]),
                })
                rxid += 1

    # Add ~50 random members on metformin alone (would put them in DM denom by pharmacy if also have 1 dx)
    extra = random.sample(members, 50)
    for m in extra:
        if m["member_id"] in dm_members:
            continue
        if 30 <= (MP_END - date.fromisoformat(m["date_of_birth"])).days // 365 <= 75:
            ndc, name = NDC_DIABETES_MED[1]  # metformin
            pharmacy.append({
                "rx_id": f"RX{rxid:08d}",
                "member_id": m["member_id"],
                "fill_date": random_date_in(date(2024, 6, 1), MP_END).isoformat(),
                "ndc_code": ndc,
                "drug_name": name,
                "days_supply": 90,
                "quantity": 90,
            })
            rxid += 1
    return pharmacy

# ------------------------------------------------------------------
# LAB RESULTS (LOINC) - for ECDS measures
# ------------------------------------------------------------------
def generate_labs(members, procs):
    """For COL-E and CCS-E, ECDS allows lab results as numerator events."""
    labs = []
    lid = 1
    # FOBT/FIT lab results from procs
    for p in procs:
        if p["procedure_code"] in CPT_FOBT or p["procedure_code"] == CPT_SDNA_FIT[0]:
            labs.append({
                "lab_id": f"LB{lid:08d}",
                "member_id": p["member_id"],
                "service_date": p["service_date"],
                "loinc_code": random.choice(LOINC_FOBT if p["procedure_code"] in CPT_FOBT else LOINC_SDNA),
                "test_name": "Fecal Immunochemical Test" if p["procedure_code"] in CPT_FOBT else "sDNA-FIT (Cologuard)",
                "result_value": random.choice(["Negative", "Negative", "Negative", "Positive"]),
                "result_units": "qualitative",
            })
            lid += 1
        elif p["procedure_code"] in CPT_CYTOLOGY:
            labs.append({
                "lab_id": f"LB{lid:08d}",
                "member_id": p["member_id"],
                "service_date": p["service_date"],
                "loinc_code": random.choice(LOINC_CERVICAL_CYTOLOGY),
                "test_name": "Cervical cytology (Pap)",
                "result_value": random.choice(["NILM", "NILM", "NILM", "NILM", "ASC-US", "LSIL"]),
                "result_units": "qualitative",
            })
            lid += 1
        elif p["procedure_code"] in CPT_HRHPV:
            labs.append({
                "lab_id": f"LB{lid:08d}",
                "member_id": p["member_id"],
                "service_date": p["service_date"],
                "loinc_code": random.choice(LOINC_HPV),
                "test_name": "HPV high-risk DNA",
                "result_value": random.choice(["Negative", "Negative", "Negative", "Positive"]),
                "result_units": "qualitative",
            })
            lid += 1
    return labs

# ------------------------------------------------------------------
# REFERENCE: NCQA value sets (helper table for joins/documentation)
# ------------------------------------------------------------------
def generate_value_sets():
    rows = []
    def add(measure, vs_name, code_system, code, description):
        rows.append({
            "measure_id": measure,
            "value_set_name": vs_name,
            "code_system": code_system,
            "code": code,
            "description": description,
        })
    # COL-E
    for c in CPT_COLONOSCOPY: add("COL-E", "Colonoscopy",     "CPT", c, "Colonoscopy")
    for c in CPT_FOBT:        add("COL-E", "FOBT/FIT",        "CPT", c, "Fecal occult blood test / FIT")
    for c in CPT_SDNA_FIT:    add("COL-E", "sDNA-FIT",        "CPT", c, "Stool DNA with FIT (Cologuard)")
    for c in CPT_FLEX_SIG:    add("COL-E", "Flexible Sigmoidoscopy", "CPT", c, "Flexible sigmoidoscopy")
    for c in CPT_CT_COLON:    add("COL-E", "CT Colonography", "CPT", c, "CT colonography")
    for c in LOINC_FOBT:      add("COL-E", "FOBT/FIT Result", "LOINC", c, "FOBT/FIT lab result")
    for c in LOINC_SDNA:      add("COL-E", "sDNA-FIT Result", "LOINC", c, "Cologuard lab result")
    # CCS-E
    for c in CPT_CYTOLOGY:    add("CCS-E", "Cervical Cytology", "CPT", c, "Pap cytology")
    for c in CPT_HRHPV:       add("CCS-E", "hrHPV Test",      "CPT", c, "High-risk HPV DNA test")
    for c in LOINC_CERVICAL_CYTOLOGY: add("CCS-E", "Cervical Cytology Result", "LOINC", c, "Pap cytology result")
    for c in LOINC_HPV:       add("CCS-E", "hrHPV Result",    "LOINC", c, "HPV high-risk result")
    for c in CPT_HYST:        add("CCS-E", "Hysterectomy (Exclusion)", "CPT", c, "Hysterectomy procedure (denominator exclusion)")
    for c in ICD10_HYST:      add("CCS-E", "Absence of Cervix (Exclusion)", "ICD-10", c, "Absence of cervix dx (denominator exclusion)")
    # CBP
    for c in ICD10_HTN:       add("CBP",   "Essential Hypertension", "ICD-10", c, "Essential hypertension dx")
    add("CBP", "Systolic BP",  "LOINC", LOINC_BP_SYS, "Systolic blood pressure")
    add("CBP", "Diastolic BP", "LOINC", LOINC_BP_DIA, "Diastolic blood pressure")
    for c in CPT_II_BP_SYS_LT_140: add("CBP", "BP CPT-II Sys <140", "CPT-II", c, "Systolic BP <140 (numerator)")
    for c in CPT_II_BP_DIA_LT_90:  add("CBP", "BP CPT-II Dia <90",  "CPT-II", c, "Diastolic BP <90 (numerator)")
    # EED
    for c in ICD10_DM:        add("EED",   "Diabetes Diagnosis", "ICD-10", c, "Diabetes mellitus dx")
    for c in CPT_RETINAL_EXAM: add("EED",  "Retinal Eye Exam", "CPT", c, "Retinal/dilated eye exam")
    add("EED", "Negative Retinal Exam (Prior Year)", "CPT-II", "2023F", "Dilated retinal eye exam interpreted, neg for retinopathy")
    # AWV
    for c in HCPCS_AWV:       add("AWV",   "Annual Wellness Visit", "HCPCS", c, "Medicare AWV")
    for c in HCPCS_IPPE:      add("AWV",   "Welcome to Medicare (IPPE)", "HCPCS", c, "Initial preventive physical exam")
    # Universal
    for c in ICD10_HOSPICE:   add("ALL",   "Hospice/Palliative (Exclusion)", "ICD-10", c, "Encounter for palliative care")
    return rows

# ------------------------------------------------------------------
# WRITE
# ------------------------------------------------------------------
def write_csv(filename, rows, fieldnames=None):
    if not rows:
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(OUT / filename, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  {filename}: {len(rows):,} rows")

def main():
    print("Generating MedPOINT-style synthetic HEDIS dataset...")

    print("\n[1/9] Providers")
    providers = generate_providers(50)
    write_csv("providers.csv", providers)

    print("[2/9] Members")
    members = generate_members(2500)
    write_csv("members.csv", members)

    print("[3/9] Enrollment")
    enrollment = generate_enrollment(members, providers)
    write_csv("enrollment.csv", enrollment)

    print("[4/9] Diagnosis claims")
    dx = generate_diagnosis_claims(members, providers)
    write_csv("diagnosis_claims.csv", dx)

    print("[5/9] Procedure claims")
    procs = generate_procedure_claims(members, providers, dx)
    write_csv("procedure_claims.csv", procs)

    print("[6/9] Vital signs (BP)")
    vitals = generate_vitals(members, dx)
    write_csv("vital_signs.csv", vitals)

    print("[7/9] Pharmacy fills")
    pharmacy = generate_pharmacy(members, dx)
    write_csv("pharmacy.csv", pharmacy)

    print("[8/9] Lab results (ECDS)")
    labs = generate_labs(members, procs)
    write_csv("lab_results.csv", labs)

    print("[9/9] NCQA value sets reference")
    vs = generate_value_sets()
    write_csv("ncqa_value_sets.csv", vs)

    print("\nDone. All files in /home/claude/hedis_v2/data/")

if __name__ == "__main__":
    main()
