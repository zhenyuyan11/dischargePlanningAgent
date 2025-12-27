# db_operations.py
# CRUD operations for all database entities
from typing import List, Optional, Dict
from datetime import datetime
from database import DatabaseConnection
from models import Patient, InpatientData, DischargePlan, PlanSection, AuditEvent, QCFlag, FinalizationData

# ========================================
# Patient Operations
# ========================================

def create_patient(patient: Patient) -> str:
    """Create a new patient in the database"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO patients (patient_id, name, mrn, language, disposition, qc_status, wf_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (patient.patient_id, patient.name, patient.mrn, patient.language,
          patient.disposition, patient.qc_status, patient.wf_status))

    conn.commit()
    return patient.patient_id

def get_patient(patient_id: str) -> Optional[Patient]:
    """Retrieve a single patient by ID"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    row = cursor.fetchone()

    if row:
        return Patient(**dict(row))
    return None

def get_all_patients() -> List[Patient]:
    """Retrieve all patients ordered by creation date"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patients ORDER BY created_at DESC")
    rows = cursor.fetchall()

    return [Patient(**dict(row)) for row in rows]

def update_patient(patient_id: str, **kwargs) -> bool:
    """Update patient fields"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    # Build dynamic UPDATE query
    valid_fields = ['name', 'mrn', 'language', 'disposition', 'qc_status', 'wf_status']
    set_clauses = []
    values = []

    for key, value in kwargs.items():
        if key in valid_fields:
            set_clauses.append(f"{key} = ?")
            values.append(value)

    if not set_clauses:
        return False

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    values.append(patient_id)

    query = f"UPDATE patients SET {', '.join(set_clauses)} WHERE patient_id = ?"
    cursor.execute(query, values)
    conn.commit()

    return cursor.rowcount > 0

def delete_patient(patient_id: str) -> bool:
    """Delete a patient (cascades to related data)"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
    conn.commit()

    return cursor.rowcount > 0

def search_patients(query: str = "", qc_filter: str = "All", wf_filter: str = "All") -> List[Patient]:
    """Search and filter patients"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM patients WHERE 1=1"
    params = []

    if query:
        sql += " AND (LOWER(name) LIKE ? OR mrn LIKE ?)"
        params.extend([f"%{query.lower()}%", f"%{query}%"])

    if qc_filter != "All":
        sql += " AND UPPER(qc_status) = ?"
        params.append(qc_filter.upper())

    if wf_filter != "All":
        sql += " AND wf_status = ?"
        params.append(wf_filter)

    sql += " ORDER BY created_at DESC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    return [Patient(**dict(row)) for row in rows]

# ========================================
# Inpatient Data Operations
# ========================================

