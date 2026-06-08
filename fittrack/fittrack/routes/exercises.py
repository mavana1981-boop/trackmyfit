from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from models import MuscleGroup, Exercise

exercises_bp = Blueprint('exercises', __name__)


@exercises_bp.route('/exercises')
@login_required
def index():
    groups = MuscleGroup.query.all()
    return render_template('exercises/index.html', groups=groups)


@exercises_bp.route('/exercises/group/<int:group_id>')
@login_required
def group(group_id):
    muscle_group = MuscleGroup.query.get_or_404(group_id)
    exercises = Exercise.query.filter_by(muscle_group_id=group_id).all()
    return render_template('exercises/group.html', group=muscle_group, exercises=exercises)


@exercises_bp.route('/exercises/<int:exercise_id>')
@login_required
def detail(exercise_id):
    exercise = Exercise.query.get_or_404(exercise_id)
    return render_template('exercises/detail.html', exercise=exercise)


@exercises_bp.route('/api/exercises')
@login_required
def api_list():
    exercises = Exercise.query.all()
    return jsonify([{
        'id': e.id,
        'name': e.name,
        'muscle_group': e.muscle_group.name,
        'difficulty': e.difficulty,
        'equipment': e.equipment
    } for e in exercises])
