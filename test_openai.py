#!/usr/bin/env python3
"""Test script to verify OpenAI discharge plan generation"""

import sys
from config import OPENAI_API_KEY, validate_config
from openai_service import DischargePlanGenerator
from db_operations import get_patient, get_inpatient_data

def test_generation():
    """Test generating a discharge plan for patient MRN001"""

    # Validate config
    is_valid, message = validate_config()
    if not is_valid:
        print(f"❌ Configuration Error: {message}")
        return False

    print("✅ API key loaded successfully")

    # Load patient data for John Smith (patient_id: p1)
    patient = get_patient("p1")
    if not patient:
        print("❌ Patient p1 not found in database")
        return False

    print(f"✅ Loaded patient: {patient.name} ({patient.mrn})")

    # Load inpatient data
    inpatient_data = get_inpatient_data("p1")
    if not inpatient_data:
        print("❌ No inpatient data found for p1")
        return False

    print(f"✅ Loaded inpatient data: {inpatient_data.stroke_type}, {inpatient_data.fall_risk} fall risk")

    # Initialize generator
    print("\n🤖 Initializing OpenAI GPT-4o...")
    generator = DischargePlanGenerator(OPENAI_API_KEY)

    # Generate discharge plan
    print("🔄 Generating discharge plan (this may take 30-60 seconds)...\n")

    try:
        sections = generator.generate_discharge_plan(
            patient_data=patient,
            inpatient_data=inpatient_data,
            language="EN",
            reading_level="Simplified",
            include_caregiver=True
        )

        print("✅ Generation successful!\n")
        print(f"📋 Generated {len(sections)} sections:\n")

        for section_name, content in sections.items():
            print(f"  ✅ {section_name}: {len(content)} characters")
            # Show first 100 chars as preview
            preview = content[:100].replace('\n', ' ')
            print(f"      Preview: {preview}...\n")

        return True

    except Exception as e:
        print(f"❌ Generation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_generation()
    sys.exit(0 if success else 1)
