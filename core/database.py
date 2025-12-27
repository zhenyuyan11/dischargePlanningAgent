# database.py
# Database initialization and connection management
import sqlite3
from pathlib import Path
from typing import Optional

# Database file path
DB_PATH = Path(__file__).parent / "stroke_discharge.db"

# SQL schema definitions
CREATE_PATIENTS_TABLE = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mrn TEXT NOT NULL UNIQUE,
    language TEXT DEFAULT 'EN',
    disposition TEXT DEFAULT 'Home',
    qc_status TEXT DEFAULT 'YELLOW',
    wf_status TEXT DEFAULT 'Draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_INPATIENT_DATA_TABLE = """
CREATE TABLE IF NOT EXISTS inpatient_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    stroke_type TEXT,
    fall_risk TEXT,
    dysphagia TEXT,
    anticoagulant BOOLEAN,
    hospital_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
);
"""

CREATE_DISCHARGE_PLANS_TABLE = """
CREATE TABLE IF NOT EXISTS discharge_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    language TEXT NOT NULL,
    reading_level TEXT,
    include_caregiver BOOLEAN DEFAULT 1,
    plan_content TEXT,
    is_current BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
);
"""

CREATE_PLAN_SECTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS plan_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    section_name TEXT NOT NULL,
    section_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plan_id) REFERENCES discharge_plans(id) ON DELETE CASCADE
);
"""

CREATE_WORKFLOW_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS workflow_state (
    patient_id TEXT PRIMARY KEY,
    intake_done BOOLEAN DEFAULT 0,
    generate_done BOOLEAN DEFAULT 0,
    qc_done BOOLEAN DEFAULT 0,
    edit_done BOOLEAN DEFAULT 0,
    finalize_done BOOLEAN DEFAULT 0,
    hospital_summary_done BOOLEAN DEFAULT 0,
    ai_generation_done BOOLEAN DEFAULT 0,
    qc_analysis_done BOOLEAN DEFAULT 0,
    qc_clearance_done BOOLEAN DEFAULT 0,
    final_approval_done BOOLEAN DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
);
"""

CREATE_AUDIT_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message TEXT NOT NULL,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE SET NULL
);
"""

CREATE_QC_FLAGS_TABLE = """
CREATE TABLE IF NOT EXISTS qc_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    plan_id INTEGER NOT NULL,
    flag_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    suggested_fix TEXT,
    target_section TEXT,
    resolved BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES discharge_plans(id) ON DELETE CASCADE
);
"""

CREATE_FINALIZATION_DATA_TABLE = """
CREATE TABLE IF NOT EXISTS finalization_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    teachback_completed BOOLEAN DEFAULT 0,
    caregiver_present BOOLEAN DEFAULT 0,
    interpreter_used BOOLEAN DEFAULT 0,
    nurse_confidence INTEGER,
    finalized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
);
"""

