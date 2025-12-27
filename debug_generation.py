#!/usr/bin/env python3
"""Debug script to see the raw OpenAI response"""

from config import OPENAI_API_KEY
from openai_service import DischargePlanGenerator
from db_operations import get_patient, get_inpatient_data

# Load patient data
patient = get_patient("p1")
inpatient_data = get_inpatient_data("p1")

# Initialize generator
generator = DischargePlanGenerator(OPENAI_API_KEY)

# Build prompt
prompt = generator._build_prompt(
    patient=patient,
    inpatient=inpatient_data,
    language="EN",
    reading_level="Simplified",
    include_caregiver=True
)

print("=" * 80)
print("PROMPT:")
print("=" * 80)
print(prompt)
print("\n" * 2)

# Call OpenAI
print("=" * 80)
print("Calling OpenAI API...")
print("=" * 80)
response_text = generator._call_openai_with_retry(prompt)

print("\n" * 2)
print("=" * 80)
print("RAW RESPONSE:")
print("=" * 80)
print(response_text)
print("\n" * 2)

# Try parsing
print("=" * 80)
print("PARSING SECTIONS:")
print("=" * 80)
try:
    sections = generator._parse_sections(response_text)
    for section_name, content in sections.items():
        print(f"\n{section_name}: {len(content)} chars")
        print(f"  First 200 chars: {content[:200]}")
except Exception as e:
    print(f"Error parsing: {e}")
