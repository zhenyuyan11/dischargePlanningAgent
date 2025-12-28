# streamlit_app.py
# Exact Streamlit tab layout for the "Patient Dashboard" shell:
# - Left sidebar: search + filters + patient list + create demo patient
# - Main: patient header card + workflow stepper + tabs
# - Tabs: Patient Info / Generate / QC Review / Plan Editor / Finalize / Export / Audit Log
#
# Run: streamlit run app/streamlit_app.py

# Add parent directory to Python path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from datetime import datetime
from typing import Dict, List, Optional
import random

# Database imports
from core.database import init_database
from core.config import OPENAI_API_KEY
from core.models import Patient, InpatientData, DischargePlan, AuditEvent, FinalizationData, QCFlag
from services.openai_service import DischargePlanGenerator
from services.db_operations import (
    get_all_patients, create_patient, update_patient,
    save_inpatient_data, get_inpatient_data,
    create_discharge_plan, get_current_plan, update_plan_section, get_plan_sections,
    get_workflow_state, update_workflow_state, initialize_workflow,
    log_event, get_recent_logs,
    save_finalization_data, get_finalization_data,
    create_qc_flag, get_qc_flags, resolve_qc_flag
)

# -----------------------------
# Helper Functions
# -----------------------------

def generate_random_clinical_data():
    """Generate realistic random clinical parameters"""

    # Stroke types with weighted probabilities (ischemic more common)
    stroke_types = ["Ischemic", "Ischemic", "Ischemic", "Hemorrhagic", "TIA"]
    stroke_type = random.choice(stroke_types)

    # Fall risk (higher risk more common in stroke patients)
    fall_risks = ["Low", "Moderate", "Moderate", "High", "High"]
    fall_risk = random.choice(fall_risks)

    # Dysphagia screening (some failures expected)
    dysphagia_results = ["Pass", "Pass", "Pass", "Fail", "Unknown"]
    dysphagia = random.choice(dysphagia_results)

    # Anticoagulant use (common for ischemic stroke)
    if stroke_type == "Ischemic":
        anticoagulant = random.choice([True, True, False])  # 66% on anticoagulants
    elif stroke_type == "Hemorrhagic":
        anticoagulant = False  # Contraindicated
    else:  # TIA
        anticoagulant = random.choice([True, False])

    # Language (mostly English with some diversity)
    languages = ["EN", "EN", "EN", "EN", "ES", "ZH"]
    language = random.choice(languages)

    # Disposition (most go home)
    dispositions = ["Home", "Home", "Home", "Rehab Facility", "SNF"]
    disposition = random.choice(dispositions)

    return {
        "stroke_type": stroke_type,
        "fall_risk": fall_risk,
        "dysphagia": dysphagia,
        "anticoagulant": anticoagulant,
        "language": language,
        "disposition": disposition
    }

def create_realistic_patient(patient_name: str):
    """Create a new patient with AI-generated realistic clinical data"""

    # Generate unique patient ID and MRN using timestamp
    import time
    timestamp = int(time.time() * 1000)  # Millisecond timestamp
    patient_id = f"p{timestamp % 1000000}"  # Last 6 digits for readability
    mrn = str(timestamp)[-9:]  # Last 9 digits for unique MRN

    # Generate random clinical data
    clinical_data = generate_random_clinical_data()

    # Generate AI hospital summary
    if OPENAI_API_KEY:
        try:
            generator = DischargePlanGenerator(OPENAI_API_KEY)
            hospital_summary = generator.generate_hospital_summary(
                patient_name=patient_name,
                stroke_type=clinical_data["stroke_type"],
                fall_risk=clinical_data["fall_risk"],
                dysphagia=clinical_data["dysphagia"],
                anticoagulant=clinical_data["anticoagulant"],
                disposition=clinical_data["disposition"]
            )
        except Exception as e:
            # Fallback if AI generation fails
            hospital_summary = f"Patient with {clinical_data['stroke_type']} stroke. {clinical_data['fall_risk']} fall risk. Dysphagia screen: {clinical_data['dysphagia']}. Discharge to {clinical_data['disposition']}."
    else:
        hospital_summary = f"Patient with {clinical_data['stroke_type']} stroke. {clinical_data['fall_risk']} fall risk. Dysphagia screen: {clinical_data['dysphagia']}. Discharge to {clinical_data['disposition']}."

    # Create Patient record
    new_patient = Patient(
        patient_id=patient_id,
        name=patient_name,
        mrn=mrn,
        language=clinical_data["language"],
        disposition=clinical_data["disposition"],
        qc_status="YELLOW",  # Default to needs review
        wf_status="Draft"
    )

    # Save patient to database
    create_patient(new_patient)
    initialize_workflow(new_patient.patient_id)

    # Create InpatientData record with generated clinical data
    inpatient_data = InpatientData(
        stroke_type=clinical_data["stroke_type"],
        fall_risk=clinical_data["fall_risk"],
        dysphagia=clinical_data["dysphagia"],
        anticoagulant=clinical_data["anticoagulant"],
        hospital_summary=hospital_summary
    )

    # Save inpatient data to database
    save_inpatient_data(new_patient.patient_id, inpatient_data)

    # Update session state
    st.session_state.patients.insert(0, new_patient)
    st.session_state.selected_patient_id = new_patient.patient_id

    # Switch to Patient Info tab and refresh workflow state
    st.session_state.active_tab = "Patient Info"
    st.session_state.workflow = get_workflow_state(new_patient.patient_id)

    log(f"Created patient with AI-generated data → {patient_name}")

