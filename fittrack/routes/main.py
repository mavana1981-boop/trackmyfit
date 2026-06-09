from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import WorkoutSession, WorkoutPlan, MuscleGroup
from datetime import datetime, timedelta
from app import db

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())

    weekly_sessions = WorkoutSession.query.filter(
        WorkoutSession.user_id == current_user.id,
        WorkoutSession.date >= week_start
    ).count()

    total_sessions = WorkoutSession.query.filter_by(user_id=current_user.id).count()

    # Last 5 sessions enriched with muscle groups
    recent_sessions_raw = (
        WorkoutSession.query
        .filter_by(user_id=current_user.id)
        .order_by(WorkoutSession.date.desc())
        .limit(5).all()
    )
    recent_sessions = [
        {'session': s, 'groups': s.effective_muscle_groups}
        for s in recent_sessions_raw
    ]

    # Last 30 days for streak
    thirty_days_ago = today - timedelta(days=30)
    sessions_last_30 = WorkoutSession.query.filter(
        WorkoutSession.user_id == current_user.id,
        WorkoutSession.date >= thirty_days_ago
    ).all()

    # ── Muscle group suggestion ───────────────────────────────────────────────
    all_groups = MuscleGroup.query.all()
    all_sessions = (
        WorkoutSession.query
        .filter_by(user_id=current_user.id)
        .order_by(WorkoutSession.date.desc())
        .all()
    )

    # Last date each group was trained (explicit OR inferred from exercises)
    group_last_trained = {}
    for s in all_sessions:
        for mg in s.effective_muscle_groups:
            if mg.id not in group_last_trained:
                group_last_trained[mg.id] = s.date

    group_suggestions = []
    for g in all_groups:
        last = group_last_trained.get(g.id)
        days_ago = (today - last).days if last else None
        group_suggestions.append({
            'group': g,
            'last_date': last,
            'days_ago': days_ago
        })

    # Sort: never trained first, then most days ago
    group_suggestions.sort(
        key=lambda x: (x['days_ago'] is not None, -(x['days_ago'] or 9999))
    )
    top_suggestion = group_suggestions[0] if group_suggestions else None

    return render_template('main/dashboard.html',
                           weekly_sessions=weekly_sessions,
                           total_sessions=total_sessions,
                           recent_sessions=recent_sessions,
                           sessions_last_30=sessions_last_30,
                           group_suggestions=group_suggestions,
                           top_suggestion=top_suggestion,
                           today=today)
