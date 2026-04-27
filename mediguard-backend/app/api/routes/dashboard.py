from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.api.dependencies import get_db, get_current_active_user
from app.models.user import User
from app.schemas.base_response import send_success

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("", summary="Get role-specific AI dashboard")
def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role == "admin":
        data = generate_admin_dashboard(db)
    elif current_user.role == "clinician":
        data = generate_doctor_dashboard(db, current_user.id)
    elif current_user.role == "lab_tech":
        data = generate_lab_dashboard(db)
    else:
        data = {"metrics": {}, "ai_insights": [], "action_items": []}

    return send_success(
        data={"role": current_user.role, **data},
        message=f"Dashboard loaded for {current_user.role}"
    )

# ==========================================
# 1. DOCTOR DASHBOARD (Clinical & Patient-Centric)
# ==========================================
def generate_doctor_dashboard(db: Session, doctor_id: str):
    return {
        "metrics": {
            "active_consultations": 3,
            "patients_seen_today": 12,
            "pending_lab_results": 2,
            "average_consult_time_mins": 14
        },
        "active_consultations_list": [
            {"id": "cons-001", "patient_name": "Augustine Watts", "status": "In Progress", "time": "08:00 AM"},
            {"id": "cons-002", "patient_name": "Clementine Baker", "status": "Waiting - Labs", "time": "09:15 AM"},
            {"id": "cons-003", "patient_name": "Jimmie Christian", "status": "Waiting - Triage", "time": "10:30 AM"}
        ],
        "ai_insights": [
            {
                "type": "alert", # Maps to your bell-fill icon
                "title": "Regional Epidemiology Alert",
                "message": "Mombasa is currently experiencing the 'Long Rains' season. Regional data flags a 40% elevated risk for Malaria and Cholera.",
                "action": "View Guidelines"
            },
            {
                "type": "anomaly", # Maps to your exclamation icon
                "title": "Historical Trend Warning",
                "message": "Analysis of your past 7 days of diagnoses shows a 30% spike in Pediatric Gastroenteritis compared to your baseline.",
                "action": "Review Cases"
            }
        ],
        "action_items": [
            {
                "title": "Review urgent CBC results for John Smith", 
                "priority": "high", # Maps to .priority-high CSS
                "tags": ["Labs", "Urgent"],
                "room": "Room 2"
            },
            {
                "title": "Sign off on 2 closed consultation notes", 
                "priority": "medium", 
                "tags": ["Admin"]
            }
        ]
    }

# ==========================================
# 2. LAB TECH DASHBOARD (Operational & Throughput)
# ==========================================
def generate_lab_dashboard(db: Session):
    return {
        "metrics": {
            "queue_size": 18,
            "urgent_tests_pending": 4,
            "average_turnaround_time_hrs": 2.1,
            "critical_values_flagged_today": 2
        },
        "chart_data": {
            "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "datasets": [
                {
                    "label": "Total Tests Processed",
                    "data": [45, 52, 38, 65, 48, 55, 60],
                    "borderColor": "#0EA5E9", 
                    "backgroundColor": "rgba(14, 165, 233, 0.1)",
                    "borderWidth": 2,
                    "tension": 0.4, 
                    "fill": True
                },
                {
                    "label": "Critical Flags",
                    "data": [2, 5, 1, 4, 2, 3, 2],
                    "borderColor": "#EF4444", 
                    "backgroundColor": "#EF4444",
                    "borderWidth": 2,
                    "tension": 0.4,
                    "borderDash": [5, 5] 
                }
            ]
        },
        "ai_insights": [
            {
                "type": "prediction", # Maps to graph-up-arrow icon
                "title": "Capacity Warning",
                "message": "Current queue volume exceeds standard capacity. AI predicts a 45-minute delay in turnaround times by 2:00 PM.",
                "action": "Adjust Queue"
            },
            {
                "type": "anomaly", 
                "title": "Sample Degradation",
                "message": "Sample #8839 (CBC) shows statistical anomalies consistent with a degraded sample. Consider requesting a redraw.",
                "action": "Flag Sample"
            }
        ],
        "action_items": [
            {
                "title": "Process STAT Comprehensive Metabolic Panel", 
                "priority": "high", 
                "room": "Room 4",
                "tags": ["STAT", "Metabolic"]
            },
            {
                "title": "Calibrate Hematology Analyzer", 
                "priority": "medium", 
                "due_time": "In 2 hours",
                "tags": ["Maintenance"]
            }
        ]
    }

# ==========================================
# 3. ADMIN DASHBOARD (Macro Facility & Financial)
# ==========================================
def generate_admin_dashboard(db: Session):
    return {
        "metrics": {
            "total_patients_today": 142,
            "active_staff": 18,
            "average_wait_time_mins": 22,
            "revenue_estimate_today": 4500.00
        },
        "ai_insights": [
            {
                "type": "prediction",
                "title": "Resource Optimization",
                "message": "AI predicts a 30% surge in pediatric cases tomorrow based on historical flu season data. Recommend increasing triage staffing.",
                "action": "Manage Roster"
            },
            {
                "type": "recommendation", # Maps to lightbulb icon
                "title": "Performance Analysis",
                "message": "Lab turnaround times have improved by 12% this week following the implementation of the new AI-flagging system."
            }
        ],
        "action_items": [
            {
                "title": "Approve 3 specialist referral requests", 
                "priority": "high",
                "tags": ["Referrals", "External"]
            },
            {
                "title": "Review weekly system audit logs", 
                "priority": "low",
                "tags": ["Security", "Routine"]
            }
        ]
    }