@st.dialog("Create New Patient")
def create_patient_dialog():
    """Dialog for creating a new patient with custom name"""
    st.write("Enter patient information:")

    patient_name = st.text_input("Patient Name", placeholder="e.g., John Smith")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Create", type="primary"):
            if patient_name.strip():
                # Generate patient with AI data
                with st.spinner("🤖 Generating patient with AI-powered clinical data..."):
                    create_realistic_patient(patient_name)
                st.success(f"✅ Created patient: {patient_name}")
                st.rerun()
            else:
                st.error("Please enter a patient name")
    with col2:
        if st.button("Cancel"):
            st.rerun()

@st.dialog("Preview QC Suggestion", width="large")
def preview_qc_expansion_dialog(flag: QCFlag, p: Patient):
    """Dialog for previewing and editing LLM-expanded QC suggestion"""

    st.markdown(f"### {flag.severity} Flag: {flag.flag_type}")
    st.write(f"**Issue:** {flag.message}")
    st.write(f"**Target Section:** {flag.target_section}")
    st.divider()

    # Initialize session state for this flag
    if f"expanded_content_{flag.id}" not in st.session_state:
        st.session_state[f"expanded_content_{flag.id}"] = None
    if f"expansion_error_{flag.id}" not in st.session_state:
        st.session_state[f"expansion_error_{flag.id}"] = None
    if f"generation_started_{flag.id}" not in st.session_state:
        st.session_state[f"generation_started_{flag.id}"] = False

    # Show loading state and generate content
    if st.session_state[f"expanded_content_{flag.id}"] is None and st.session_state[f"expansion_error_{flag.id}"] is None:
        # Show loading message
        st.info("⏳ Applying the fix with AI... This may take 10-20 seconds.")

        # Generate content if not already started
        if not st.session_state[f"generation_started_{flag.id}"]:
            st.session_state[f"generation_started_{flag.id}"] = True

            try:
                # Validate API key
                if not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key-here":
                    st.session_state[f"expansion_error_{flag.id}"] = "OpenAI API key not configured"
                else:
                    # Get context
                    current_plan = get_current_plan(p.patient_id)
                    if not current_plan:
                        st.session_state[f"expansion_error_{flag.id}"] = "No discharge plan found"
                    else:
                        inpatient_data = get_inpatient_data(p.patient_id)
                        sections_dict = get_plan_sections(current_plan.id)

                        # Call LLM (this happens while loading message is visible)
                        generator = DischargePlanGenerator(OPENAI_API_KEY)
                        expanded = generator.expand_qc_suggestion(
                            patient=p,
                            inpatient=inpatient_data,
                            sections_dict=sections_dict,
                            qc_flag=flag,
                            suggested_fix_text=flag.suggested_fix
                        )

                        st.session_state[f"expanded_content_{flag.id}"] = expanded
                        log(f"LLM expanded QC suggestion: {flag.flag_type}")
                        st.rerun()  # Rerun to show preview

            except Exception as e:
                st.session_state[f"expansion_error_{flag.id}"] = str(e)
                log(f"QC expansion failed: {str(e)}")
                st.rerun()  # Rerun to show error

    # Show error with fallback option
    elif st.session_state[f"expansion_error_{flag.id}"]:
        st.error(f"❌ Failed to generate content: {st.session_state[f'expansion_error_{flag.id}']}")
        st.divider()
        st.markdown("### Fallback: Use Original Suggestion")

        fallback_content = st.text_area(
            "Content to insert",
            value=flag.suggested_fix,
            height=200,
            key=f"fallback_{flag.id}"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Insert Fallback", type="primary", key=f"insert_fallback_{flag.id}"):
                _apply_qc_suggestion(p, flag, fallback_content)
                _clear_expansion_state(flag.id)
                st.session_state[f"show_dialog_{flag.id}"] = False
                st.rerun()
        with col2:
            if st.button("Cancel", key=f"cancel_fallback_{flag.id}"):
                _clear_expansion_state(flag.id)
                st.session_state[f"show_dialog_{flag.id}"] = False
                st.rerun()

    # Show editable preview
    elif st.session_state[f"expanded_content_{flag.id}"]:
        st.success("✅ Content generated! You can edit before applying.")
        st.markdown("### Preview & Edit")
        st.caption(f"This will **replace** the entire **{flag.target_section}** section")

        edited_content = st.text_area(
            "Generated content (editable)",
            value=st.session_state[f"expanded_content_{flag.id}"],
            height=300,
            key=f"edit_{flag.id}",
            help="Edit the content before inserting"
        )

        st.caption(f"Length: {len(edited_content)} characters")
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Insert into Plan", type="primary", key=f"insert_{flag.id}", use_container_width=True):
                _apply_qc_suggestion(p, flag, edited_content)
                _clear_expansion_state(flag.id)
                st.session_state[f"show_dialog_{flag.id}"] = False
                st.success("✅ Section regenerated!")
                st.rerun()
        with col2:
            if st.button("Cancel", key=f"cancel_{flag.id}", use_container_width=True):
                _clear_expansion_state(flag.id)
                st.session_state[f"show_dialog_{flag.id}"] = False
                st.rerun()

def _clear_expansion_state(flag_id: int):
    """Clear session state for flag expansion"""
    keys = [f"expansion_error_{flag_id}", f"expanded_content_{flag_id}", f"generation_started_{flag_id}"]
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]

