CREATE TABLE patients (
    patient_id VARCHAR(20) PRIMARY KEY,
    patient_name VARCHAR(100) NOT NULL,
    age INT NOT NULL,
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    contact_number VARCHAR(15) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE samples (
    sample_id VARCHAR(20) PRIMARY KEY,
    patient_id VARCHAR(20) NOT NULL,
    sample_type ENUM('Blood', 'Swab', 'Tissue') NOT NULL,
    collection_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_patient
        FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id)
        ON DELETE CASCADE
);
ALTER TABLE samples
    ADD COLUMN test VARCHAR(100) NOT NULL,
    ADD COLUMN referring_doctor VARCHAR(100) NOT NULL,
    ADD COLUMN referring_hospital VARCHAR(150) NOT NULL;

CREATE TABLE patient_report(
    report_id VARCHAR (20) PRIMARY KEY,
    patient_id VARCHAR(20) NOT NULL,
    draft_text TEXT,
    final_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    signed_by VARCHAR(100) NULL,  
    signature_path VARCHAR(255) NULL,
    report_status ENUM ('Delivered','Pending') NOT NULL;
    CONSTRAINT fk_report_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;





INSERT INTO patients
(patient_id, patient_name, age, gender, contact_number)
VALUES
('P001', 'John Silva', 25, 'Male', '0712345601'),
('P002', 'Nimal Perera', 32, 'Male', '0712345602'),
('P003', 'Kamal Fernando', 41, 'Male', '0712345603'),
('P004', 'Saman Wijesinghe', 29, 'Male', '0712345604'),
('P005', 'Ruwan Jayasuriya', 35, 'Male', '0712345605'),
('P006', 'Anjali Perera', 27, 'Female', '0712345606'),
('P007', 'Nadeesha Silva', 30, 'Female', '0712345607'),
('P008', 'Dilani Fernando', 38, 'Female', '0712345608'),
('P009', 'Harshini Peris', 24, 'Female', '0712345609'),
('P010', 'Tharindu Gunasekara', 33, 'Male', '0712345610'),
('P011', 'Lakmal Perera', 45, 'Male', '0712345611'),
('P012', 'Sachini Silva', 28, 'Female', '0712345612'),
('P013', 'Chathura Fernando', 36, 'Male', '0712345613'),
('P014', 'Isuri Jayawardena', 22, 'Female', '0712345614'),
('P015', 'Ramesh Kumar', 31, 'Male', '0712345615'),
('P016', 'Nirosha Perera', 40, 'Female', '0712345616'),
('P017', 'Kasun Madushan', 26, 'Male', '0712345617'),
('P018', 'Piumi Fernando', 34, 'Female', '0712345618'),
('P019', 'Thilina Silva', 39, 'Male', '0712345619'),
('P020', 'Ayesha Perera', 23, 'Female', '0712345620');

INSERT INTO samples
(sample_id, patient_id, sample_type, collection_date)
VALUES
('S001', 'P001', 'Blood', '2026-06-01'),
('S002', 'P002', 'Swab', '2026-06-01'),
('S003', 'P003', 'Tissue', '2026-06-02'),
('S004', 'P004', 'Blood', '2026-06-02'),
('S005', 'P005', 'Swab', '2026-06-03'),
('S006', 'P006', 'Blood', '2026-06-03'),
('S007', 'P007', 'Tissue', '2026-06-04'),
('S008', 'P008', 'Blood', '2026-06-04'),
('S009', 'P009', 'Swab', '2026-06-05'),
('S010', 'P010', 'Blood', '2026-06-05'),
('S011', 'P011', 'Tissue', '2026-06-06'),
('S012', 'P012', 'Swab', '2026-06-06'),
('S013', 'P013', 'Blood', '2026-06-07'),
('S014', 'P014', 'Tissue', '2026-06-07'),
('S015', 'P015', 'Blood', '2026-06-08'),
('S016', 'P016', 'Swab', '2026-06-08'),
('S017', 'P017', 'Tissue', '2026-06-09'),
('S018', 'P018', 'Blood', '2026-06-09'),
('S019', 'P019', 'Swab', '2026-06-10'),
('S020', 'P020', 'Blood', '2026-06-10');
