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

    # Add initial audit log entry
    cursor.execute("""
        INSERT INTO audit_log (message) VALUES ('Database initialized with demo data')
    """)

    conn.commit()
    print(f"✓ Seeded database with {len(demo_patients)} demo patients")