def _apply_qc_suggestion(p: Patient, flag: QCFlag, content: str):
    """Apply QC suggestion content to discharge plan"""
    try:
        current_plan = get_current_plan(p.patient_id)
        if not current_plan:
            st.error("No discharge plan found")
            return

        sections_dict = get_plan_sections(current_plan.id)
        section_name = flag.target_section

        if section_name and section_name in sections_dict:
            # Clean up the regenerated content
            # Remove any section headers that LLM might have included
            import re
            cleaned_content = content
            # Remove lines like "==== MOBILITY ===" or "===MOBILITY==="
            cleaned_content = re.sub(r'={3,}\s*[A-Z\s]+={3,}\s*\n?', '', cleaned_content)
            cleaned_content = cleaned_content.strip()

            # Replace entire section with regenerated content
            update_plan_section(current_plan.id, section_name, cleaned_content)
            log(f"Regenerated {section_name} section with QC fix: {flag.flag_type}")
        else:
            st.warning(f"⚠️ Target section not found. Flag marked as resolved without applying.")
            log(f"No target section for flag: {flag.flag_type}")

        # Mark flag as resolved
        resolve_qc_flag(flag.id)

        # Recalculate QC status
        from services.db_operations import get_qc_flags
        unresolved_flags = get_qc_flags(p.patient_id, resolved=False)
        remaining_flags = [f for f in unresolved_flags if f.id != flag.id]

        if any(f.severity == "RED" for f in remaining_flags):
            new_status = "RED"
        elif any(f.severity == "YELLOW" for f in remaining_flags):
            new_status = "YELLOW"
        else:
            new_status = "GREEN"

        update_patient(p.patient_id, qc_status=new_status)
        p.qc_status = new_status

        # Update workflow state
        from services.db_operations import check_qc_clearance
        if check_qc_clearance(p.patient_id):
            update_workflow_state(p.patient_id, qc_clearance_done=True)
            st.session_state.workflow["qc_clearance_done"] = True
        else:
            update_workflow_state(p.patient_id, qc_clearance_done=False)
            st.session_state.workflow["qc_clearance_done"] = False

    except Exception as e:
        st.error(f"Failed to apply suggestion: {str(e)}")
        log(f"Error applying QC fix: {str(e)}")

