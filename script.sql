
DROP TABLE IF EXISTS patient_report;
DROP TABLE IF EXISTS samples;
DROP TABLE IF EXISTS patients;
DROP TABLE IF EXISTS users;


CREATE TABLE users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


CREATE TABLE patients (
    patient_id     VARCHAR(20)                      PRIMARY KEY,
    patient_name   VARCHAR(100)                     NOT NULL,
    age            INT                              NOT NULL,
    gender         ENUM('Male', 'Female', 'Other')  NOT NULL,
    contact_number VARCHAR(15)                      NOT NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


CREATE TABLE samples (
    sample_id          VARCHAR(20)                       PRIMARY KEY,
    patient_id         VARCHAR(20)                       NOT NULL,
    sample_type        ENUM('Blood', 'Swab', 'Tissue')   NOT NULL,
    test               VARCHAR(100)                      NOT NULL,
    collection_date    DATE                              NOT NULL,
    referring_doctor   VARCHAR(100)                      NOT NULL,
    referring_hospital VARCHAR(150)                      NOT NULL,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_sample_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;


CREATE TABLE patient_report (
    report_id      VARCHAR(20)                   PRIMARY KEY,
    sample_id      VARCHAR(20)                   NOT NULL,
    draft_text     TEXT,
    final_text     TEXT,
    comments       TEXT,
    signed_by      VARCHAR(100)                  NULL,
    signature_path VARCHAR(255)                  NULL,
    report_status  ENUM('Delivered', 'Pending')  NOT NULL DEFAULT 'Pending',
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_report_sample
        FOREIGN KEY (sample_id) REFERENCES samples(sample_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

INSERT INTO patients (patient_id, patient_name, age, gender, contact_number) VALUES
('P000001', 'John Silva',            25, 'Male',   '0712345601'),
('P000002', 'Nimal Perera',          32, 'Male',   '0712345602'),
('P000003', 'Kamal Fernando',        41, 'Male',   '0712345603'),
('P000004', 'Saman Wijesinghe',      29, 'Male',   '0712345604'),
('P000005', 'Ruwan Jayasuriya',      35, 'Male',   '0712345605'),
('P000006', 'Anjali Perera',         27, 'Female', '0712345606'),
('P000007', 'Nadeesha Silva',        30, 'Female', '0712345607'),
('P000008', 'Dilani Fernando',       38, 'Female', '0712345608'),
('P000009', 'Harshini Peris',        24, 'Female', '0712345609'),
('P000010', 'Tharindu Gunasekara',   33, 'Male',   '0712345610'),
('P000011', 'Lakmal Perera',         45, 'Male',   '0712345611'),
('P000012', 'Sachini Silva',         28, 'Female', '0712345612'),
('P000013', 'Chathura Fernando',     36, 'Male',   '0712345613'),
('P000014', 'Isuri Jayawardena',     22, 'Female', '0712345614'),
('P000015', 'Ramesh Kumar',          31, 'Male',   '0712345615'),
('P000016', 'Nirosha Perera',        40, 'Female', '0712345616'),
('P000017', 'Kasun Madushan',        26, 'Male',   '0712345617'),
('P000018', 'Piumi Fernando',        34, 'Female', '0712345618'),
('P000019', 'Thilina Silva',         39, 'Male',   '0712345619'),
('P000020', 'Ayesha Perera',         23, 'Female', '0712345620');


INSERT INTO samples (sample_id, patient_id, sample_type, test, collection_date, referring_doctor, referring_hospital) VALUES
('S000001', 'P000001', 'Blood',  'FBC',          '2026-06-01', 'Dr. Perera',    'Colombo General'),
('S000002', 'P000002', 'Swab',   'Culture',      '2026-06-01', 'Dr. Silva',     'Nawaloka Hospital'),
('S000003', 'P000003', 'Tissue', 'Biopsy',       '2026-06-02', 'Dr. Fernando',  'Lanka Hospital'),
('S000004', 'P000004', 'Blood',  'Lipid Panel',  '2026-06-02', 'Dr. Jayawardena','Asiri Hospital'),
('S000005', 'P000005', 'Swab',   'PCR',          '2026-06-03', 'Dr. Perera',    'Colombo General'),
('S000006', 'P000006', 'Blood',  'Blood Sugar',  '2026-06-03', 'Dr. Perera',    'Nawaloka Hospital'),
('S000007', 'P000007', 'Tissue', 'Biopsy',       '2026-06-04', 'Dr. Silva',     'Lanka Hospital'),
('S000008', 'P000008', 'Blood',  'FBC',          '2026-06-04', 'Dr. Fernando',  'Asiri Hospital'),
('S000009', 'P000009', 'Swab',   'Culture',      '2026-06-05', 'Dr. Jayawardena','Colombo General'),
('S000010', 'P000010', 'Blood',  'Thyroid',      '2026-06-05', 'Dr. Perera',    'Nawaloka Hospital'),
('S000011', 'P000011', 'Tissue', 'Biopsy',       '2026-06-06', 'Dr. Silva',     'Lanka Hospital'),
('S000012', 'P000012', 'Swab',   'PCR',          '2026-06-06', 'Dr. Fernando',  'Colombo General'),
('S000013', 'P000013', 'Blood',  'Liver Panel',  '2026-06-07', 'Dr. Jayawardena','Asiri Hospital'),
('S000014', 'P000014', 'Tissue', 'Biopsy',       '2026-06-07', 'Dr. Perera',    'Nawaloka Hospital'),
('S000015', 'P000015', 'Blood',  'FBC',          '2026-06-08', 'Dr. Silva',     'Colombo General'),
('S000016', 'P000016', 'Swab',   'Culture',      '2026-06-08', 'Dr. Fernando',  'Lanka Hospital'),
('S000017', 'P000017', 'Tissue', 'Biopsy',       '2026-06-09', 'Dr. Jayawardena','Asiri Hospital'),
('S000018', 'P000018', 'Blood',  'Blood Sugar',  '2026-06-09', 'Dr. Perera',    'Nawaloka Hospital'),
('S000019', 'P000019', 'Swab',   'PCR',          '2026-06-10', 'Dr. Silva',     'Colombo General'),
('S000020', 'P000020', 'Blood',  'Thyroid',      '2026-06-10', 'Dr. Fernando',  'Lanka Hospital');