from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import WorkoutSession, WorkoutPlan, MuscleGroup
from datetime import datetime, timedelta
from app import db

main_bp = Blueprint('main', __name__)


@main_bp.route('/health')
def health():
    return 'ok', 200


@main_bp.route('/')
def index():
    from flask_login import current_user
    if current_user.is_authenticated:
        return dashboard()
    from flask import render_template
    return render_template('auth/login.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    today = datetime.utcnow().date()
    week_start  = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    weekly_sessions = WorkoutSession.query.filter(
        WorkoutSession.user_id == current_user.id,
        WorkoutSession.date >= week_start
    ).count()

    monthly_sessions = WorkoutSession.query.filter(
        WorkoutSession.user_id == current_user.id,
        WorkoutSession.date >= month_start
    ).count()

    # Last 7 sessions with effective muscle groups
    recent_sessions_raw = (
        WorkoutSession.query
        .filter_by(user_id=current_user.id)
        .order_by(WorkoutSession.date.desc())
        .limit(7).all()
    )
    recent_sessions = [
        {'session': s, 'groups': s.effective_muscle_groups}
        for s in recent_sessions_raw
    ]

    # All sessions for group analysis
    all_sessions = (
        WorkoutSession.query
        .filter_by(user_id=current_user.id)
        .order_by(WorkoutSession.date.desc())
        .all()
    )

    # Muscle group last trained date
    all_groups = MuscleGroup.query.all()
    group_last_trained = {}
    for s in all_sessions:
        for mg in s.effective_muscle_groups:
            if mg.id not in group_last_trained:
                group_last_trained[mg.id] = s.date

    group_suggestions = []
    for g in all_groups:
        last = group_last_trained.get(g.id)
        days_ago = (today - last).days if last else None
        group_suggestions.append({'group': g, 'last_date': last, 'days_ago': days_ago})
    group_suggestions.sort(
        key=lambda x: (x['days_ago'] is not None, -(x['days_ago'] or 9999))
    )
    top_suggestion = group_suggestions[0] if group_suggestions else None

    # Plans ordered
    all_plans = WorkoutPlan.query.filter_by(user_id=current_user.id)\
        .order_by(WorkoutPlan.sort_order, WorkoutPlan.created_at).all()

    return render_template('main/dashboard.html',
                           weekly_sessions=weekly_sessions,
                           monthly_sessions=monthly_sessions,
                           recent_sessions=recent_sessions,
                           group_suggestions=group_suggestions,
                           top_suggestion=top_suggestion,
                           all_groups=all_groups,
                           all_plans=all_plans,
                           today=today)