# -----------------------------
# Session state init
# -----------------------------
def init_state():
    # Load patients from database
    if "patients" not in st.session_state:
        st.session_state.patients = get_all_patients()

    if "selected_patient_id" not in st.session_state:
        if st.session_state.patients:
            st.session_state.selected_patient_id = st.session_state.patients[0].patient_id

    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Patient Info"

    # Load audit log from database
    if "audit_log" not in st.session_state:
        st.session_state.audit_log = get_recent_logs(limit=50)

    # Load workflow state for selected patient
    if "workflow" not in st.session_state:
        if "selected_patient_id" in st.session_state:
            st.session_state.workflow = get_workflow_state(st.session_state.selected_patient_id)
        else:
            st.session_state.workflow = {
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

def now_str():
    return datetime.now().strftime("%H:%M:%S")

def log(msg: str):
    # Save to database
    patient_id = st.session_state.get("selected_patient_id")
    log_event(msg, patient_id)
    # Also update session_state for immediate display
    event = AuditEvent(ts=now_str(), msg=msg)
    st.session_state.audit_log.insert(0, event)

def get_patient(pid: str) -> Patient:
    # Try session_state first (fast)
    for p in st.session_state.patients:
        if p.patient_id == pid:
            return p
    # Fallback: reload from database
    from services.db_operations import get_patient as db_get_patient
    p = db_get_patient(pid)
    if p:
        return p
    # Last resort: return first patient
    return st.session_state.patients[0] if st.session_state.patients else None

def qc_badge(qc_status: str) -> str:
    return {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}.get(qc_status, "⚪")

# -----------------------------
# "Deep link" tab switch helper
# -----------------------------
def goto_tab(tab_name: str):
    st.session_state.active_tab = tab_name
    log(f"Switched tab → {tab_name}")
    st.rerun()

# -----------------------------
# Workflow stepper renderer
# -----------------------------
def render_stepper(wf: Dict[str, bool]):
    # Simple "stepper" without custom CSS: columns + icons
    steps = [
        ("Patient Hospital Summary", wf.get("hospital_summary_done", wf.get("intake_done", False))),
        ("AI Generation", wf.get("ai_generation_done", wf.get("generate_done", False))),
        ("QC Analysis", wf.get("qc_analysis_done", wf.get("qc_done", False))),
        ("QC Clearance", wf.get("qc_clearance_done", wf.get("edit_done", False))),
        ("Final Approval", wf.get("final_approval_done", wf.get("finalize_done", False))),
    ]
    cols = st.columns(len(steps))
    for i, (label, done) in enumerate(steps):
        icon = "✔" if done else "⏳"
        cols[i].markdown(f"**{label}**  \n{icon}")

# -----------------------------
# Sidebar (fixed)
# -----------------------------
def render_sidebar():
    st.sidebar.header("AI-Driven Personalized Discharge Planning")

    q = st.sidebar.text_input("🔍 Patient Search (Name / MRN)", value="")
    qc_filter = st.sidebar.selectbox("QC Status", ["All", "Green", "Yellow", "Red"], index=0)
    wf_filter = st.sidebar.selectbox("Workflow", ["All", "Draft", "Finalized"], index=0)

    def matches(p: Patient) -> bool:
        if q and (q.lower() not in p.name.lower() and q not in p.mrn):
            return False
        if qc_filter != "All" and p.qc_status != qc_filter.upper():
            return False
        if wf_filter != "All" and p.wf_status != wf_filter:
            return False
        return True

    filtered = [p for p in st.session_state.patients if matches(p)]

    st.sidebar.markdown(f"**Patient List** · {len(filtered)} patients")

    if not filtered:
        st.sidebar.info("No patients match filters.")
        return

    # Keep selection stable
    current = st.session_state.selected_patient_id
    if current not in [p.patient_id for p in filtered]:
        st.session_state.selected_patient_id = filtered[0].patient_id

    # Custom CSS for professional patient cards
    st.sidebar.markdown("""
        <style>
        .patient-card {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            border: 1px solid #e0e0e0;
            background: white;
            cursor: pointer;
            transition: all 0.2s;
            text-align: left;
        }
        .patient-card:hover {
            border-color: #1f77b4;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .patient-card-selected {
            border: 2px solid #1f77b4;
            background: #f0f7ff;
            box-shadow: 0 2px 8px rgba(31,119,180,0.2);
        }
        .patient-name {
            font-weight: 600;
            font-size: 14px;
            color: #1a1a1a;
            margin-bottom: 8px;
        }
        .patient-mrn {
            font-size: 12px;
            color: #666;
            font-family: monospace;
        }
        .patient-status {
            font-size: 11px;
            color: #888;
            margin-top: 4px;
        }
        .status-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 6px;
        }
        .status-green { background-color: #52c41a; }
        .status-yellow { background-color: #faad14; }
        .status-red { background-color: #f5222d; }
        </style>
    """, unsafe_allow_html=True)

    # Use a container with fixed height for scrolling
    with st.sidebar.container(height=400):
        for p in filtered:
            is_selected = p.patient_id == st.session_state.selected_patient_id

            # QC status indicator
            qc_color = {
                "GREEN": "green",
                "YELLOW": "yellow",
                "RED": "red"
            }.get(p.qc_status, "yellow")

            # Create patient card with HTML for better styling
            if is_selected:
                st.markdown(f"""
                    <div class="patient-card patient-card-selected">
                        <div class="patient-name">✓ {p.name}</div>
                        <div class="patient-mrn">MRN: {p.mrn}</div>
                        <div class="patient-status">
                            <span class="status-dot status-{qc_color}"></span>
                            {p.disposition} · {p.wf_status}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                # Clickable card for non-selected patients
                if st.button(
                    f"{p.name}\nMRN: {p.mrn}\n{p.disposition} · {p.wf_status}",
                    key=f"patient_{p.patient_id}",
                    use_container_width=True,
                    type="secondary"
                ):
                    st.session_state.selected_patient_id = p.patient_id
                    st.session_state.workflow = get_workflow_state(p.patient_id)
                    log(f"Selected patient → {p.name}")
                    st.rerun()

    st.sidebar.divider()

    if st.sidebar.button("➕ Create Demo Patient"):
        create_patient_dialog()

# -----------------------------
# Main shell (header + stepper + tabs)
# -----------------------------
def render_header(p: Patient):
    # Patient header card (fixed above tabs)
    st.markdown(f"<h2 style='font-size: 2.5rem !important; margin-bottom: 0.5rem;'>{p.name}</h2>", unsafe_allow_html=True)
    left, right = st.columns([3, 1])
    with left:
        st.markdown(
            f"MRN: `{p.mrn}` • Lang: `{p.language}` • Disposition: `{p.disposition}`"
        )
    with right:
        st.markdown(f"**QC:** {qc_badge(p.qc_status)} `{p.qc_status}`")
        st.markdown(f"**Workflow:** `{p.wf_status}`")

def render_tabs(p: Patient):
    # The tab bar is shown directly below header + stepper.
    # NOTE: Streamlit doesn't (currently) support programmatic "select tab" as a first-class API.
    # We emulate "active tab" with session_state + a top segmented control.
    tab_names = ["Patient Info", "Generate", "QC Review", "Plan Editor", "Finalize / Export", "Audit Log"]

    # Custom CSS for tab-style radio buttons
    st.markdown("""
        <style>
        /* Style the radio group container */
        div[role="radiogroup"][aria-label="Tabs"] {
            border-bottom: 2px solid #e0e0e0;
            margin-bottom: 1rem;
            padding-bottom: 0;
        }

        /* Hide radio circles and style labels as tabs */
        div[role="radiogroup"][aria-label="Tabs"] label {
            padding: 14px 28px !important;
            margin-right: 2px !important;
            margin-bottom: -2px !important;
            border: none !important;
            border-bottom: 3px solid transparent !important;
            border-radius: 0 !important;
            background: transparent !important;
            cursor: pointer !important;
            transition: all 0.25s ease !important;
            display: inline-block !important;
            font-size: 15px !important;
            font-weight: 500 !important;
            color: #666 !important;
        }

        /* Hide radio input circles */
        div[role="radiogroup"][aria-label="Tabs"] input[type="radio"] {
            opacity: 0 !important;
            position: absolute !important;
            width: 0 !important;
            height: 0 !important;
        }

        /* Selected tab style */
        div[role="radiogroup"][aria-label="Tabs"] label:has(input:checked) {
            background: transparent !important;
            border-bottom: 3px solid #1f77b4 !important;
            color: #1f77b4 !important;
            font-weight: 600 !important;
            position: relative !important;
        }

        /* Hover effects */
        div[role="radiogroup"][aria-label="Tabs"] label:hover {
            background: rgba(31, 119, 180, 0.05) !important;
            color: #333 !important;
        }

        div[role="radiogroup"][aria-label="Tabs"] label:has(input:checked):hover {
            background: rgba(31, 119, 180, 0.08) !important;
            color: #1f77b4 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # A segmented control-like selector that behaves like tabs (and is programmatically controllable).
    # If you insist on st.tabs specifically, see the note below.
    chosen = st.radio(
        "Tabs",
        tab_names,
        index=tab_names.index(st.session_state.active_tab),
        horizontal=True,
        label_visibility="collapsed",
    )
    if chosen != st.session_state.active_tab:
        st.session_state.active_tab = chosen
        log(f"Switched tab → {chosen}")
        st.rerun()

    st.divider()

    # Render the "active tab" content area (only this changes)
    if st.session_state.active_tab == "Patient Info":
        render_patient_info_tab(p)
    elif st.session_state.active_tab == "Generate":
        render_generate_tab(p)
    elif st.session_state.active_tab == "QC Review":
        render_qc_tab(p)
    elif st.session_state.active_tab == "Plan Editor":
        render_plan_editor_tab(p)
    elif st.session_state.active_tab == "Finalize / Export":
        render_finalize_tab(p)
    elif st.session_state.active_tab == "Audit Log":
        render_audit_tab()

# -----------------------------
# Tab content (minimal stubs)
# -----------------------------
def render_patient_info_tab(p: Patient):
    st.subheader("Patient Information")

    # Load inpatient data for this patient
    inpatient_data = get_inpatient_data(p.patient_id)

    # Patient Demographics Section
    st.markdown("### 📋 Demographics")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Patient ID", p.patient_id)
        st.metric("Name", p.name)
    with col2:
        st.metric("MRN", p.mrn)
        st.metric("Language", p.language)
    with col3:
        st.metric("Disposition", p.disposition)
        st.metric("Workflow Status", p.wf_status)

    st.divider()

    # Clinical Information Section
    st.markdown("### 🏥 Clinical Information")

    if inpatient_data:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Stroke Type**")
            st.info(inpatient_data.stroke_type)

            st.markdown("**Fall Risk**")
            risk_color = {"Low": "🟢", "Moderate": "🟡", "High": "🔴"}
            st.info(f"{risk_color.get(inpatient_data.fall_risk, '')} {inpatient_data.fall_risk}")

        with col2:
            st.markdown("**Dysphagia Screen**")
            dysphagia_color = {"Pass": "✅", "Fail": "❌", "Unknown": "❓"}
            st.info(f"{dysphagia_color.get(inpatient_data.dysphagia, '')} {inpatient_data.dysphagia}")

            st.markdown("**Anticoagulant**")
            st.info("✅ Yes" if inpatient_data.anticoagulant else "❌ No")

        st.divider()

        # Hospital Summary Section (Editable)
        st.markdown("### 📝 Hospital Summary")

        with st.form("hospital_summary_form"):
            hospital_summary = st.text_area(
                "Clinical Notes",
                value=inpatient_data.hospital_summary if inpatient_data.hospital_summary else "",
                height=200,
                placeholder="Enter hospital summary, admission details, diagnostic findings, treatment administered, etc.",
                label_visibility="collapsed"
            )

            submitted = st.form_submit_button("💾 Save Hospital Summary", type="primary")
            if submitted:
                # Update the hospital summary in the database
                updated_data = InpatientData(
                    stroke_type=inpatient_data.stroke_type,
                    fall_risk=inpatient_data.fall_risk,
                    dysphagia=inpatient_data.dysphagia,
                    anticoagulant=inpatient_data.anticoagulant,
                    hospital_summary=hospital_summary
                )
                save_inpatient_data(p.patient_id, updated_data)

                # Set hospital_summary_done flag
                if hospital_summary and hospital_summary.strip():
                    update_workflow_state(p.patient_id, hospital_summary_done=True)
                    st.session_state.workflow["hospital_summary_done"] = True

                log(f"Updated hospital summary for {p.name}")
                st.success("✅ Hospital summary saved successfully! Changes will be visible when you switch tabs or patients.")
    else:
        st.warning("No inpatient data available for this patient.")
        st.caption("Inpatient clinical information has not been recorded yet.")

def render_generate_tab(p: Patient):
    st.subheader("Generate Discharge Plan with AI")
    st.write("Generate a comprehensive discharge plan using GPT-4o based on patient data.")

    col1, col2, col3 = st.columns(3)
    with col1:
        lang = st.selectbox("Language", ["EN", "ES", "ZH"], index=0)
    with col2:
        reading = st.selectbox("Reading Level", ["Standard", "Simplified"], index=1)
    with col3:
        caregiver = st.checkbox("Include caregiver instructions", value=True)

    st.info("💡 Tip: The AI will generate 6 comprehensive sections based on all patient information from the Patient Info tab")

    if st.button("🚀 Generate Discharge Plan", type="primary"):
        # Validate API key
        if not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key-here":
            st.error("❌ OpenAI API key not configured. Please add your API key to the .env file")
            st.code("OPENAI_API_KEY=sk-your-key-here", language="bash")
            return

        # Load inpatient data
        inpatient_data = get_inpatient_data(p.patient_id)
        if not inpatient_data:
            st.warning("⚠️ No inpatient data found. Please complete Patient Info tab first.")
            return

        # Show loading indicator
        with st.spinner("🤖 Generating discharge plan with AI... This may take 30-60 seconds..."):
            try:
                # Call OpenAI service
                generator = DischargePlanGenerator(OPENAI_API_KEY)
                sections = generator.generate_discharge_plan(
                    patient_data=p,
                    inpatient_data=inpatient_data,
                    language=lang,
                    reading_level=reading,
                    include_caregiver=caregiver
                )

                # Create discharge plan record
                plan = DischargePlan(
                    language=lang,
                    reading_level=reading,
                    include_caregiver=caregiver,
                    plan_content=f"AI-generated plan with {len(sections)} sections"
                )
                plan_id = create_discharge_plan(p.patient_id, plan)

                # Save each section
                for section_name, content in sections.items():
                    update_plan_section(plan_id, section_name, content)

            except Exception as e:
                st.error(f"❌ Failed to generate discharge plan: {str(e)}")
                log(f"AI generation failed: {str(e)}")
                return

        # Run automatic QC review
        with st.spinner("🔍 Running quality checks..."):
            try:
                # Get the saved sections
                current_plan = get_current_plan(p.patient_id)
                sections_dict = get_plan_sections(current_plan.id)

                # Run QC analysis
                qc_flags = generator.review_discharge_plan(
                    patient=p,
                    inpatient=inpatient_data,
                    sections_dict=sections_dict
                )

                # Save QC flags to database
                for flag_data in qc_flags:
                    flag = QCFlag(
                        flag_type=flag_data["flag_type"],
                        severity=flag_data["severity"],
                        message=flag_data["message"],
                        suggested_fix=flag_data.get("suggested_fix", ""),
                        target_section=flag_data.get("target_section", "")
                    )
                    create_qc_flag(p.patient_id, current_plan.id, flag)

                # Determine overall QC status from flags
                if any(f["severity"] == "RED" for f in qc_flags):
                    qc_status = "RED"
                elif any(f["severity"] == "YELLOW" for f in qc_flags):
                    qc_status = "YELLOW"
                else:
                    qc_status = "GREEN"

                # Update patient QC status
                update_patient(p.patient_id, qc_status=qc_status)
                p.qc_status = qc_status

                # Log QC results
                log(f"QC review completed: {qc_status}, {len(qc_flags)} flags")

            except Exception as e:
                st.warning(f"⚠️ QC review failed: {str(e)}. Plan saved, but manual review recommended.")
                log(f"QC review failed: {str(e)}")
                # Default to YELLOW if QC fails
                update_patient(p.patient_id, qc_status="YELLOW")
                p.qc_status = "YELLOW"

        # Update workflow (after plan generation and QC review)
        update_workflow_state(p.patient_id, ai_generation_done=True, qc_analysis_done=True)
        st.session_state.workflow["ai_generation_done"] = True
        st.session_state.workflow["qc_analysis_done"] = True

        # Log success
        log(f"AI-generated plan created: {lang}, {reading}, {len(sections)} sections")

        # Show success message
        st.success(f"✅ Successfully generated {len(sections)} sections!")

        # Show QC results
        if p.qc_status == "GREEN":
            st.success(f"✅ Quality check passed! No issues found.")
        elif p.qc_status == "YELLOW":
            yellow_count = len([f for f in qc_flags if f["severity"] == "YELLOW"])
            st.warning(f"🟡 Quality check found {yellow_count} item(s) to review.")
        elif p.qc_status == "RED":
            red_count = len([f for f in qc_flags if f["severity"] == "RED"])
            st.error(f"🔴 Quality check found {red_count} critical issue(s) that must be resolved.")

        # Show preview of generated sections
        with st.expander("📋 Preview Generated Sections", expanded=True):
            for section_name in sections.keys():
                st.write(f"✓ {section_name}")

        st.info("👉 Navigate to Plan Editor tab to review and edit the generated sections, or QC Review to check quality")

def render_qc_tab(p: Patient):
    st.subheader("QC Review")
    status = p.qc_status
    if status == "GREEN":
        st.success("🟢 GREEN — All safety checks passed. Ready to finalize.")
    elif status == "YELLOW":
        st.warning("🟡 YELLOW — Review recommended. Resolve remaining items.")
    else:
        st.error("🔴 RED — Must resolve safety issues before finalizing.")

    # Action buttons
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("🔁 Re-run QC"):
            # Run actual AI QC review
            try:
                if not OPENAI_API_KEY:
                    st.error("❌ OpenAI API key not configured")
                    return

                # Get current plan and sections
                current_plan = get_current_plan(p.patient_id)
                if not current_plan:
                    st.warning("⚠️ No discharge plan found. Generate a plan first.")
                    return

                inpatient_data = get_inpatient_data(p.patient_id)
                sections_dict = get_plan_sections(current_plan.id)

                # Run AI QC review
                generator = DischargePlanGenerator(OPENAI_API_KEY)
                with st.spinner("🤖 Running AI quality control review..."):
                    qc_flags = generator.review_discharge_plan(
                        patient=p,
                        inpatient=inpatient_data,
                        sections_dict=sections_dict
                    )

                # Mark old flags as resolved
                old_flags = get_qc_flags(p.patient_id, resolved=False)
                for old_flag in old_flags:
                    resolve_qc_flag(old_flag.id)

                # Save new flags
                for flag_data in qc_flags:
                    flag = QCFlag(
                        flag_type=flag_data["flag_type"],
                        severity=flag_data["severity"],
                        message=flag_data["message"],
                        suggested_fix=flag_data.get("suggested_fix", ""),
                        target_section=flag_data.get("target_section", "")
                    )
                    create_qc_flag(p.patient_id, current_plan.id, flag)

                # Update patient QC status
                if any(f["severity"] == "RED" for f in qc_flags):
                    qc_status = "RED"
                elif any(f["severity"] == "YELLOW" for f in qc_flags):
                    qc_status = "YELLOW"
                else:
                    qc_status = "GREEN"

                update_patient(p.patient_id, qc_status=qc_status)
                p.qc_status = qc_status

                # Check QC clearance
                from services.db_operations import check_qc_clearance
                if check_qc_clearance(p.patient_id):
                    update_workflow_state(p.patient_id, qc_clearance_done=True)
                    st.session_state.workflow["qc_clearance_done"] = True
                else:
                    update_workflow_state(p.patient_id, qc_clearance_done=False)
                    st.session_state.workflow["qc_clearance_done"] = False

                log(f"QC re-run completed: {qc_status}, {len(qc_flags)} flags")
                st.success(f"✅ QC review completed: {len(qc_flags)} flags identified")
                st.rerun()

            except Exception as e:
                st.error(f"❌ QC review failed: {str(e)}")
                log(f"QC re-run failed: {str(e)}")

    with c2:
        if st.button("🛠️ Go to Plan Editor"):
            goto_tab("Plan Editor")

    st.divider()

    # Fetch real QC flags from database
    unresolved_flags = get_qc_flags(p.patient_id, resolved=False)
    all_flags = get_qc_flags(p.patient_id)

    # Display summary statistics
    if all_flags:
        red_count = sum(1 for f in unresolved_flags if f.severity == "RED")
        yellow_count = sum(1 for f in unresolved_flags if f.severity == "YELLOW")
        green_count = sum(1 for f in unresolved_flags if f.severity == "GREEN")
        resolved_count = len(all_flags) - len(unresolved_flags)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🔴 RED", red_count)
        with col2:
            st.metric("🟡 YELLOW", yellow_count)
        with col3:
            st.metric("🟢 GREEN", green_count)
        with col4:
            st.metric("✅ Resolved", resolved_count)

        st.divider()

    # Display flags
    st.markdown("### Quality Control Flags")

    if not unresolved_flags:
        if all_flags:
            st.success("🎉 All QC flags have been resolved!")
        elif p.qc_status and p.qc_status in ["GREEN", "YELLOW", "RED"]:
            # QC has run but found no issues - plan is perfect!
            st.success("🎉 No quality issues found! The discharge plan meets all safety and quality standards.")
        else:
            # QC has never been run
            st.info("ℹ️ No QC review has been run yet. Generate a discharge plan first, or click 'Re-run QC' above.")
    else:
        for flag in unresolved_flags:
            # Severity indicator
            if flag.severity == "RED":
                severity_emoji = "🔴"
                severity_color = "red"
            elif flag.severity == "YELLOW":
                severity_emoji = "🟡"
                severity_color = "orange"
            else:
                severity_emoji = "🟢"
                severity_color = "green"

            # Display flag
            with st.container():
                st.markdown(f"**{severity_emoji} {flag.severity}** — _{flag.flag_type}_")
                st.write(flag.message)

                if flag.suggested_fix:
                    with st.expander("💡 Suggested Fix"):
                        st.write(flag.suggested_fix)

                # Action buttons for each flag
                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button(f"✅ Accept Suggestion", key=f"accept_{flag.id}"):
                        st.session_state[f"show_dialog_{flag.id}"] = True
                        st.rerun()

                st.divider()

    # Check if any dialog should be shown (outside the loop to persist across reruns)
    # Only one dialog can be open at a time
    for flag in unresolved_flags:
        if st.session_state.get(f"show_dialog_{flag.id}", False):
            preview_qc_expansion_dialog(flag, p)
            break  # Only open one dialog at a time

def render_plan_editor_tab(p: Patient):
    st.subheader("Plan Editor")
    st.write("Review and edit AI-generated discharge plan sections.")

    # Load current plan and its sections
    plan = get_current_plan(p.patient_id)

    if not plan:
        st.warning("⚠️ No discharge plan found. Please generate a plan first in the Generate tab.")
        return

    # Get all sections from database
    sections_dict = get_plan_sections(plan.id)

    # Section options with completion indicators
    section_options = ["Medications", "Warning Signs", "Mobility", "Diet", "Follow-Ups", "Teach-Back"]

    # Create labels with checkmarks
    def format_section_label(section_name):
        if section_name in sections_dict and sections_dict[section_name]:
            return f"✅ {section_name}"
        else:
            return f"⚪ {section_name}"

    # Section selector
    section = st.selectbox(
        "Section",
        section_options,
        format_func=format_section_label
    )

    # Pre-populate with generated content if exists
    existing_content = sections_dict.get(section, "")
    if not existing_content:
        existing_content = f"[No content generated for {section} section yet]\n\nGenerate a plan in the Generate tab or write content manually here."

    text = st.text_area(
        "Section content",
        height=300,
        value=existing_content,
        help="Edit the AI-generated content or write your own"
    )

    # Show section statistics
    col_stat1, col_stat2 = st.columns(2)
    with col_stat1:
        completed_sections = sum(1 for s in section_options if s in sections_dict and sections_dict[s])
        st.metric("Completed Sections", f"{completed_sections}/6")
    with col_stat2:
        if text:
            st.metric("Current Section Length", f"{len(text)} chars")

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("💾 Save Changes"):
            update_plan_section(plan.id, section, text)
            log(f"Edited section: {section}")
            st.success(f"✅ {section} section saved!")
            st.rerun()
    with c2:
        if st.button("🔁 Re-run QC"):
            update_patient(p.patient_id, qc_status="GREEN")
            p.qc_status = "GREEN"
            update_workflow_state(p.patient_id, qc_analysis_done=True)
            st.session_state.workflow["qc_analysis_done"] = True
            log("QC re-run → GREEN (demo)")
            st.rerun()
    with c3:
        st.caption("💡 Tip: Save each section after editing. Use QC Review tab to check quality.")

def render_finalize_tab(p: Patient):
    st.subheader("Finalize & Export Discharge Plan")

    # QC Status Check
    if p.qc_status != "GREEN":
        st.warning("⚠️ Finalize is disabled until QC status is GREEN. Please resolve all quality issues first.")
        st.stop()

    # Get plan data
    current_plan = get_current_plan(p.patient_id)
    if not current_plan:
        st.warning("⚠️ No discharge plan found. Please generate a plan first.")
        return

    inpatient_data = get_inpatient_data(p.patient_id)
    sections_dict = get_plan_sections(current_plan.id)

    # Display Complete Discharge Plan
    st.divider()
    st.subheader("📋 Complete Discharge Plan")

    # Patient Info Card
    with st.container():
        st.markdown("#### Patient Information")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Name:** {p.name}")
            st.write(f"**MRN:** {p.mrn}")
        with col2:
            st.write(f"**Language:** {p.language}")
            st.write(f"**Disposition:** {p.disposition}")

    st.divider()

    # Clinical Info Card
    with st.container():
        st.markdown("#### Clinical Information")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Stroke Type:** {inpatient_data.stroke_type}")
            st.write(f"**Fall Risk:** {inpatient_data.fall_risk}")
        with col2:
            st.write(f"**Dysphagia Screen:** {inpatient_data.dysphagia}")
            st.write(f"**Anticoagulant:** {'Yes' if inpatient_data.anticoagulant else 'No'}")

    st.divider()

    # Plan Sections Display
    st.markdown("#### Discharge Instructions")
    section_order = ["Medications", "Warning Signs", "Mobility", "Diet", "Follow-Ups", "Teach-Back"]
    for section_name in section_order:
        with st.expander(f"📌 {section_name}", expanded=False):
            content = sections_dict.get(section_name, "")
            if content:
                st.write(content)
            else:
                st.info(f"No {section_name.lower()} instructions available")

    st.divider()

    # Finalization Form
    st.subheader("📝 Finalization Checklist")
    teachback = st.checkbox("Teach-back completed", value=True)
    caregiver = st.checkbox("Caregiver present", value=False)
    interp = st.checkbox("Interpreter used", value=False)
    conf = st.slider("Nurse confidence", 1, 5, 4)

    if st.button("✅ Finalize Discharge Plan"):
        # Save finalization data to database
        finalization = FinalizationData(
            teachback_completed=teachback,
            caregiver_present=caregiver,
            interpreter_used=interp,
            nurse_confidence=conf
        )
        save_finalization_data(p.patient_id, finalization)

        # Update patient workflow status
        update_workflow_state(p.patient_id, final_approval_done=True)
        update_patient(p.patient_id, wf_status="Finalized")

        # Update session state
        p.wf_status = "Finalized"
        st.session_state.workflow["final_approval_done"] = True

        log(f"Finalized plan (Teachback={teachback}, Caregiver={caregiver}, Interpreter={interp}, Confidence={conf})")
        st.success("✅ Discharge plan finalized successfully!")
        st.rerun()

    st.divider()

    # Export Section
    st.subheader("📥 Export")

    # Get finalization data if available
    finalization_data = get_finalization_data(p.patient_id)

    # PDF Download Button
    if st.button("📄 Download Discharge Plan (PDF)", type="primary"):
        try:
            # Import PDF generator
            from services.pdf_generator import DischargePlanPDFGenerator

            # Generate PDF
            with st.spinner("🔄 Generating PDF..."):
                generator = DischargePlanPDFGenerator()
                pdf_bytes = generator.generate_discharge_plan_pdf(
                    patient=p,
                    inpatient=inpatient_data,
                    plan=current_plan,
                    sections_dict=sections_dict,
                    finalization=finalization_data
                )

            # Create download filename
            filename = f"discharge_plan_{p.patient_id}_{current_plan.id}.pdf"

            # Provide download
            st.download_button(
                label="💾 Download PDF",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf"
            )

            log(f"Exported discharge plan as PDF: {filename}")
            st.success("✅ PDF generated successfully!")

        except Exception as e:
            st.error(f"❌ Failed to generate PDF: {str(e)}")
            log(f"PDF generation error: {str(e)}")

def render_audit_tab():
    st.subheader("Audit Log")
    for e in st.session_state.audit_log[:50]:
        st.write(f"`{e.ts}`  {e.msg}")

# -----------------------------
# IMPORTANT NOTE ABOUT st.tabs
# -----------------------------
# Streamlit's native st.tabs renders true tabs, but it does not provide a reliable way
# (today) to programmatically set the active tab from Python in the same run.
# That's why we use a horizontal radio (segmented control) above.
#
# If you still want st.tabs visually, you can render st.tabs and put content into each tab,
# but "deep-linking" from QC → Plan Editor won't be able to automatically switch the active tab.
# The approach above gives you fully controllable "tabs" suitable for your demo workflow.

# -----------------------------
# App entry
# -----------------------------
def main():
    st.set_page_config(page_title="dischargePlanningAgent", layout="wide")

    # Global font size configuration via CSS
    st.markdown("""
        <style>
        /* Global font size adjustments */
        html, body, [class*="css"] {
            font-size: 16px;  /* Base font size - adjust this value */
        }

        /* Headings */
        h1 { font-size: 2.0rem !important; }
        h2 { font-size: 1.6rem !important; }
        h3 { font-size: 1.3rem !important; }
        h4 { font-size: 1.1rem !important; }

        /* Body text */
        p, div, span, label {
            font-size: 1.0rem !important;
        }

        /* Buttons */
        .stButton button {
            font-size: 0.95rem !important;
        }

        /* Input fields */
        input, textarea, select {
            font-size: 0.95rem !important;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            font-size: 0.9rem !important;
        }

        /* Tables */
        table {
            font-size: 0.9rem !important;
        }

        /* Code blocks */
        code {
            font-size: 0.9rem !important;
        }

        /* Captions */
        .caption {
            font-size: 0.85rem !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Initialize database on first run
    init_database()

    init_state()
    render_sidebar()

    # Check if we have patients
    if not st.session_state.patients:
        st.error("No patients found in database. Please add patients first.")
        return

    p = get_patient(st.session_state.selected_patient_id)

    # Safety check
    if p is None:
        st.error("Error loading patient. Please try refreshing the page.")
        return

    # Main area (fixed frame)
    render_header(p)
    st.markdown("### Workflow Progress")
    render_stepper(st.session_state.workflow)
    st.divider()

    # Tab bar + content (only this changes)
    render_tabs(p)

if __name__ == "__main__":
    main()
