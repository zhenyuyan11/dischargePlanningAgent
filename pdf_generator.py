# pdf_generator.py
# Professional PDF generation for stroke discharge plans using reportlab

from io import BytesIO
from datetime import datetime
from typing import Dict, Optional
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, ListFlowable, ListItem
from reportlab.platypus.flowables import KeepTogether
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from models import Patient, InpatientData, DischargePlan, FinalizationData


class DischargePlanPDFGenerator:
    """Generates professional PDF documents for stroke discharge plans"""

    def __init__(self):
        """Initialize PDF generator with styling and configuration"""
        # Page dimensions
        self.page_width, self.page_height = letter
        self.margin = 0.75 * inch

        # Colors
        self.header_color = colors.HexColor("#003366")  # Professional blue
        self.text_color = colors.black
        self.light_gray = colors.HexColor("#F0F0F0")

        # Fonts and sizes
        self.title_font = "Helvetica-Bold"
        self.title_size = 16
        self.section_font = "Helvetica-Bold"
        self.section_size = 14
        self.body_font = "Helvetica"
        self.body_size = 11
        self.small_font = "Helvetica"
        self.small_size = 9

        # Get base styles
        self.styles = getSampleStyleSheet()

        # Custom styles
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontName=self.title_font,
            fontSize=self.title_size,
            textColor=self.header_color,
            alignment=TA_CENTER,
            spaceAfter=12
        )

        self.section_style = ParagraphStyle(
            'CustomSection',
            parent=self.styles['Heading2'],
            fontName=self.section_font,
            fontSize=self.section_size,
            textColor=self.header_color,
            spaceAfter=6,
            spaceBefore=12
        )

        self.body_style = ParagraphStyle(
            'CustomBody',
            parent=self.styles['BodyText'],
            fontName=self.body_font,
            fontSize=self.body_size,
            textColor=self.text_color,
            alignment=TA_LEFT,
            leading=13  # Line spacing
        )

        self.small_style = ParagraphStyle(
            'CustomSmall',
            parent=self.styles['Normal'],
            fontName=self.small_font,
            fontSize=self.small_size,
            textColor=colors.gray,
            alignment=TA_CENTER
        )

    def generate_discharge_plan_pdf(
        self,
        patient: Patient,
        inpatient: InpatientData,
        plan: DischargePlan,
        sections_dict: Dict[str, str],
        finalization: Optional[FinalizationData] = None
    ) -> bytes:
        """
        Generate a professional PDF discharge plan

        Args:
            patient: Patient demographics
            inpatient: Clinical information
            plan: Discharge plan metadata
            sections_dict: Dictionary of section names to content
            finalization: Optional finalization metadata

        Returns:
            PDF file as bytes
        """
        # Create PDF in memory
        buffer = BytesIO()

        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=self.margin,
            leftMargin=self.margin,
            topMargin=self.margin + 0.5*inch,  # Extra space for header
            bottomMargin=self.margin + 0.3*inch  # Extra space for footer
        )

        # Build content
        story = []

        # Title
        story.append(Paragraph("STROKE DISCHARGE INSTRUCTIONS", self.title_style))
        story.append(Spacer(1, 0.2*inch))

        # Patient Information Section
        story.extend(self._add_patient_info_section(patient))
        story.append(Spacer(1, 0.2*inch))

        # Clinical Information Section
        story.extend(self._add_clinical_info_section(inpatient))
        story.append(Spacer(1, 0.3*inch))

        # Discharge Plan Sections
        section_order = ["Medications", "Warning Signs", "Mobility", "Diet", "Follow-Ups", "Teach-Back"]
        for section_name in section_order:
            content = sections_dict.get(section_name, "")
            story.extend(self._add_plan_section(section_name, content))

        # Finalization/Signature Section
        if finalization:
            story.append(Spacer(1, 0.3*inch))
            story.extend(self._add_signature_section(finalization))

        # Build PDF with header and footer
        doc.build(
            story,
            onFirstPage=self._add_header_footer,
            onLaterPages=self._add_header_footer
        )

        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    def _add_patient_info_section(self, patient: Patient) -> list:
        """Create patient demographics table"""
        elements = []

        elements.append(Paragraph("PATIENT INFORMATION", self.section_style))

        # Create table data
        data = [
            ["Patient Name:", patient.name, "Language:", patient.language],
            ["Medical Record #:", patient.mrn, "Disposition:", patient.disposition]
        ]

        # Create table
        table = Table(data, colWidths=[1.5*inch, 2.5*inch, 1.2*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.light_gray),
            ('BACKGROUND', (2, 0), (2, -1), self.light_gray),
            ('FONTNAME', (0, 0), (0, -1), self.section_font),
            ('FONTNAME', (2, 0), (2, -1), self.section_font),
            ('FONTNAME', (1, 0), (-1, -1), self.body_font),
            ('FONTSIZE', (0, 0), (-1, -1), self.body_size),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(table)
        return elements

    def _add_clinical_info_section(self, inpatient: InpatientData) -> list:
        """Create clinical information table"""
        elements = []

        elements.append(Paragraph("CLINICAL INFORMATION", self.section_style))

        # Create table data
        anticoag_status = "Yes" if inpatient.anticoagulant else "No"
        data = [
            ["Stroke Type:", inpatient.stroke_type, "Dysphagia Screen:", inpatient.dysphagia],
            ["Fall Risk Level:", inpatient.fall_risk, "On Anticoagulant:", anticoag_status]
        ]

        # Create table
        table = Table(data, colWidths=[1.5*inch, 2.5*inch, 1.5*inch, 1.7*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.light_gray),
            ('BACKGROUND', (2, 0), (2, -1), self.light_gray),
            ('FONTNAME', (0, 0), (0, -1), self.section_font),
            ('FONTNAME', (2, 0), (2, -1), self.section_font),
            ('FONTNAME', (1, 0), (-1, -1), self.body_font),
            ('FONTSIZE', (0, 0), (-1, -1), self.body_size),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(table)
        return elements

    def _add_plan_section(self, section_name: str, content: str) -> list:
        """Format a discharge plan section with markdown and emoji support"""
        elements = []

        # Section header
        elements.append(Paragraph(section_name.upper(), self.section_style))

        # Section content
        if content:
            elements.extend(self._parse_and_format_content(content))
        else:
            elements.append(Paragraph("<i>No specific instructions for this section.</i>", self.body_style))
            elements.append(Spacer(1, 0.1*inch))

        return elements

    def _parse_and_format_content(self, content: str) -> list:
        """Parse markdown-style content and convert to formatted PDF elements"""
        elements = []

        # Split into lines
        lines = content.split('\n')

        bullet_items = []
        current_paragraph = []

        for line in lines:
            line_stripped = line.strip()

            # Skip empty lines
            if not line_stripped:
                # Flush current paragraph
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    para_formatted = self._format_markdown(para_text)
                    elements.append(Paragraph(para_formatted, self.body_style))
                    elements.append(Spacer(1, 0.08*inch))
                    current_paragraph = []

                # Flush bullet items
                if bullet_items:
                    elements.extend(self._create_bullet_list(bullet_items))
                    bullet_items = []
                    elements.append(Spacer(1, 0.08*inch))
                continue

            # Check if line is a bullet point
            if line_stripped.startswith('-') or line_stripped.startswith('•') or line_stripped.startswith('*'):
                # Flush current paragraph first
                if current_paragraph:
                    para_text = ' '.join(current_paragraph)
                    para_formatted = self._format_markdown(para_text)
                    elements.append(Paragraph(para_formatted, self.body_style))
                    elements.append(Spacer(1, 0.08*inch))
                    current_paragraph = []

                # Extract bullet content (remove bullet marker)
                bullet_text = re.sub(r'^[-•*]\s*', '', line_stripped)
                bullet_items.append(bullet_text)
            else:
                # Flush bullet items first
                if bullet_items:
                    elements.extend(self._create_bullet_list(bullet_items))
                    bullet_items = []
                    elements.append(Spacer(1, 0.08*inch))

                # Add to current paragraph
                current_paragraph.append(line_stripped)

        # Flush any remaining content
        if current_paragraph:
            para_text = ' '.join(current_paragraph)
            para_formatted = self._format_markdown(para_text)
            elements.append(Paragraph(para_formatted, self.body_style))
            elements.append(Spacer(1, 0.08*inch))

        if bullet_items:
            elements.extend(self._create_bullet_list(bullet_items))
            elements.append(Spacer(1, 0.08*inch))

        return elements

    def _format_markdown(self, text: str) -> str:
        """Convert markdown formatting to HTML tags for ReportLab"""
        # Convert **bold** to <b>bold</b>
        text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)

        # Convert *italic* to <i>italic</i> (only single asterisks not part of double)
        text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)

        # Handle emojis - keep them but ensure they're properly encoded
        # ReportLab can render many emojis if the text is properly formatted
        # Common emojis used in discharge plans should work in most PDF readers

        return text

    def _create_bullet_list(self, items: list) -> list:
        """Create a formatted bullet list"""
        elements = []

        # Create custom bullet style
        bullet_style = ParagraphStyle(
            'BulletStyle',
            parent=self.body_style,
            leftIndent=20,
            bulletIndent=10,
            spaceBefore=3,
            spaceAfter=3
        )

        for item in items:
            # Format markdown in bullet text
            item_formatted = self._format_markdown(item)
            # Add bullet point manually
            bullet_text = f"• {item_formatted}"
            elements.append(Paragraph(bullet_text, bullet_style))

        return elements

    def _add_signature_section(self, finalization: FinalizationData) -> list:
        """Add finalization metadata and signature section"""
        elements = []

        elements.append(Paragraph("DISCHARGE CERTIFICATION", self.section_style))

        # Create finalization data table
        teachback = "Yes" if finalization.teachback_completed else "No"
        caregiver = "Yes" if finalization.caregiver_present else "No"
        interpreter = "Yes" if finalization.interpreter_used else "No"

        data = [
            ["Teach-back Completed:", teachback],
            ["Caregiver Present:", caregiver],
            ["Interpreter Used:", interpreter],
            ["Nurse Confidence Level:", f"{finalization.nurse_confidence}/5"],
            ["Finalized At:", finalization.finalized_at or "N/A"]
        ]

        table = Table(data, colWidths=[2.5*inch, 4.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.light_gray),
            ('FONTNAME', (0, 0), (0, -1), self.section_font),
            ('FONTNAME', (1, 0), (-1, -1), self.body_font),
            ('FONTSIZE', (0, 0), (-1, -1), self.body_size),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(table)
        return elements

    def _add_header_footer(self, canvas, doc):
        """Add header and footer to each page"""
        canvas.saveState()

        # Header
        canvas.setFont(self.title_font, 10)
        canvas.setFillColor(self.header_color)
        canvas.drawString(self.margin, self.page_height - 0.5*inch, "STROKE DISCHARGE INSTRUCTIONS")

        canvas.setFont(self.body_font, 9)
        canvas.setFillColor(colors.gray)
        generation_date = datetime.now().strftime("%B %d, %Y")
        canvas.drawRightString(self.page_width - self.margin, self.page_height - 0.5*inch, f"Generated: {generation_date}")

        # Header line
        canvas.setStrokeColor(self.header_color)
        canvas.setLineWidth(1)
        canvas.line(self.margin, self.page_height - 0.6*inch, self.page_width - self.margin, self.page_height - 0.6*inch)

        # Footer
        canvas.setFont(self.small_font, self.small_size)
        canvas.setFillColor(colors.gray)

        # Page number
        page_num = f"Page {doc.page}"
        canvas.drawCentredString(self.page_width / 2, 0.5*inch, page_num)

        # Emergency contact
        canvas.drawString(self.margin, 0.5*inch, "EMERGENCY: Call 911 for immediate medical assistance")

        # Confidentiality notice
        canvas.drawRightString(self.page_width - self.margin, 0.5*inch, "CONFIDENTIAL MEDICAL INFORMATION")

        canvas.restoreState()
