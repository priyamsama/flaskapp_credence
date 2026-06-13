
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
    id             VARCHAR(20)                      NOT NULL UNIQUE,
    age            INT                              NOT NULL,
    gender         ENUM('Male', 'Female', 'Other')  NOT NULL,
    contact_number VARCHAR(15)                      NOT NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;


CREATE TABLE samples (
    sample_id          VARCHAR(20)                       PRIMARY KEY,
    patient_id         VARCHAR(20)                       NOT NULL,
    sample_name        VARCHAR(50)                       NOT NULL UNIQUE,
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
    patient_id     VARCHAR(20)                   NOT NULL,
    sample_id      VARCHAR(20)                   NOT NULL UNIQUE,
    comments       TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_report_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_report_sample
        FOREIGN KEY (sample_id) REFERENCES samples(sample_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

INSERT INTO patients (patient_id, patient_name, id, age, gender, contact_number) VALUES
('P000001', 'John Silva',            '900000001V', 25, 'Male',   '0712345601'),
('P000002', 'Nimal Perera',          '900000002V', 32, 'Male',   '0712345602'),
('P000003', 'Kamal Fernando',        '900000003V', 41, 'Male',   '0712345603'),
('P000004', 'Saman Wijesinghe',      '900000004V', 29, 'Male',   '0712345604'),
('P000005', 'Ruwan Jayasuriya',      '900000005V', 35, 'Male',   '0712345605'),
('P000006', 'Anjali Perera',         '900000006V', 27, 'Female', '0712345606'),
('P000007', 'Nadeesha Silva',        '900000007V', 30, 'Female', '0712345607'),
('P000008', 'Dilani Fernando',       '900000008V', 38, 'Female', '0712345608'),
('P000009', 'Harshini Peris',        '900000009V', 24, 'Female', '0712345609'),
('P000010', 'Tharindu Gunasekara',   '900000010V', 33, 'Male',   '0712345610'),
('P000011', 'Lakmal Perera',         '900000011V', 45, 'Male',   '0712345611'),
('P000012', 'Sachini Silva',         '900000012V', 28, 'Female', '0712345612'),
('P000013', 'Chathura Fernando',     '900000013V', 36, 'Male',   '0712345613'),
('P000014', 'Isuri Jayawardena',     '900000014V', 22, 'Female', '0712345614'),
('P000015', 'Ramesh Kumar',          '900000015V', 31, 'Male',   '0712345615'),
('P000016', 'Nirosha Perera',        '900000016V', 40, 'Female', '0712345616'),
('P000017', 'Kasun Madushan',        '900000017V', 26, 'Male',   '0712345617'),
('P000018', 'Piumi Fernando',        '900000018V', 34, 'Female', '0712345618'),
('P000019', 'Thilina Silva',         '900000019V', 39, 'Male',   '0712345619'),
('P000020', 'Ayesha Perera',         '900000020V', 23, 'Female', '0712345620');


INSERT INTO samples (sample_id, patient_id, sample_name, sample_type, test, collection_date, referring_doctor, referring_hospital) VALUES
('S000001', 'P000001', 'Sample_S000001', 'Blood',  'FBC',          '2026-06-01', 'Dr. Perera',    'Colombo General'),
('S000002', 'P000002', 'Sample_S000002', 'Swab',   'Culture',      '2026-06-01', 'Dr. Silva',     'Nawaloka Hospital'),
('S000003', 'P000003', 'Sample_S000003', 'Tissue', 'Biopsy',       '2026-06-02', 'Dr. Fernando',  'Lanka Hospital'),
('S000004', 'P000004', 'Sample_S000004', 'Blood',  'Lipid Panel',  '2026-06-02', 'Dr. Jayawardena','Asiri Hospital'),
('S000005', 'P000005', 'Sample_S000005', 'Swab',   'PCR',          '2026-06-03', 'Dr. Perera',    'Colombo General'),
('S000006', 'P000006', 'Sample_S000006', 'Blood',  'Blood Sugar',  '2026-06-03', 'Dr. Perera',    'Nawaloka Hospital'),
('S000007', 'P000007', 'Sample_S000007', 'Tissue', 'Biopsy',       '2026-06-04', 'Dr. Silva',     'Lanka Hospital'),
('S000008', 'P000008', 'Sample_S000008', 'Blood',  'FBC',          '2026-06-04', 'Dr. Fernando',  'Asiri Hospital'),
('S000009', 'P000009', 'Sample_S000009', 'Swab',   'Culture',      '2026-06-05', 'Dr. Jayawardena','Colombo General'),
('S000010', 'P000010', 'Sample_S000010', 'Blood',  'Thyroid',      '2026-06-05', 'Dr. Perera',    'Nawaloka Hospital'),
('S000011', 'P000011', 'Sample_S000011', 'Tissue', 'Biopsy',       '2026-06-06', 'Dr. Silva',     'Lanka Hospital'),
('S000012', 'P000012', 'Sample_S000012', 'Swab',   'PCR',          '2026-06-06', 'Dr. Fernando',  'Colombo General'),
('S000013', 'P000013', 'Sample_S000013', 'Blood',  'Liver Panel',  '2026-06-07', 'Dr. Jayawardena','Asiri Hospital'),
('S000014', 'P000014', 'Sample_S000014', 'Tissue', 'Biopsy',       '2026-06-07', 'Dr. Perera',    'Nawaloka Hospital'),
('S000015', 'P000015', 'Sample_S000015', 'Blood',  'FBC',          '2026-06-08', 'Dr. Silva',     'Colombo General'),
('S000016', 'P000016', 'Sample_S000016', 'Swab',   'Culture',      '2026-06-08', 'Dr. Fernando',  'Lanka Hospital'),
('S000017', 'P000017', 'Sample_S000017', 'Tissue', 'Biopsy',       '2026-06-09', 'Dr. Jayawardena','Asiri Hospital'),
('S000018', 'P000018', 'Sample_S000018', 'Blood',  'Blood Sugar',  '2026-06-09', 'Dr. Perera',    'Nawaloka Hospital'),
('S000019', 'P000019', 'Sample_S000019', 'Swab',   'PCR',          '2026-06-10', 'Dr. Silva',     'Colombo General'),
('S000020', 'P000020', 'Sample_S000020', 'Blood',  'Thyroid',      '2026-06-10', 'Dr. Fernando',  'Lanka Hospital');