def save_inpatient_data(patient_id: str, inpatient: InpatientData) -> int:
    """Save or update inpatient data for a patient"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    # Check if inpatient data exists for this patient
    cursor.execute("""
        SELECT id FROM inpatient_data WHERE patient_id = ?
        ORDER BY created_at DESC LIMIT 1
    """, (patient_id,))

    existing = cursor.fetchone()

    if existing:
        # Update existing
        cursor.execute("""
            UPDATE inpatient_data
            SET stroke_type=?, fall_risk=?, dysphagia=?, anticoagulant=?, hospital_summary=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (inpatient.stroke_type, inpatient.fall_risk, inpatient.dysphagia,
              1 if inpatient.anticoagulant else 0, inpatient.hospital_summary, existing[0]))
        inpatient_id = existing[0]
    else:
        # Create new
        cursor.execute("""
            INSERT INTO inpatient_data (patient_id, stroke_type, fall_risk, dysphagia, anticoagulant, hospital_summary)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (patient_id, inpatient.stroke_type, inpatient.fall_risk,
              inpatient.dysphagia, 1 if inpatient.anticoagulant else 0, inpatient.hospital_summary))
        inpatient_id = cursor.lastrowid

    conn.commit()
    return inpatient_id

def get_inpatient_data(patient_id: str) -> Optional[InpatientData]:
    """Get latest inpatient data for a patient"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM inpatient_data WHERE patient_id = ?
        ORDER BY created_at DESC LIMIT 1
    """, (patient_id,))

    row = cursor.fetchone()
    if row:
        data = dict(row)
        data['anticoagulant'] = bool(data['anticoagulant'])
        return InpatientData(**data)
    return None

def get_inpatient_history(patient_id: str) -> List[InpatientData]:
    """Get all inpatient data versions for a patient"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM inpatient_data WHERE patient_id = ?
        ORDER BY created_at DESC
    """, (patient_id,))

    rows = cursor.fetchall()
    result = []
    for row in rows:
        data = dict(row)
        data['anticoagulant'] = bool(data['anticoagulant'])
        result.append(InpatientData(**data))
    return result

# ========================================
# Discharge Plan Operations
# ========================================

def create_discharge_plan(patient_id: str, plan: DischargePlan) -> int:
    """Create a new discharge plan (marks previous as not current)"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    # Get next version number
    cursor.execute("""
        SELECT MAX(version) FROM discharge_plans WHERE patient_id = ?
    """, (patient_id,))
    result = cursor.fetchone()
    next_version = (result[0] or 0) + 1

    # Mark all previous plans as not current
    cursor.execute("""
        UPDATE discharge_plans SET is_current = 0 WHERE patient_id = ?
    """, (patient_id,))

    # Create new plan
    cursor.execute("""
        INSERT INTO discharge_plans
        (patient_id, version, language, reading_level, include_caregiver, plan_content, is_current)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (patient_id, next_version, plan.language, plan.reading_level,
          1 if plan.include_caregiver else 0, plan.plan_content))

    plan_id = cursor.lastrowid
    conn.commit()

    return plan_id

def get_current_plan(patient_id: str) -> Optional[DischargePlan]:
    """Get the current active discharge plan for a patient"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM discharge_plans
        WHERE patient_id = ? AND is_current = 1
        ORDER BY created_at DESC LIMIT 1
    """, (patient_id,))

    row = cursor.fetchone()
    if row:
        data = dict(row)
        data['include_caregiver'] = bool(data['include_caregiver'])
        data['is_current'] = bool(data['is_current'])
        return DischargePlan(**data)
    return None

def get_plan_history(patient_id: str) -> List[DischargePlan]:
    """Get all discharge plan versions for a patient"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM discharge_plans WHERE patient_id = ?
        ORDER BY version DESC
    """, (patient_id,))

    rows = cursor.fetchall()
    plans = []
    for row in rows:
        data = dict(row)
        data['include_caregiver'] = bool(data['include_caregiver'])
        data['is_current'] = bool(data['is_current'])
        plans.append(DischargePlan(**data))
    return plans

def update_plan_section(plan_id: int, section_name: str, content: str) -> bool:
    """Update or create a plan section"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    # Check if section exists
    cursor.execute("""
        SELECT id FROM plan_sections WHERE plan_id = ? AND section_name = ?
    """, (plan_id, section_name))

    existing = cursor.fetchone()

    if existing:
        # Update existing
        cursor.execute("""
            UPDATE plan_sections
            SET section_content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (content, existing[0]))
    else:
        # Create new
        cursor.execute("""
            INSERT INTO plan_sections (plan_id, section_name, section_content)
            VALUES (?, ?, ?)
        """, (plan_id, section_name, content))

    conn.commit()
    return True

def get_plan_sections(plan_id: int) -> Dict[str, str]:
    """Get all sections for a plan as a dictionary"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT section_name, section_content
        FROM plan_sections WHERE plan_id = ?
    """, (plan_id,))

    rows = cursor.fetchall()
    return {row[0]: row[1] for row in rows}

# ========================================
# Workflow State Operations
# ========================================

def initialize_workflow(patient_id: str) -> Dict[str, bool]:
    """Initialize default workflow state for a patient"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO workflow_state (patient_id)
        VALUES (?)
    """, (patient_id,))
    conn.commit()

    return {
        "intake_done": False,
        "generate_done": False,
        "qc_done": False,
        "edit_done": False,
        "finalize_done": False,
        "hospital_summary_done": False,
        "ai_generation_done": False,
        "qc_analysis_done": False,
        "qc_clearance_done": False,
        "final_approval_done": False,
    }

def get_workflow_state(patient_id: str) -> Dict[str, bool]:
    """Get workflow state for a patient"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT intake_done, generate_done, qc_done, edit_done, finalize_done,
               hospital_summary_done, ai_generation_done, qc_analysis_done,
               qc_clearance_done, final_approval_done
        FROM workflow_state WHERE patient_id = ?
    """, (patient_id,))

    row = cursor.fetchone()
    if row:
        return {
            "intake_done": bool(row[0]),
            "generate_done": bool(row[1]),
            "qc_done": bool(row[2]),
            "edit_done": bool(row[3]),
            "finalize_done": bool(row[4]),
            "hospital_summary_done": bool(row[5]),
            "ai_generation_done": bool(row[6]),
            "qc_analysis_done": bool(row[7]),
            "qc_clearance_done": bool(row[8]),
            "final_approval_done": bool(row[9]),
        }
    else:
        # Initialize if doesn't exist
        return initialize_workflow(patient_id)

def update_workflow_state(patient_id: str, **steps) -> bool:
    """Update specific workflow steps"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    # Build dynamic UPDATE query
    valid_steps = [
        "intake_done", "generate_done", "qc_done", "edit_done", "finalize_done",
        "hospital_summary_done", "ai_generation_done", "qc_analysis_done",
        "qc_clearance_done", "final_approval_done"
    ]
    set_clauses = []
    values = []

    for key, value in steps.items():
        if key in valid_steps:
            set_clauses.append(f"{key} = ?")
            values.append(1 if value else 0)

    if not set_clauses:
        return False

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    values.append(patient_id)

    query = f"UPDATE workflow_state SET {', '.join(set_clauses)} WHERE patient_id = ?"
    cursor.execute(query, values)
    conn.commit()

    return cursor.rowcount > 0

def check_qc_clearance(patient_id: str) -> bool:
    """Check if all RED/YELLOW QC flags are resolved"""
    unresolved_flags = get_qc_flags(patient_id, resolved=False)
    has_critical_flags = any(
        f.severity in ["RED", "YELLOW"]
        for f in unresolved_flags
    )
    return not has_critical_flags

# ========================================
# Audit Log Operations
# ========================================

def log_event(message: str, patient_id: Optional[str] = None) -> int:
    """Log an audit event"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO audit_log (patient_id, message)
        VALUES (?, ?)
    """, (patient_id, message))

    conn.commit()
    return cursor.lastrowid

def get_recent_logs(limit: int = 50) -> List[AuditEvent]:
    """Get recent audit log entries"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, patient_id, strftime('%H:%M:%S', timestamp) as ts, message
        FROM audit_log
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    return [AuditEvent(ts=row[2], msg=row[3], id=row[0], patient_id=row[1]) for row in rows]

def get_audit_log(patient_id: Optional[str] = None, limit: int = 50) -> List[AuditEvent]:
    """Get audit log entries, optionally filtered by patient"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    if patient_id:
        cursor.execute("""
            SELECT id, patient_id, strftime('%H:%M:%S', timestamp) as ts, message
            FROM audit_log
            WHERE patient_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (patient_id, limit))
    else:
        cursor.execute("""
            SELECT id, patient_id, strftime('%H:%M:%S', timestamp) as ts, message
            FROM audit_log
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

    rows = cursor.fetchall()
    return [AuditEvent(ts=row[2], msg=row[3], id=row[0], patient_id=row[1]) for row in rows]

# ========================================
# QC Flag Operations
# ========================================

def create_qc_flag(patient_id: str, plan_id: int, flag: QCFlag) -> int:
    """Create a new QC flag"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO qc_flags (patient_id, plan_id, flag_type, severity, message, suggested_fix, target_section, resolved)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (patient_id, plan_id, flag.flag_type, flag.severity, flag.message,
          flag.suggested_fix, flag.target_section, 1 if flag.resolved else 0))

    conn.commit()
    return cursor.lastrowid

def get_qc_flags(patient_id: str, resolved: Optional[bool] = None) -> List[QCFlag]:
    """Get QC flags for a patient, optionally filtered by resolved status"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    if resolved is not None:
        cursor.execute("""
            SELECT * FROM qc_flags
            WHERE patient_id = ? AND resolved = ?
            ORDER BY created_at DESC
        """, (patient_id, 1 if resolved else 0))
    else:
        cursor.execute("""
            SELECT * FROM qc_flags
            WHERE patient_id = ?
            ORDER BY created_at DESC
        """, (patient_id,))

    rows = cursor.fetchall()
    flags = []
    for row in rows:
        data = dict(row)
        data['resolved'] = bool(data['resolved'])
        flags.append(QCFlag(**data))
    return flags

def resolve_qc_flag(flag_id: int) -> bool:
    """Mark a QC flag as resolved"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE qc_flags
        SET resolved = 1, resolved_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (flag_id,))

    conn.commit()
    return cursor.rowcount > 0

# ========================================
# Finalization Operations
# ========================================

def save_finalization_data(patient_id: str, data: FinalizationData) -> int:
    """Save finalization data for a patient"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO finalization_data
        (patient_id, teachback_completed, caregiver_present, interpreter_used, nurse_confidence)
        VALUES (?, ?, ?, ?, ?)
    """, (patient_id, 1 if data.teachback_completed else 0,
          1 if data.caregiver_present else 0,
          1 if data.interpreter_used else 0,
          data.nurse_confidence))

    conn.commit()
    return cursor.lastrowid

def get_finalization_data(patient_id: str) -> Optional[FinalizationData]:
    """Get finalization data for a patient"""
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM finalization_data
        WHERE patient_id = ?
        ORDER BY finalized_at DESC LIMIT 1
    """, (patient_id,))

    row = cursor.fetchone()
    if row:
        data = dict(row)
        data['teachback_completed'] = bool(data['teachback_completed'])
        data['caregiver_present'] = bool(data['caregiver_present'])
        data['interpreter_used'] = bool(data['interpreter_used'])
        return FinalizationData(**data)
    return None
