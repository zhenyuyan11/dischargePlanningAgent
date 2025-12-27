#!/usr/bin/env python3
"""
Database debugging utility for stroke discharge app
Run: python3 debug_db.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "stroke_discharge.db"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def view_all_data():
    """View all data in the database"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Patients
    print_section("PATIENTS")
    cursor.execute("SELECT * FROM patients ORDER BY created_at DESC")
    for row in cursor.fetchall():
        print(f"  {row['patient_id']}: {row['name']} (MRN: {row['mrn']})")
        print(f"    Language: {row['language']}, Disposition: {row['disposition']}")
        print(f"    QC Status: {row['qc_status']}, Workflow: {row['wf_status']}")
        print()

    # Inpatient Data
    print_section("INPATIENT DATA")
    cursor.execute("""
        SELECT i.*, p.name
        FROM inpatient_data i
        JOIN patients p ON i.patient_id = p.patient_id
        ORDER BY i.created_at DESC
    """)
    for row in cursor.fetchall():
        print(f"  {row['name']} ({row['patient_id']}):")
        print(f"    Stroke: {row['stroke_type']}, Fall Risk: {row['fall_risk']}")
        print(f"    Dysphagia: {row['dysphagia']}, Anticoag: {bool(row['anticoagulant'])}")
        if row['hospital_summary']:
            summary = row['hospital_summary'][:80] + "..." if len(row['hospital_summary']) > 80 else row['hospital_summary']
            print(f"    Summary: {summary}")
        print()

    # Discharge Plans
    print_section("DISCHARGE PLANS")
    cursor.execute("""
        SELECT d.*, p.name
        FROM discharge_plans d
        JOIN patients p ON d.patient_id = p.patient_id
        ORDER BY d.created_at DESC
    """)
    plans = cursor.fetchall()
    if plans:
        for row in plans:
            current = "✓ CURRENT" if row['is_current'] else ""
            print(f"  Plan #{row['id']} for {row['name']} (v{row['version']}) {current}")
            print(f"    Language: {row['language']}, Reading: {row['reading_level']}")
            print(f"    Created: {row['created_at']}")
            print()
    else:
        print("  No discharge plans yet")
        print()

    # Workflow States
    print_section("WORKFLOW STATES")
    cursor.execute("""
        SELECT w.*, p.name
        FROM workflow_state w
        JOIN patients p ON w.patient_id = p.patient_id
    """)
    for row in cursor.fetchall():
        print(f"  {row['name']} ({row['patient_id']}):")
        steps = []
        # Use dict() to convert Row to dict for .get() support
        row_dict = dict(row)
        if row_dict.get('hospital_summary_done') or row_dict.get('intake_done'):
            steps.append("✓ Hospital Summary")
        if row_dict.get('ai_generation_done') or row_dict.get('generate_done'):
            steps.append("✓ AI Generation")
        if row_dict.get('qc_analysis_done') or row_dict.get('qc_done'):
            steps.append("✓ QC Analysis")
        if row_dict.get('qc_clearance_done') or row_dict.get('edit_done'):
            steps.append("✓ QC Clearance")
        if row_dict.get('final_approval_done') or row_dict.get('finalize_done'):
            steps.append("✓ Final Approval")
        print(f"    {' → '.join(steps) if steps else 'Not started'}")
        print()

    # Audit Log (last 10)
    print_section("AUDIT LOG (Last 10 Events)")
    cursor.execute("""
        SELECT a.*, p.name
        FROM audit_log a
        LEFT JOIN patients p ON a.patient_id = p.patient_id
        ORDER BY a.timestamp DESC
        LIMIT 10
    """)
    for row in cursor.fetchall():
        patient_info = f"[{row['name']}]" if row['name'] else "[System]"
        print(f"  {row['timestamp']} {patient_info}: {row['message']}")

    # Plan Sections
    print_section("PLAN SECTIONS")
    cursor.execute("""
        SELECT s.*, d.patient_id, p.name
        FROM plan_sections s
        JOIN discharge_plans d ON s.plan_id = d.id
        JOIN patients p ON d.patient_id = p.patient_id
        ORDER BY s.updated_at DESC
    """)
    sections = cursor.fetchall()
    if sections:
        for row in sections:
            print(f"  {row['name']} - {row['section_name']}:")
            content_preview = row['section_content'][:60] + "..." if len(row['section_content']) > 60 else row['section_content']
            print(f"    {content_preview}")
            print()
    else:
        print("  No plan sections edited yet")
        print()

    # Finalization Data
    print_section("FINALIZATION DATA")
    cursor.execute("""
        SELECT f.*, p.name
        FROM finalization_data f
        JOIN patients p ON f.patient_id = p.patient_id
        ORDER BY f.finalized_at DESC
    """)
    finalizations = cursor.fetchall()
    if finalizations:
        for row in finalizations:
            print(f"  {row['name']} ({row['patient_id']}):")
            print(f"    Teachback: {bool(row['teachback_completed'])}, Caregiver: {bool(row['caregiver_present'])}")
            print(f"    Interpreter: {bool(row['interpreter_used'])}, Confidence: {row['nurse_confidence']}/5")
            print(f"    Finalized: {row['finalized_at']}")
            print()
    else:
        print("  No finalizations yet")
        print()

    conn.close()