class DatabaseConnection:
    """Database connection manager for Streamlit compatibility"""

    @classmethod
    def get_connection(cls) -> sqlite3.Connection:
        """Get a fresh database connection for each operation"""
        conn = sqlite3.connect(
            str(DB_PATH),
            timeout=30.0,  # Wait up to 30 seconds for locks
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @classmethod
    def close(cls):
        """No-op for compatibility (connections are not cached)"""
        pass

def init_database():
    """Initialize database schema and seed demo data if needed"""
    try:
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()

        # Create all tables (IF NOT EXISTS handles re-runs safely)
        cursor.execute(CREATE_PATIENTS_TABLE)
        cursor.execute(CREATE_INPATIENT_DATA_TABLE)
        cursor.execute(CREATE_DISCHARGE_PLANS_TABLE)
        cursor.execute(CREATE_PLAN_SECTIONS_TABLE)
        cursor.execute(CREATE_WORKFLOW_STATE_TABLE)
        cursor.execute(CREATE_AUDIT_LOG_TABLE)
        cursor.execute(CREATE_QC_FLAGS_TABLE)
        cursor.execute(CREATE_FINALIZATION_DATA_TABLE)

        conn.commit()

        # Run migrations for existing databases
        _migrate_database(cursor)
        conn.commit()

        # Check if demo data needed
        cursor.execute("SELECT COUNT(*) FROM patients")
        count = cursor.fetchone()[0]

        if count == 0:
            seed_demo_data()
    except Exception as e:
        # If database is locked or another error, just continue
        # Tables likely already exist from a previous run
        print(f"Database initialization skipped: {e}")
        pass

def _migrate_database(cursor):
    """Apply database migrations for existing databases"""
    # Migration: Add suggested_fix column to qc_flags table if it doesn't exist
    try:
        cursor.execute("PRAGMA table_info(qc_flags)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'suggested_fix' not in columns:
            cursor.execute("ALTER TABLE qc_flags ADD COLUMN suggested_fix TEXT")
            print("Migration applied: Added suggested_fix column to qc_flags table")
        if 'target_section' not in columns:
            cursor.execute("ALTER TABLE qc_flags ADD COLUMN target_section TEXT")
            print("Migration applied: Added target_section column to qc_flags table")
    except Exception as e:
        print(f"Migration skipped: {e}")

    # Migration: Add new workflow flag columns
    try:
        cursor.execute("PRAGMA table_info(workflow_state)")
        columns = [col[1] for col in cursor.fetchall()]

        new_columns = [
            'hospital_summary_done',
            'ai_generation_done',
            'qc_analysis_done',
            'qc_clearance_done',
            'final_approval_done'
        ]

        for col in new_columns:
            if col not in columns:
                cursor.execute(f"ALTER TABLE workflow_state ADD COLUMN {col} BOOLEAN DEFAULT 0")
                print(f"Migration applied: Added {col} column to workflow_state table")

        # Copy data from old columns to new columns if new columns were just added
        if 'hospital_summary_done' not in columns:
            cursor.execute("""
                UPDATE workflow_state SET
                    hospital_summary_done = intake_done,
                    ai_generation_done = generate_done,
                    qc_analysis_done = qc_done,
                    qc_clearance_done = 0,
                    final_approval_done = finalize_done
            """)
            print("Migration applied: Copied old workflow flag values to new columns")

            # Recalculate QC clearance based on actual QC flag state
            # QC clearance is TRUE only if: plan exists AND no unresolved RED/YELLOW flags
            cursor.execute("""
                UPDATE workflow_state
                SET qc_clearance_done = CASE
                    WHEN EXISTS (
                        SELECT 1 FROM discharge_plans dp
                        WHERE dp.patient_id = workflow_state.patient_id
                    ) AND NOT EXISTS (
                        SELECT 1 FROM qc_flags qf
                        WHERE qf.patient_id = workflow_state.patient_id
                        AND qf.resolved = 0
                        AND qf.severity IN ('RED', 'YELLOW')
                    ) THEN 1
                    ELSE 0
                END
            """)

            print("Migration applied: Recalculated QC clearance status for all patients")

    except Exception as e:
        print(f"Workflow migration skipped: {e}")

def seed_demo_data():
    """Seed database with 10 realistic demo patients"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    # Demo patients - diverse demographics, dispositions, and languages
    demo_patients = [
        ("p001", "John Smith", "MRN001234", "EN", "Home", "YELLOW", "Draft"),
        ("p002", "Maria Garcia", "MRN002567", "ES", "Rehab", "YELLOW", "Draft"),
        ("p003", "Wei Chen", "MRN003891", "ZH", "Home", "YELLOW", "Draft"),
        ("p004", "Patricia Johnson", "MRN004234", "EN", "SNF", "YELLOW", "Draft"),
        ("p005", "David Kim", "MRN005678", "KO", "Home", "YELLOW", "Draft"),
        ("p006", "Mohammed Hassan", "MRN006912", "AR", "Rehab", "YELLOW", "Draft"),
        ("p007", "Jennifer Williams", "MRN007345", "EN", "Home", "YELLOW", "Draft"),
        ("p008", "Nguyen Tran", "MRN008789", "VI", "Home", "YELLOW", "Draft"),
        ("p009", "Robert Brown", "MRN009123", "EN", "Rehab", "YELLOW", "Draft"),
        ("p010", "Yuki Tanaka", "MRN010456", "JA", "Home", "YELLOW", "Draft"),
    ]

    cursor.executemany("""
        INSERT INTO patients (patient_id, name, mrn, language, disposition, qc_status, wf_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, demo_patients)

    # Demo inpatient data with clinical information - 10 diverse realistic scenarios
    demo_inpatient_data = [
        # p001 - John Smith - Ischemic stroke, moderate fall risk, on anticoagulant
        ("p001", "Ischemic", "Moderate", "Pass", 1,
         """68-year-old male admitted with sudden onset right-sided weakness and slurred speech. CT head showed acute left MCA territory ischemic stroke. Received IV alteplase at 2.5 hours with partial improvement. MRI confirmed infarct in left frontal-parietal region. Echocardiogram revealed atrial fibrillation (new diagnosis). Started on apixaban 5mg BID for stroke prevention. Carotid dopplers showed 30% bilateral stenosis. Swallow screen passed but mild dysarthria noted. PT evaluation shows moderate fall risk - ambulating 50 feet with rolling walker, requires contact guard. Right upper extremity with 3/5 strength. Occupational therapy for ADL training. Blood pressure controlled on lisinopril 10mg daily. LDL 142, started on atorvastatin 80mg. Patient lives alone, nephew available for support. Home health and outpatient PT/OT arranged. Neurology follow-up in 2 weeks."""),

        # p002 - Maria Garcia - Hemorrhagic stroke, high fall risk, dysphagia
        ("p002", "Hemorrhagic", "High", "Fail", 0,
         """71-year-old Spanish-speaking female presented with sudden severe headache, vomiting, and left hemiplegia. CT revealed right basal ganglia hemorrhage (4.2cm) with mild mass effect. Initial BP 220/118, controlled with IV nicardipine then transitioned to oral antihypertensives (amlodipine 10mg, labetalol 200mg BID). Neurosurgery consulted - conservative management. Failed bedside swallow evaluation, NG tube placed. Speech therapy recommends pureed diet with nectar-thick liquids when cleared for PO. High fall risk - left sided weakness 1/5, requires total assist for transfers. Family desires home discharge despite recommendations for acute rehabilitation. Interpreter services utilized for all teaching. Arranged home health with PT/OT/ST, DME (hospital bed, commode, wheelchair). Caregiver training completed with daughter. Follow-up with neurology and PCP in 1 week."""),

        # p003 - Wei Chen - Ischemic stroke, low fall risk, minimal deficits
        ("p003", "Ischemic", "Low", "Pass", 1,
         """62-year-old Mandarin-speaking male with sudden onset right hand weakness and difficulty writing, symptoms lasted 45 minutes before resolving. MRI DWI showed small acute infarct in left corona radiata. Carotid ultrasound normal. TEE negative for PFO or cardiac thrombus. Holter monitor confirmed paroxysmal atrial fibrillation. Started on apixaban 5mg BID and aspirin 81mg (to continue for 21 days). Diabetes with HbA1c 7.8%, on metformin. Hypertension controlled on losartan. Swallow screen passed. Neurologically intact on discharge - no residual weakness. Low fall risk, ambulating independently. Return to work clearance pending outpatient neurology evaluation. Stroke education provided via interpreter. Patient understands importance of anticoagulation compliance. Close INR monitoring not needed with DOAC. Neurology follow-up in 1 month, cardiology for EP consultation regarding possible ablation."""),

        # p004 - Patricia Johnson - Ischemic stroke, high fall risk, going to SNF
        ("p004", "Ischemic", "High", "Fail", 1,
         """79-year-old female with acute left MCA stroke, presented 8 hours after last known well (outside IV tPA window). CT perfusion showed no salvageable penumbra. Large territory infarct involving frontal, parietal, and temporal lobes. Right hemiplegia (0/5 strength), global aphasia, severe neglect. History of atrial fibrillation but was not on anticoagulation due to prior GI bleeding. Now started on apixaban 5mg BID after discussion with GI (benefits outweigh risks). Failed swallow evaluation - aspiration noted on VFSS. PEG tube placed on hospital day 4. High fall risk - requires total assist for all mobility and ADLs. Contracture prevention with hand splints and ankle boots. Family meeting held - patient requires 24/7 care. Skilled nursing facility placement arranged. Comprehensive stroke rehabilitation will continue at SNF. Palliative care consulted for goals of care discussion. Code status: DNR/DNI per advance directive."""),

        # p005 - David Kim - TIA, low fall risk, rapid recovery
        ("p005", "TIA", "Low", "Pass", 0,
         """58-year-old Korean-speaking male with 20-minute episode of left face and arm numbness with word-finding difficulty, completely resolved. MRI brain negative for acute infarct but showed chronic small vessel disease. CTA head/neck revealed 85% right internal carotid artery stenosis. Patient symptomatic (stenosis ipsilateral to symptoms). Vascular surgery consulted - scheduled for right carotid endarterectomy next week. Started on aspirin 325mg and clopidogrel 75mg (dual antiplatelet therapy). Hypertension controlled on amlodipine. Diabetes well-controlled (HbA1c 6.4%). Lipids at goal on rosuvastatin 20mg. Swallow screen passed. No neurological deficits on exam. Low fall risk. Patient works as accountant, cleared to return to work with restriction to avoid strenuous activity until after CEA. Extensive stroke education provided regarding warning signs. Emphasized need for pre-op labs and adherence to NPO instructions. Vascular surgery follow-up in 5 days for pre-op evaluation."""),

        # p006 - Mohammed Hassan - Ischemic stroke, moderate fall risk, needs rehab
        ("p006", "Ischemic", "Moderate", "Pass", 1,
         """66-year-old Arabic-speaking male with sudden onset left-sided weakness. CT showed right MCA territory acute ischemic stroke, presented at 90 minutes. Underwent mechanical thrombectomy with successful recanalization (TICI 3). Post-procedure exam shows significant improvement - left arm 4/5, left leg 4/5 strength. Atrial fibrillation on telemetry, started on apixaban. Post-op ICU stay for neuro checks, now stable on floor. Swallow screen passed. Moderate fall risk - ambulating with walker and supervision. Patient is imam at local mosque, highly motivated for recovery. Interpreter services arranged. Accepting transfer to acute inpatient rehabilitation facility for intensive therapy (3 hours daily). Home is two-story, will need assessment for DME and possible first-floor bedroom setup. Wife and three adult children involved and supportive. Insurance approved 2-week rehab stay. Goal is return to baseline function and community reintegration. Arranged neurology and PCP follow-up post-rehab discharge."""),

        # p007 - Jennifer Williams - Hemorrhagic stroke, moderate fall risk
        ("p007", "Hemorrhagic", "Moderate", "Pass", 0,
         """54-year-old female with sudden onset worst headache of life and right arm weakness. CT revealed left frontal lobe hemorrhage (2.8cm) with surrounding edema. No SAH. CTA negative for aneurysm or AVM. Blood pressure 198/102 on arrival, aggressively managed per AHA guidelines. Neurosurgery following - no surgical intervention indicated. Exam shows right upper extremity weakness 3/5, right lower 4/5. Mild expressive aphasia improving daily. Swallow screen passed on hospital day 2. Moderate fall risk - ambulating with walker and standby assist. MRI showed developmental venous anomaly (incidental, not bleeding source). Hemorrhage likely hypertensive etiology - patient had been off BP meds for 2 weeks. Restarted on lisinopril 20mg and hydrochlorothiazide 12.5mg with good control. Young children at home (ages 8 and 11), husband taking FMLA leave. Social work involved for community resources. Short-term disability paperwork completed. Plan for home with home health PT/OT/RN visits. Strict BP parameters <140/90. Follow-up MRI in 6 weeks, neurology in 2 weeks."""),

        # p008 - Nguyen Tran - Ischemic stroke, low fall risk, good recovery
        ("p008", "Ischemic", "Low", "Pass", 1,
         """48-year-old Vietnamese-speaking female with sudden onset right facial droop and right arm numbness. NIH stroke scale 4 on arrival. CT negative, MRI showed acute left corona radiata lacunar infarct. Symptoms rapidly improved - only mild residual right facial asymmetry by hospital day 2. Workup revealed undiagnosed hypertension (BP 165/95) and hyperlipidemia (LDL 187). Started on aspirin 81mg, clopidogrel 75mg (for 21 days), atorvastatin 80mg, and lisinopril 10mg. Echocardiogram normal, carotid dopplers normal, prolonged cardiac monitoring negative for atrial fibrillation. Diagnosis: small vessel lacunar stroke due to uncontrolled vascular risk factors. Swallow screen passed. Low fall risk, ambulating independently. Neurologically near baseline. Patient owns nail salon - eager to return to work. Extensive risk factor education via interpreter. Smoking cessation counseling provided (10 pack-year history, agrees to quit). Enrollment in cardiac rehabilitation for exercise prescription and risk reduction. Dietitian consult for DASH diet. Close outpatient follow-up arranged: neurology in 2 weeks, PCP in 1 week for BP recheck and medication titration."""),

        # p009 - Robert Brown - TIA with high-risk features
        ("p009", "TIA", "Moderate", "Pass", 1,
         """73-year-old male with three episodes of right hand weakness and slurred speech over past week, each lasting 5-10 minutes. Latest episode occurred in ED. MRI shows multiple small acute/subacute infarcts in left hemisphere - crescendo TIAs. CTA revealed left ICA occlusion with good collateral flow via circle of Willis. Patient not candidate for CEA/stenting given complete occlusion. High-risk TIA given multiple events and imaging findings. Started on aggressive medical management: aspirin 81mg, clopidogrel 75mg (lifelong dual antiplatelet), atorvastatin 80mg (LDL currently 156), and optimized BP control (amlodipine 10mg, metoprolol 50mg BID). Diabetes management intensified - HbA1c 8.9%, endocrinology consulted. Started on GLP-1 agonist. Swallow screen passed. Moderate fall risk due to unsteady gait (likely chronic small vessel disease). PT recommends walker for community ambulation. Extensive discussion about stroke risk - ABCD2 score 6 (high risk). Patient and wife educated on calling 911 for any new symptoms. Close neurology follow-up in 1 week, then monthly for 3 months. Cardiac rehab enrollment for supervised exercise and risk reduction. Home BP monitoring arranged."""),

        # p010 - Yuki Tanaka - Ischemic stroke, young patient
        ("p010", "Ischemic", "Low", "Pass", 1,
         """42-year-old Japanese-speaking female with sudden onset severe headache, dizziness, and ataxia. MRI showed acute right cerebellar infarct. CTA revealed right vertebral artery dissection. Patient has history of recent chiropractic neck manipulation 3 days prior. Started on aspirin 325mg. Neurosurgery and interventional neuroradiology consulted - no acute intervention needed. Serial exams for posterior fossa stroke monitoring - no signs of edema or hydrocephalus. By day 3, ataxia significantly improved. Swallow screen passed. Low fall risk with close supervision. Young stroke workup: normal echocardiogram, negative hypercoagulability panel, no evidence of vasculitis. Smoking cessation strongly advised (5 pack-year history). Contraceptive counseling - switched from estrogen-containing OCP to progesterone-only due to stroke history. Patient is a yoga instructor - concerned about return to work. Clearance for modified activities in 4-6 weeks pending neurology evaluation. No heavy lifting or neck manipulation. Long-term aspirin therapy. Follow-up CTA in 3 months to assess vessel healing. Neurology follow-up in 2 weeks. Genetic counseling offered given young age (patient declined). Strong emphasis on risk factor modification and warning sign education.""")
    ]

    cursor.executemany("""
        INSERT INTO inpatient_data (patient_id, stroke_type, fall_risk, dysphagia, anticoagulant, hospital_summary)
        VALUES (?, ?, ?, ?, ?, ?)
    """, demo_inpatient_data)

    # Initialize workflow states for demo patients - all start fresh (all flags = 0)
    for patient_id, _, _, _, _, _, _ in demo_patients:
        cursor.execute("""
            INSERT INTO workflow_state
            (patient_id, hospital_summary_done, ai_generation_done, qc_analysis_done, qc_clearance_done, final_approval_done)
            VALUES (?, 0, 0, 0, 0, 0)
        """, (patient_id,))

    # Add initial audit log entries
    cursor.execute("""
        INSERT INTO audit_log (message) VALUES ('Database initialized with 10 demo patients')
    """)

    # Add audit log entry for each patient
    audit_entries = [
        ('p001', 'John Smith: Clinical data imported'),
        ('p002', 'Maria Garcia: Clinical data imported'),
        ('p003', 'Wei Chen: Clinical data imported'),
        ('p004', 'Patricia Johnson: Clinical data imported'),
        ('p005', 'David Kim: Clinical data imported'),
        ('p006', 'Mohammed Hassan: Clinical data imported'),
        ('p007', 'Jennifer Williams: Clinical data imported'),
        ('p008', 'Nguyen Tran: Clinical data imported'),
        ('p009', 'Robert Brown: Clinical data imported'),
        ('p010', 'Yuki Tanaka: Clinical data imported')
    ]

    cursor.executemany("""
        INSERT INTO audit_log (patient_id, message) VALUES (?, ?)
    """, audit_entries)

    conn.commit()
    print(f"✓ Seeded database with {len(demo_patients)} demo patients and clinical data")
