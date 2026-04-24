/* =============================================================================
   File: 00_schema_and_load.sql
   Purpose: Create the MedPOINT_HEDIS database, define tables, and BULK INSERT
            from the synthetic CSV files.
   Author:  Jeremiah Salamat
   Notes:   Designed for SQL Server / SSMS. Adjust file paths as needed.
            Run this script ONCE to build the database, then run the measure
            queries in 01_xx through 05_xx.
   ============================================================================= */

-- ===== 1. Create database ====================================================
IF DB_ID('MedPOINT_HEDIS') IS NULL
    CREATE DATABASE MedPOINT_HEDIS;
GO
USE MedPOINT_HEDIS;
GO

-- ===== 2. Drop tables if rerunning ===========================================
IF OBJECT_ID('dbo.lab_results', 'U')      IS NOT NULL DROP TABLE dbo.lab_results;
IF OBJECT_ID('dbo.pharmacy', 'U')          IS NOT NULL DROP TABLE dbo.pharmacy;
IF OBJECT_ID('dbo.vital_signs', 'U')       IS NOT NULL DROP TABLE dbo.vital_signs;
IF OBJECT_ID('dbo.procedure_claims', 'U')  IS NOT NULL DROP TABLE dbo.procedure_claims;
IF OBJECT_ID('dbo.diagnosis_claims', 'U')  IS NOT NULL DROP TABLE dbo.diagnosis_claims;
IF OBJECT_ID('dbo.enrollment', 'U')        IS NOT NULL DROP TABLE dbo.enrollment;
IF OBJECT_ID('dbo.members', 'U')           IS NOT NULL DROP TABLE dbo.members;
IF OBJECT_ID('dbo.providers', 'U')         IS NOT NULL DROP TABLE dbo.providers;
IF OBJECT_ID('dbo.ncqa_value_sets', 'U')   IS NOT NULL DROP TABLE dbo.ncqa_value_sets;
GO

-- ===== 3. Create tables ======================================================
CREATE TABLE dbo.providers (
    provider_id     VARCHAR(10)  PRIMARY KEY,
    npi             VARCHAR(10)  NOT NULL,
    first_name      VARCHAR(50),
    last_name       VARCHAR(50),
    specialty       VARCHAR(50),
    provider_type   VARCHAR(20),     -- PCP / Specialist
    active_flag     CHAR(1)
);

CREATE TABLE dbo.members (
    member_id          VARCHAR(10)  PRIMARY KEY,
    first_name         VARCHAR(50),
    last_name          VARCHAR(50),
    date_of_birth      DATE         NOT NULL,
    sex                CHAR(1)      NOT NULL,
    race_ethnicity     VARCHAR(20),
    payer_line         VARCHAR(10)  NOT NULL,    -- COMM, MCAL, MA, MMP, EXCH
    primary_language   VARCHAR(20),
    zip_code           VARCHAR(10)
);

CREATE TABLE dbo.enrollment (
    enrollment_id        VARCHAR(12) PRIMARY KEY,
    member_id            VARCHAR(10) NOT NULL FOREIGN KEY REFERENCES dbo.members(member_id),
    payer_line           VARCHAR(10) NOT NULL,
    coverage_start_date  DATE        NOT NULL,
    coverage_end_date    DATE        NOT NULL,
    pcp_provider_id      VARCHAR(10) FOREIGN KEY REFERENCES dbo.providers(provider_id)
);

CREATE TABLE dbo.diagnosis_claims (
    claim_id          VARCHAR(12) PRIMARY KEY,
    member_id         VARCHAR(10) NOT NULL FOREIGN KEY REFERENCES dbo.members(member_id),
    provider_id       VARCHAR(10) FOREIGN KEY REFERENCES dbo.providers(provider_id),
    service_date      DATE        NOT NULL,
    icd10_code        VARCHAR(10) NOT NULL,
    claim_type        VARCHAR(20),
    place_of_service  VARCHAR(5)
);

CREATE TABLE dbo.procedure_claims (
    procedure_id      VARCHAR(12) PRIMARY KEY,
    member_id         VARCHAR(10) NOT NULL FOREIGN KEY REFERENCES dbo.members(member_id),
    provider_id       VARCHAR(10) FOREIGN KEY REFERENCES dbo.providers(provider_id),
    service_date      DATE        NOT NULL,
    code_system       VARCHAR(10),       -- CPT, HCPCS, CPT-II
    procedure_code    VARCHAR(10) NOT NULL,
    place_of_service  VARCHAR(5)
);

CREATE TABLE dbo.vital_signs (
    vital_id          VARCHAR(12) PRIMARY KEY,
    member_id         VARCHAR(10) NOT NULL FOREIGN KEY REFERENCES dbo.members(member_id),
    service_date      DATE        NOT NULL,
    loinc_systolic    VARCHAR(10),
    systolic_bp       INT,
    loinc_diastolic   VARCHAR(10),
    diastolic_bp      INT,
    provider_id       VARCHAR(10) FOREIGN KEY REFERENCES dbo.providers(provider_id),
    place_of_service  VARCHAR(5)
);