def reset_database():
    """Reset database to initial demo state"""
    import os
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("✓ Database deleted")

    from database import init_database
    init_database()
    print("✓ Database recreated with demo data")

def run_custom_query(query):
    """Run a custom SQL query"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(query)

        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            if rows:
                # Print column names
                print("  " + " | ".join(rows[0].keys()))
                print("  " + "-" * 60)
                # Print rows
                for row in rows:
                    print("  " + " | ".join(str(v) for v in row))
            else:
                print("  No results")
        else:
            conn.commit()
            print(f"  ✓ Query executed. Rows affected: {cursor.rowcount}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    finally:
        conn.close()

def interactive_mode():
    """Interactive SQL console"""
    print("\n" + "="*60)
    print("  INTERACTIVE MODE")
    print("="*60)
    print("  Enter SQL queries (or 'exit' to quit)")
    print("  Examples:")
    print("    SELECT * FROM patients;")
    print("    UPDATE patients SET qc_status='GREEN' WHERE patient_id='p1';")
    print("    DELETE FROM patients WHERE patient_id='p4';")
    print("="*60 + "\n")

    while True:
        try:
            query = input("SQL> ").strip()
            if query.lower() in ['exit', 'quit', 'q']:
                break
            if query:
                run_custom_query(query)
                print()
        except KeyboardInterrupt:
            print("\n✓ Exiting interactive mode")
            break
        except EOFError:
            break

def main():
    import sys

    if not DB_PATH.exists():
        print(f"✗ Database not found at: {DB_PATH}")
        print("  Run the Streamlit app first to create it.")
        return

    print(f"Database: {DB_PATH}")

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "view":
            view_all_data()
        elif command == "reset":
            confirm = input("⚠️  Reset database to demo state? This will DELETE all data! (yes/no): ")
            if confirm.lower() == "yes":
                reset_database()
            else:
                print("Cancelled")
        elif command == "sql":
            interactive_mode()
        elif command == "query":
            if len(sys.argv) > 2:
                query = " ".join(sys.argv[2:])
                run_custom_query(query)
            else:
                print("Usage: python3 debug_db.py query SELECT * FROM patients;")
        else:
            print(f"Unknown command: {command}")
            print_help()
    else:
        # Default: view all data
        view_all_data()

def print_help():
    print("""
Usage: python3 debug_db.py [command]

Commands:
  (none)       View all data in database (default)
  view         View all data in database
  reset        Reset database to initial demo state
  sql          Interactive SQL console
  query SQL    Run a custom SQL query

Examples:
  python3 debug_db.py
  python3 debug_db.py view
  python3 debug_db.py reset
  python3 debug_db.py sql
  python3 debug_db.py query "SELECT * FROM patients WHERE qc_status='RED'"
""")

if __name__ == "__main__":
    main()
