# openai_service.py
# OpenAI API integration for discharge plan generation

import time
from openai import OpenAI
from typing import Dict, List
from core.models import Patient, InpatientData, QCFlag


class DischargePlanGenerator:
    """Generate stroke discharge plans using OpenAI GPT-4o"""

    def __init__(self, api_key: str):
        """Initialize the OpenAI client"""
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o"
        self.temperature = 0.3  # Low temperature for medical accuracy

    def generate_discharge_plan(
        self,
        patient_data: Patient,
        inpatient_data: InpatientData,
        language: str,
        reading_level: str,
        include_caregiver: bool
    ) -> Dict[str, str]:
        """
        Generate a comprehensive discharge plan with 6 sections

        Returns:
            Dict with keys: Medications, Warning Signs, Mobility, Diet, Follow-Ups, Teach-Back
        """
        prompt = self._build_prompt(
            patient_data,
            inpatient_data,
            language,
            reading_level,
            include_caregiver
        )

        response_text = self._call_openai_with_retry(prompt)
        sections = self._parse_sections(response_text)

        return sections

    def _build_prompt(
        self,
        patient: Patient,
        inpatient: InpatientData,
        language: str,
        reading_level: str,
        include_caregiver: bool
    ) -> str:
        """Build comprehensive prompt for discharge plan generation"""

        # Language settings
        lang_map = {
            "EN": "English",
            "ES": "Spanish (Español)",
            "ZH": "Chinese (中文)"
        }
        target_language = lang_map.get(language, "English")

        # Reading level guidance
        reading_guidance = {
            "Standard": "Use clear medical terminology with explanations. Target 8th-10th grade reading level.",
            "Simplified": "Use very simple words and short sentences. Avoid medical jargon. Target 5th-6th grade reading level."
        }
        reading_instruction = reading_guidance.get(reading_level, reading_guidance["Simplified"])

        # Build prompt
        prompt = f"""You are a medical discharge planner creating a comprehensive stroke discharge plan.

PATIENT INFORMATION:
- Name: {patient.name}
- MRN: {patient.mrn}
- Language Preference: {target_language}
- Disposition: {patient.disposition}

CLINICAL INFORMATION:
- Stroke Type: {inpatient.stroke_type}
- Fall Risk: {inpatient.fall_risk}
- Dysphagia Screen: {inpatient.dysphagia}
- On Anticoagulant: {"Yes" if inpatient.anticoagulant else "No"}

HOSPITAL SUMMARY:
{inpatient.hospital_summary}

INSTRUCTIONS:
- Generate the discharge plan in {target_language}
- {reading_instruction}
{'- Include specific instructions for caregivers throughout all sections' if include_caregiver else ''}
- Base recommendations on stroke type ({inpatient.stroke_type})
- Address fall risk level ({inpatient.fall_risk})
- Include dysphagia precautions (screen result: {inpatient.dysphagia})
{'- Include anticoagulant warnings and bleeding precautions' if inpatient.anticoagulant else ''}
- Use professional medical language - DO NOT use emojis
- Use bullet points for lists, bold text for emphasis

Generate EXACTLY 6 sections with the following structure. Use these EXACT section headers:

===MEDICATIONS===
[List medications with dosages, timing, and special instructions. Include anticoagulant warnings if applicable. Explain purpose of each medication simply.]

===WARNING SIGNS===
[List emergency symptoms that require calling 911 immediately. Include stroke-specific warning signs. Make this clear and actionable.]

===MOBILITY===
[Include fall prevention strategies based on {inpatient.fall_risk} risk level. List assistive devices if needed. Include PT/OT exercises. Address safety at home.]

===DIET===
[Include dysphagia precautions based on {inpatient.dysphagia} result. Nutrition recommendations. Hydration guidelines. Food textures if needed.]

===FOLLOW-UPS===
[REQUIRED: Include specific follow-up schedule:
- Neurology appointment within 1-2 weeks
- Primary care physician within 1 week
- Physical therapy/Occupational therapy if needed
- Lab work if on anticoagulant (INR check timeline)
- Any specialist referrals (cardiology, endocrinology, etc.)
- Imaging follow-up if needed (carotid ultrasound, echocardiogram)
Provide specific timeframes for each appointment.]

===TEACH-BACK===
[REQUIRED: Create 5-7 teach-back verification questions such as:
- "Can you tell me what medications you'll take and when?"
- "What symptoms would make you call 911?"
- "How will you prevent falls at home?"
- "What foods/drinks should you avoid?" (if dysphagia)
- "When is your follow-up appointment?"
- "What are the signs your stroke might be coming back?"
Make questions specific to this patient's needs.]

CRITICAL: Use the exact section headers shown above (===SECTION NAME===). This is essential for parsing."""

        return prompt

    def _call_openai_with_retry(self, prompt: str, max_retries: int = 2) -> str:
        """Call OpenAI API with automatic retry on failure"""

        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert medical discharge planner specializing in stroke care. Generate accurate, patient-friendly discharge instructions."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=self.temperature,
                    max_tokens=4000
                )

                return response.choices[0].message.content

            except Exception as e:
                if attempt < max_retries:
                    # Exponential backoff
                    wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                    print(f"API call failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # Final attempt failed
                    raise Exception(f"OpenAI API call failed after {max_retries + 1} attempts: {str(e)}")

    def _parse_sections(self, response_text: str) -> Dict[str, str]:
        """Parse the response into 6 sections"""

        sections = {}
        section_names = [
            "MEDICATIONS",
            "WARNING SIGNS",
            "MOBILITY",
            "DIET",
            "FOLLOW-UPS",
            "TEACH-BACK"
        ]

        # Split by section markers
        for i, section_name in enumerate(section_names):
            marker = f"==={section_name}==="

            if marker in response_text:
                # Find start of this section
                start_idx = response_text.find(marker) + len(marker)

                # Find start of next section (or end of text)
                if i < len(section_names) - 1:
                    next_marker = f"==={section_names[i + 1]}==="
                    end_idx = response_text.find(next_marker)
                    if end_idx == -1:
                        end_idx = len(response_text)
                else:
                    end_idx = len(response_text)

                # Extract and clean content
                content = response_text[start_idx:end_idx].strip()
                sections[section_name.title()] = content
            else:
                # Section not found - add placeholder
                sections[section_name.title()] = f"[{section_name.title()} content not generated]"

        # Verify we got all 6 sections
        if len(sections) != 6:
            raise Exception(f"Expected 6 sections, got {len(sections)}")

        return sections

    def review_discharge_plan(
        self,
        patient: Patient,
        inpatient: InpatientData,
        sections_dict: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """
        Review discharge plan for quality issues

        Returns:
            List of dicts with keys: flag_type, severity, message, suggested_fix
        """
        prompt = self._build_qc_prompt(patient, inpatient, sections_dict)
        response_text = self._call_openai_with_retry(prompt)

        # Parse JSON response
        try:
            import json
            # Extract JSON from response (handle potential markdown code blocks)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()

            flags = json.loads(json_text)
            return flags if isinstance(flags, list) else []
        except Exception as e:
            print(f"Error parsing QC response: {e}")
            print(f"Response text: {response_text[:500]}")
            return []

    def _build_qc_prompt(
        self,
        patient: Patient,
        inpatient: InpatientData,
        sections_dict: Dict[str, str]
    ) -> str:
        """Build comprehensive QC review prompt"""

        # Format sections for review
        sections_text = ""
        for section_name, content in sections_dict.items():
            sections_text += f"\n\n===={section_name.upper()}====\n{content}"

        prompt = f"""You are a medical quality control reviewer for stroke discharge plans.

PATIENT INFORMATION:
- Name: {patient.name}
- MRN: {patient.mrn}
- Disposition: {patient.disposition}

CLINICAL INFORMATION:
- Stroke Type: {inpatient.stroke_type}
- Fall Risk: {inpatient.fall_risk}
- Dysphagia Screen: {inpatient.dysphagia}
- On Anticoagulant: {"Yes" if inpatient.anticoagulant else "No"}

HOSPITAL SUMMARY:
{inpatient.hospital_summary}

DISCHARGE PLAN TO REVIEW:
{sections_text}

INSTRUCTIONS:
Review the discharge plan for quality issues. Check for:

1. COMPLETENESS:
   - All sections have appropriate content
   - Medication lists are present
   - Follow-up appointments specified with timelines
   - Emergency warning signs included
   - No missing critical information

2. SAFETY:
   - Anticoagulant bleeding precautions present if patient on anticoagulants
   - Fall prevention strategies appropriate for {inpatient.fall_risk} fall risk
   - Dysphagia precautions match screen result ({inpatient.dysphagia})
   - Emergency warning signs clearly listed
   - All critical safety information included

3. CONSISTENCY:
   - Recommendations match stroke type ({inpatient.stroke_type})
   - Fall prevention matches fall risk level ({inpatient.fall_risk})
   - Diet instructions match dysphagia status ({inpatient.dysphagia})
   - No contradictions between sections

4. MEDICAL ACCURACY:
   - Medication dosages are appropriate
   - No contraindicated medications
   - Recommendations are medically sound
   - Follows stroke discharge guidelines (AHA/NINDS)

For each issue found, return a JSON object with:
- flag_type: Category of issue (e.g., "Safety - Anticoagulant", "Completeness - Medications", "Consistency - Fall Risk")
- severity: "RED" for critical safety issues, "YELLOW" for important but not critical, "GREEN" for minor suggestions
- message: Clear description of the issue
- suggested_fix: Specific text to add/modify to fix the issue
- target_section: Which section to update with the fix. Must be one of: "Medications", "Warning Signs", "Mobility", "Diet", "Follow-Ups", "Teach-Back"

SEVERITY GUIDELINES:
- RED: Missing anticoagulant warnings, missing emergency signs, medically incorrect info, missing critical medications
- YELLOW: Missing follow-up timelines, incomplete sections, minor inconsistencies, missing recommended but non-critical info
- GREEN: Minor improvements, style suggestions

Return ONLY a JSON array of flags. If no issues found, return an empty array [].

Example format:
[
  {{
    "flag_type": "Safety - Anticoagulant",
    "severity": "RED",
    "message": "Bleeding precautions missing. Patient is on anticoagulant.",
    "suggested_fix": "⚠️ BLEEDING PRECAUTIONS: Call doctor if you notice unusual bleeding, bruising, blood in urine/stool, or severe headaches. Avoid activities with high fall/injury risk.",
    "target_section": "Warning Signs"
  }}
]"""

        return prompt

    def generate_hospital_summary(
        self,
        patient_name: str,
        stroke_type: str,
        fall_risk: str,
        dysphagia: str,
        anticoagulant: bool,
        disposition: str
    ) -> str:
        """
        Generate a realistic hospital summary using AI

        Returns:
            Realistic 2-3 paragraph hospital summary
        """

        prompt = f"""Generate a realistic hospital summary for a stroke patient with the following characteristics:

Patient: {patient_name}
Stroke Type: {stroke_type}
Fall Risk: {fall_risk}
Dysphagia Screen: {dysphagia}
On Anticoagulant: {"Yes" if anticoagulant else "No"}
Discharge Disposition: {disposition}

Write a brief 2-3 paragraph hospital summary that includes:
- Chief complaint and presentation
- Relevant medical history (hypertension, diabetes, atrial fibrillation, etc. as appropriate)
- Hospital course and interventions
- Current status and reason for discharge
- Any complications or concerns

Make it sound like a real medical summary written by a healthcare professional. Be specific but concise.
Use appropriate medical terminology. Do not include discharge instructions or plans."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a medical professional writing concise hospital summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,  # Higher temperature for variety
                max_tokens=400
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            # Fallback to template if API fails
            return f"""Patient presented to ED with acute onset neurological deficits consistent with {stroke_type.lower()} stroke. Imaging confirmed diagnosis. Patient received appropriate acute stroke interventions per protocol. Hospital course complicated by {fall_risk.lower()} fall risk. Dysphagia screen {dysphagia.lower()}. Currently stable and appropriate for discharge to {disposition}."""

    def expand_qc_suggestion(
        self,
        patient: Patient,
        inpatient: InpatientData,
        sections_dict: Dict[str, str],
        qc_flag: QCFlag,
        suggested_fix_text: str
    ) -> str:
        """Expand QC suggestion into comprehensive, ready-to-insert content"""

        prompt = self._build_expansion_prompt(
            patient, inpatient, sections_dict, qc_flag, suggested_fix_text
        )

        expanded_content = self._call_openai_with_retry(prompt)

        # Clean up markdown artifacts and unwanted titles
        expanded_content = expanded_content.strip()
        if expanded_content.startswith("```"):
            lines = expanded_content.split("\n")
            expanded_content = "\n".join(lines[1:-1]).strip()

        # Remove any section titles that might have been generated
        # e.g., "Medications for Ann Lee" or "Mobility:"
        lines = expanded_content.split("\n")
        if lines:
            first_line = lines[0].strip()
            # Check if first line looks like a title (short line ending with patient name or colon)
            if len(first_line) < 60 and (
                patient.name.split()[0] in first_line or  # First name in title
                patient.name.split()[-1] in first_line or  # Last name in title
                first_line.endswith(":") or  # Section name with colon
                first_line.startswith("#")  # Markdown header
            ):
                # Remove the first line (it's likely a title)
                expanded_content = "\n".join(lines[1:]).strip()

        return expanded_content

    def _build_expansion_prompt(
        self,
        patient: Patient,
        inpatient: InpatientData,
        sections_dict: Dict[str, str],
        qc_flag: QCFlag,
        suggested_fix_text: str
    ) -> str:
        """Build prompt to regenerate entire section with QC suggestion applied"""

        target_section = qc_flag.target_section
        current_section_content = sections_dict.get(target_section, "")

        # Get section-specific instructions from original generation
        section_instructions = {
            "Medications": "List medications with dosages, timing, and special instructions. Include anticoagulant warnings if applicable. Explain purpose of each medication simply.",
            "Warning Signs": "List emergency symptoms that require calling 911 immediately. Include stroke-specific warning signs. Make this clear and actionable.",
            "Mobility": f"Include fall prevention strategies based on {inpatient.fall_risk} risk level. List assistive devices if needed. Include PT/OT exercises. Address safety at home.",
            "Diet": f"Include dysphagia precautions based on {inpatient.dysphagia} result. Nutrition recommendations. Hydration guidelines. Food textures if needed.",
            "Follow-Ups": "Include specific follow-up schedule with timeframes (neurology, primary care, PT/OT, lab work if on anticoagulant, specialist referrals, imaging).",
            "Teach-Back": "Create 5-7 teach-back verification questions specific to this patient's needs (medications, warning signs, fall prevention, diet, follow-ups)."
        }

        section_guidance = section_instructions.get(target_section, "Provide comprehensive, patient-specific guidance.")

        # Severity-specific emphasis
        severity_emphasis = {
            "RED": "CRITICAL: This is a safety issue. Address it with clear, direct, actionable language.",
            "YELLOW": "IMPORTANT: This needs attention. Provide clear, helpful guidance.",
            "GREEN": "Enhancement: Improve clarity and completeness."
        }
        emphasis = severity_emphasis.get(qc_flag.severity, severity_emphasis["YELLOW"])

        prompt = f"""You are an expert medical discharge planner specializing in stroke care. You are regenerating a section of a discharge plan to address a quality control concern.

IMPORTANT: Write ALL content in English. Use 5th-6th grade reading level. Be patient-friendly and actionable.

PATIENT INFORMATION:
- Name: {patient.name}, MRN: {patient.mrn}
- Language Preference: {patient.language} (write in English, note language for context only)
- Disposition: {patient.disposition}

CLINICAL INFORMATION:
- Stroke Type: {inpatient.stroke_type}
- Fall Risk: {inpatient.fall_risk}
- Dysphagia Screen: {inpatient.dysphagia}
- On Anticoagulant: {"Yes" if inpatient.anticoagulant else "No"}

HOSPITAL SUMMARY:
{inpatient.hospital_summary[:500]}...

SECTION TO REGENERATE: {target_section}

CURRENT SECTION CONTENT:
{current_section_content if current_section_content and not current_section_content.strip().startswith("[") else "[Empty - needs to be generated from scratch]"}

QUALITY CONTROL ISSUE ({qc_flag.severity} priority):
{qc_flag.message}

REQUIRED CHANGES:
{suggested_fix_text}

{emphasis}

TASK:
Regenerate the ENTIRE "{target_section}" section by:
1. **MUST INCLUDE the required changes** - The content from "REQUIRED CHANGES" above MUST appear in your output
2. **Preserving good content** - Keep existing accurate information that doesn't conflict with the required changes
3. **Integrating changes naturally** - Weave the required changes seamlessly into the section

SECTION REQUIREMENTS:
{section_guidance}

FORMATTING INSTRUCTIONS:
- DO NOT use emojis - use professional medical language only
- Use bullet points for lists
- Use **bold** for emphasis on important information
- Keep paragraphs short (2-3 sentences max)
- Use simple words and clear language (5th-6th grade level)
- Make content specific to this patient's stroke type, fall risk, and clinical needs

CRITICAL RULES:
- Output ONLY the section content (no headers, no titles, no meta-commentary)
- Do NOT include section headers like "===MOBILITY==="
- Do NOT include titles like "Medications for [Patient Name]"
- Start directly with the content (bullet points or paragraphs)
- **MANDATORY**: The "REQUIRED CHANGES" content MUST be included in your regenerated section
- If current section is empty/placeholder, generate complete section from scratch including the required changes
- If current section has content, integrate the required changes while preserving non-conflicting existing content
- Do NOT duplicate information from other sections
- The required changes should flow naturally within the section, not appear as a separate appendix

OUTPUT (content only, no titles or headers):"""

        return prompt