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
    """Seed database with 3 demo patients"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    # Demo patients
    demo_patients = [
        ("p1", "John Smith", "123456", "EN", "Home", "YELLOW", "Draft"),
        ("p2", "Mary Chen", "234567", "EN", "Home", "RED", "Draft"),
        ("p3", "Carlos Ruiz", "345678", "ES", "Rehab", "GREEN", "Finalized"),
    ]

    cursor.executemany("""
        INSERT INTO patients (patient_id, name, mrn, language, disposition, qc_status, wf_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, demo_patients)

    # Demo inpatient data with clinical information
    demo_inpatient_data = [
        # John Smith (p1) - Ischemic stroke, moderate fall risk, on anticoagulants
        ("p1", "Ischemic", "Moderate", "Pass", 1,
         """68-year-old male admitted with sudden onset right-sided weakness and speech difficulty. CT head showed acute left MCA territory ischemic stroke. Patient received IV tPA within 3-hour window with partial symptom improvement. MRI confirmed infarct in left frontal and temporal regions. Echocardiogram revealed atrial fibrillation, likely cardioembolic source. Started on apixaban for stroke prevention. Swallow screen passed. PT/OT consulted - patient ambulating with walker, moderate fall risk due to right leg weakness. Speech therapy for mild expressive aphasia. Blood pressure controlled on amlodipine and lisinopril. Patient educated on stroke warning signs and medication compliance. Discharge to home with outpatient PT/OT and neurology follow-up in 2 weeks."""),

        # Mary Chen (p2) - Hemorrhagic stroke, high fall risk, NOT on anticoagulants
        ("p2", "Hemorrhagic", "High", "Fail", 0,
         """72-year-old female presented with severe headache, nausea, and left-sided weakness. CT head revealed right basal ganglia hemorrhage approximately 3cm with mild midline shift. Blood pressure critically elevated at 210/115 on arrival, now controlled with IV nicardipine transitioned to oral agents. Neurosurgery consulted, no surgical intervention needed. Dysphagia screen failed - NGT placed, speech therapy recommends pureed diet with thickened liquids. High fall risk due to left hemiparesis and impaired balance. Patient requires moderate assist for transfers. CTA head/neck showed no aneurysm or AVM. Hemorrhage attributed to uncontrolled hypertension. Patient not candidate for anticoagulation. PT/OT recommend acute rehab placement but family requesting home discharge with home health. Extensive counseling provided regarding fall risks and aspiration precautions."""),

        # Carlos Ruiz (p3) - TIA, low fall risk, on anticoagulants
        ("p3", "TIA", "Low", "Pass", 1,
         """55-year-old male with history of hypertension and diabetes presented with transient right arm numbness and facial droop lasting 15 minutes, completely resolved on arrival. MRI brain showed no acute infarct but multiple old lacunar infarcts suggesting chronic small vessel disease. Carotid ultrasound revealed 70% stenosis of left internal carotid artery. Cardiology workup negative for atrial fibrillation. Started on dual antiplatelet therapy (aspirin and clopidogrel) for 21 days then transition to single agent. Blood pressure optimized, HbA1c elevated at 8.2% - diabetes management intensified. Patient ambulating independently, no fall risk. Swallow screen passed. Neurology recommends carotid endarterectomy vs stenting within 2 weeks. Extensive stroke education provided. Patient and family understand TIA is warning sign. Discharge to inpatient rehab for intensive PT/OT prior to vascular procedure. Scheduled for vascular surgery consultation and neurology follow-up.""")
    ]

    cursor.executemany("""
        INSERT INTO inpatient_data (patient_id, stroke_type, fall_risk, dysphagia, anticoagulant, hospital_summary)
        VALUES (?, ?, ?, ?, ?, ?)
    """, demo_inpatient_data)

    # Initialize workflow states for demo patients
    for patient_id, _, _, _, _, _, _ in demo_patients:
        # First two patients have intake/generate done, third is finalized
        if patient_id == "p3":
            cursor.execute("""
                INSERT INTO workflow_state
                (patient_id, hospital_summary_done, ai_generation_done, qc_analysis_done, qc_clearance_done, final_approval_done)
                VALUES (?, 1, 1, 1, 1, 1)
            """, (patient_id,))
        else:
            cursor.execute("""
                INSERT INTO workflow_state
                (patient_id, hospital_summary_done, ai_generation_done, qc_analysis_done, qc_clearance_done, final_approval_done)
                VALUES (?, 1, 1, 0, 0, 0)
            """, (patient_id,))

    # Add initial audit log entries
    cursor.execute("""
        INSERT INTO audit_log (message) VALUES ('Database initialized with demo data')
    """)
    cursor.execute("""
        INSERT INTO audit_log (patient_id, message) VALUES ('p1', 'John Smith: Clinical data imported')
    """)
    cursor.execute("""
        INSERT INTO audit_log (patient_id, message) VALUES ('p2', 'Mary Chen: Clinical data imported')
    """)
    cursor.execute("""
        INSERT INTO audit_log (patient_id, message) VALUES ('p3', 'Carlos Ruiz: Clinical data imported')
    """)

    conn.commit()
    print(f"✓ Seeded database with {len(demo_patients)} demo patients and clinical data")
