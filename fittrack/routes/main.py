from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import WorkoutSession, WorkoutPlan
from datetime import datetime, timedelta
from app import db
from sqlalchemy import func

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())

    # Sessions this week
    weekly_sessions = WorkoutSession.query.filter(
        WorkoutSession.user_id == current_user.id,
        WorkoutSession.date >= week_start
    ).count()

    # Total sessions
    total_sessions = WorkoutSession.query.filter_by(user_id=current_user.id).count()

    # Last 5 sessions
    recent_sessions = WorkoutSession.query.filter_by(user_id=current_user.id)\
        .order_by(WorkoutSession.date.desc()).limit(5).all()

    # User plans count
    plans_count = WorkoutPlan.query.filter_by(user_id=current_user.id).count()

    # Sessions per day of week (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    sessions_last_30 = WorkoutSession.query.filter(
        WorkoutSession.user_id == current_user.id,
        WorkoutSession.date >= thirty_days_ago
    ).all()

    return render_template('main/dashboard.html',
                           weekly_sessions=weekly_sessions,
                           total_sessions=total_sessions,
                           recent_sessions=recent_sessions,
                           plans_count=plans_count,
                           sessions_last_30=sessions_last_30,
                           today=today)
