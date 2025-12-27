# services/__init__.py
# Re-export everything to maintain backward compatibility

from .db_operations import (
    get_all_patients, create_patient, update_patient,
    save_inpatient_data, get_inpatient_data,
    create_discharge_plan, get_current_plan, update_plan_section, get_plan_sections,
    get_workflow_state, update_workflow_state, initialize_workflow,
    log_event, get_recent_logs,
    save_finalization_data, get_finalization_data,
    create_qc_flag, get_qc_flags, resolve_qc_flag
)
from .openai_service import DischargePlanGenerator
from .pdf_generator import DischargePlanPDFGenerator

__all__ = [
    # DB Operations
    'get_all_patients', 'create_patient', 'update_patient',
    'save_inpatient_data', 'get_inpatient_data',
    'create_discharge_plan', 'get_current_plan', 'update_plan_section', 'get_plan_sections',
    'get_workflow_state', 'update_workflow_state', 'initialize_workflow',
    'log_event', 'get_recent_logs',
    'save_finalization_data', 'get_finalization_data',
    'create_qc_flag', 'get_qc_flags', 'resolve_qc_flag',
    # Services
    'DischargePlanGenerator',
    'DischargePlanPDFGenerator'
]
