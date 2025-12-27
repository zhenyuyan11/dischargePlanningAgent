# dischargePlanningAgent

AI-powered stroke discharge planning system with automated plan generation, quality control, and PDF export.

## Overview

dischargePlanningAgent is a Streamlit-based application that uses OpenAI GPT-4 to generate comprehensive, personalized stroke discharge instructions for patients. The system includes built-in quality control, multi-language support, and professional PDF export capabilities.

## Features

- **AI-Powered Plan Generation**: Automated discharge plan creation using OpenAI GPT-4
- **Multi-Language Support**: Generate plans in English, Spanish, Chinese, and more
- **Quality Control Workflow**: Built-in QC review with automated flag detection
- **Customizable Reading Levels**: Adjust plans for 5th-8th grade reading comprehension
- **Professional PDF Export**: Generate print-ready discharge instructions
- **Audit Trail**: Complete tracking of all plan modifications and reviews
- **Patient Dashboard**: Manage multiple patients with searchable interface
- **Caregiver Support**: Optional caregiver-specific instructions

## Technology Stack

- **Frontend**: Streamlit
- **AI/ML**: OpenAI GPT-4
- **Database**: SQLite (development) / PostgreSQL (production)
- **PDF Generation**: ReportLab
- **Language**: Python 3.8+

## Installation

### Prerequisites

- Python 3.8 or higher
- OpenAI API key

### Setup

1. Clone the repository:
```bash
git clone https://github.com/zhenyuyan11/dischargePlanningAgent.git
cd dischargePlanningAgent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root:
```
OPENAI_API_KEY=your-openai-api-key-here
```

4. Run the application:
```bash
streamlit run app/streamlit_app.py
```

5. Open your browser to `http://localhost:8501`

## Configuration

Edit `core/config.py` to customize:
- Hospital name
- PDF styling (colors, fonts)
- Emergency contact numbers

## Usage

### Creating a Discharge Plan

1. **Add Patient**: Use the sidebar to create a new patient or select existing
2. **Enter Clinical Data**: Input stroke type, fall risk, medications, etc.
3. **Generate Plan**: Click "Generate Discharge Plan" to create AI-powered instructions
4. **Quality Review**: Review and address any QC flags
5. **Edit Sections**: Customize individual sections as needed
6. **Finalize**: Complete teach-back and finalize the plan
7. **Export PDF**: Generate professional PDF for patient

### Workflow Stages

- **Draft**: Plan is being created and reviewed
- **QC Review**: Quality control checks in progress
- **Plan Editor**: Manual edits and customization
- **Finalize**: Completing teach-back and final approval
- **Export**: Generate and download PDF

## Security & Compliance

⚠️ **IMPORTANT**: This application handles Protected Health Information (PHI).

### For Production Deployment:

- **DO NOT** use Streamlit Community Cloud for real patient data
- **DO** use HIPAA-compliant hosting (AWS/Azure/GCP with BAA)
- **DO** implement proper authentication and access controls
- **DO** encrypt data at rest and in transit
- **DO** conduct security audits

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed production deployment guidance.

### Development/Demo Use Only:

The current SQLite setup is suitable for:
- Local development
- Demonstration purposes
- Testing with synthetic data

## Project Structure

```
dischargePlanningAgent/
├── app/                  # Application entry points
│   └── streamlit_app.py  # Main Streamlit application
├── core/                 # Core foundation layer
│   ├── models.py         # Data models
│   ├── config.py         # Configuration settings
│   └── database.py       # Database initialization
├── services/             # Business logic layer
│   ├── db_operations.py  # Database CRUD operations
│   ├── openai_service.py # OpenAI integration
│   └── pdf_generator.py  # PDF export functionality
├── tools/                # Development & debugging tools
│   ├── test_openai.py    # OpenAI API testing
│   ├── debug_db.py       # Database debugging
│   └── debug_generation.py # Generation debugging
├── docs/                 # Documentation
│   └── DEPLOYMENT.md     # Deployment guide
├── .streamlit/           # Streamlit configuration
├── requirements.txt      # Python dependencies
├── README.md             # This file
└── .env                  # Environment variables (not in repo)
```

## API Costs

Approximate OpenAI API costs:
- Per discharge plan: $0.60 - $0.90
- 100 patients/day: ~$60-90/month

## Contributing

This is a research/demonstration project. For questions or collaboration:
- Open an issue for bugs or feature requests
- Contact the development team for research collaboration

## Disclaimer

This tool is intended to **assist** healthcare providers in creating discharge instructions. All generated content must be reviewed and approved by qualified medical professionals before use with patients. This system does not replace clinical judgment.

## License

[Specify your license here - e.g., MIT, GPL, or proprietary]

## Acknowledgments

Developed for stroke discharge planning research and quality improvement initiatives.

---

**Note**: Always ensure compliance with local healthcare regulations (HIPAA, GDPR, etc.) when deploying in clinical environments.
