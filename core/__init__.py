# core/__init__.py
# Re-export everything to maintain backward compatibility

from .models import Patient, InpatientData, DischargePlan, PlanSection, AuditEvent, QCFlag, FinalizationData
from .config import OPENAI_API_KEY, HOSPITAL_NAME, PDF_HEADER_COLOR, PDF_EMERGENCY_NUMBER, validate_config
from .database import init_database, DatabaseConnection, DB_PATH

__all__ = [
    # Models
    'Patient', 'InpatientData', 'DischargePlan', 'PlanSection',
    'AuditEvent', 'QCFlag', 'FinalizationData',
    # Config
    'OPENAI_API_KEY', 'HOSPITAL_NAME', 'PDF_HEADER_COLOR',
    'PDF_EMERGENCY_NUMBER', 'validate_config',
    # Database
    'init_database', 'DatabaseConnection', 'DB_PATH'
]
