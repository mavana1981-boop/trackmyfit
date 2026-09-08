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
    # Track last trained date AND plan name per group (only from explicit tags)
    group_last_trained = {}   # group_id -> (date, session)
    for s in all_sessions:
        for mg in s.effective_muscle_groups:  # only explicit tags
            if mg.id not in group_last_trained:
                group_last_trained[mg.id] = s

    group_suggestions = []
    for g in all_groups:
        last_session = group_last_trained.get(g.id)
        last_date = last_session.date if last_session else None
        days_ago = (today - last_date).days if last_date else None
        plan_name = last_session.display_name if last_session else None
        group_suggestions.append({
            'group': g,
            'last_date': last_date,
            'days_ago': days_ago,
            'last_plan': plan_name
        })
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

@main_bp.route('/dashboard/rebuild-groups', methods=['POST'])
@login_required
def rebuild_groups():
    """Rebuild muscle group tags for all sessions based on exercises done."""
    from models import WorkoutSession, SessionExercise, MuscleGroup
    sessions = WorkoutSession.query.filter_by(user_id=current_user.id).all()
    updated = 0
    for s in sessions:
        if not s.muscle_groups:  # only sessions without explicit tags
            seen = {}
            for se in s.session_exercises:
                mg = se.exercise.muscle_group
                seen[mg.id] = mg
            if seen:
                s.muscle_groups = list(seen.values())
                updated += 1
    db.session.commit()
    from flask import jsonify
    return jsonify({'ok': True, 'updated': updated})
