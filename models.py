# models.py
# Data models for dischargePlanningAgent
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime

@dataclass
class Patient:
    patient_id: str
    name: str
    mrn: str
    language: str = "EN"
    disposition: str = "Home"
    qc_status: str = "YELLOW"  # GREEN, YELLOW, RED
    wf_status: str = "Draft"   # Draft, Finalized
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@dataclass
class InpatientData:
    stroke_type: str
    fall_risk: str
    dysphagia: str
    anticoagulant: bool
    hospital_summary: str = ""
    id: Optional[int] = None
    patient_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@dataclass
class DischargePlan:
    language: str
    reading_level: str
    include_caregiver: bool
    plan_content: str = ""
    id: Optional[int] = None
    patient_id: Optional[str] = None
    version: int = 1
    is_current: bool = True
    created_at: Optional[str] = None

@dataclass
class PlanSection:
    section_name: str
    section_content: str
    id: Optional[int] = None
    plan_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@dataclass
class AuditEvent:
    ts: str
    msg: str
    id: Optional[int] = None
    patient_id: Optional[str] = None

@dataclass
class QCFlag:
    flag_type: str
    severity: str  # RED, YELLOW, GREEN
    message: str
    suggested_fix: str = ""
    target_section: str = ""  # Which section to update: Medications, Warning Signs, Mobility, Diet, Follow-Ups, Teach-Back
    resolved: bool = False
    id: Optional[int] = None
    patient_id: Optional[str] = None
    plan_id: Optional[int] = None
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None

@dataclass
class FinalizationData:
    teachback_completed: bool
    caregiver_present: bool
    interpreter_used: bool
    nurse_confidence: int  # 1-5 scale
    id: Optional[int] = None
    patient_id: Optional[str] = None
    finalized_at: Optional[str] = None