CREATE TABLE dbo.pharmacy (
    rx_id        VARCHAR(12) PRIMARY KEY,
    member_id    VARCHAR(10) NOT NULL FOREIGN KEY REFERENCES dbo.members(member_id),
    fill_date    DATE        NOT NULL,
    ndc_code     VARCHAR(15),
    drug_name    VARCHAR(100),
    days_supply  INT,
    quantity     INT
);

CREATE TABLE dbo.lab_results (
    lab_id        VARCHAR(12) PRIMARY KEY,
    member_id     VARCHAR(10) NOT NULL FOREIGN KEY REFERENCES dbo.members(member_id),
    service_date  DATE        NOT NULL,
    loinc_code    VARCHAR(15),
    test_name     VARCHAR(100),
    result_value  VARCHAR(50),
    result_units  VARCHAR(30)
);

CREATE TABLE dbo.ncqa_value_sets (
    measure_id        VARCHAR(10) NOT NULL,    -- COL-E, CCS-E, CBP, EED, AWV, ALL
    value_set_name    VARCHAR(80),
    code_system       VARCHAR(10),             -- ICD-10, CPT, CPT-II, HCPCS, LOINC
    code              VARCHAR(15) NOT NULL,
    description       VARCHAR(200)
);
GO

-- ===== 4. Indexes for performance ============================================
CREATE INDEX IX_dx_member_code        ON dbo.diagnosis_claims (member_id, icd10_code, service_date);
CREATE INDEX IX_dx_code               ON dbo.diagnosis_claims (icd10_code);
CREATE INDEX IX_proc_member_code      ON dbo.procedure_claims (member_id, procedure_code, service_date);
CREATE INDEX IX_proc_code             ON dbo.procedure_claims (procedure_code);
CREATE INDEX IX_vital_member_date     ON dbo.vital_signs (member_id, service_date DESC);
CREATE INDEX IX_pharm_member_date     ON dbo.pharmacy (member_id, fill_date);
CREATE INDEX IX_enroll_member_dates   ON dbo.enrollment (member_id, coverage_start_date, coverage_end_date);
CREATE INDEX IX_vs_measure_code       ON dbo.ncqa_value_sets (measure_id, code);
GO

-- ===== 5. BULK INSERT (adjust path to your local data folder) ================
-- Example path: 'C:\hedis_v2\data\providers.csv'
-- Make sure FORMAT='CSV' and FIRSTROW=2 are used.

/*
BULK INSERT dbo.providers
FROM 'C:\hedis_v2\data\providers.csv'
WITH (FORMAT='CSV', FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0a', TABLOCK);

BULK INSERT dbo.members
FROM 'C:\hedis_v2\data\members.csv'
WITH (FORMAT='CSV', FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0a', TABLOCK);

BULK INSERT dbo.enrollment
FROM 'C:\hedis_v2\data\enrollment.csv'
WITH (FORMAT='CSV', FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0a', TABLOCK);

BULK INSERT dbo.diagnosis_claims
FROM 'C:\hedis_v2\data\diagnosis_claims.csv'
WITH (FORMAT='CSV', FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0a', TABLOCK);

BULK INSERT dbo.procedure_claims
FROM 'C:\hedis_v2\data\procedure_claims.csv'
WITH (FORMAT='CSV', FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0a', TABLOCK);

BULK INSERT dbo.vital_signs
FROM 'C:\hedis_v2\data\vital_signs.csv'
WITH (FORMAT='CSV', FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0a', TABLOCK);

BULK INSERT dbo.pharmacy
FROM 'C:\hedis_v2\data\pharmacy.csv'
WITH (FORMAT='CSV', FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0a', TABLOCK);

BULK INSERT dbo.lab_results
FROM 'C:\hedis_v2\data\lab_results.csv'
WITH (FORMAT='CSV', FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0a', TABLOCK);

BULK INSERT dbo.ncqa_value_sets
FROM 'C:\hedis_v2\data\ncqa_value_sets.csv'
WITH (FORMAT='CSV', FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0a', TABLOCK);
*/

-- ===== 6. Sanity check =======================================================
SELECT 'providers'         AS table_name, COUNT(*) AS row_count FROM dbo.providers UNION ALL
SELECT 'members',           COUNT(*) FROM dbo.members           UNION ALL
SELECT 'enrollment',        COUNT(*) FROM dbo.enrollment        UNION ALL
SELECT 'diagnosis_claims',  COUNT(*) FROM dbo.diagnosis_claims  UNION ALL
SELECT 'procedure_claims',  COUNT(*) FROM dbo.procedure_claims  UNION ALL
SELECT 'vital_signs',       COUNT(*) FROM dbo.vital_signs       UNION ALL
SELECT 'pharmacy',          COUNT(*) FROM dbo.pharmacy          UNION ALL
SELECT 'lab_results',       COUNT(*) FROM dbo.lab_results       UNION ALL
SELECT 'ncqa_value_sets',   COUNT(*) FROM dbo.ncqa_value_sets;
