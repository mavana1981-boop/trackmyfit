from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import WorkoutPlan, PlanExercise, Exercise, MuscleGroup
import os, base64, json, io
import requests as http_requests

workouts_bp = Blueprint('workouts', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_plan_groups(plan, group_ids):
    plan.muscle_groups = []
    for gid in group_ids:
        mg = MuscleGroup.query.get(gid)
        if mg:
            plan.muscle_groups.append(mg)


def _find_or_create_exercise(name, muscle_group_hint=None):
    name = name.strip()
    ex_map = {e.name.lower(): e for e in Exercise.query.all()}
    if name.lower() in ex_map:
        return ex_map[name.lower()]
    for key, ex in ex_map.items():
        if name.lower() in key or key in name.lower():
            return ex
    group = None
    if muscle_group_hint:
        group = MuscleGroup.query.filter(MuscleGroup.name.ilike(f'%{muscle_group_hint}%')).first()
    if not group:
        group = MuscleGroup.query.first()
    new_ex = Exercise(name=name, description='Importado via PDF.', instructions='Consulte o PDF.',
                      difficulty='Intermediário', equipment='Consulte o plano', muscle_group_id=group.id)
    db.session.add(new_ex)
    db.session.flush()
    return new_ex


def _save_plans(planos, user_id):
    # Get current max order for this user
    max_order = db.session.query(db.func.max(WorkoutPlan.sort_order))\
        .filter_by(user_id=user_id).scalar() or 0
    created = []
    for i, p in enumerate(planos):
        plan = WorkoutPlan(name=p.get('nome', 'Plano Importado'),
                           description=p.get('descricao', ''),
                           user_id=user_id, sort_order=max_order + i + 1)
        db.session.add(plan)
        db.session.flush()
        for j, ex_data in enumerate(p.get('exercicios', [])):
            ex = _find_or_create_exercise(ex_data.get('nome', 'Exercício'), ex_data.get('grupo_muscular'))
            try: sets = int(ex_data.get('series', 3))
            except: sets = 3
            try: rest = int(ex_data.get('descanso_segundos', 60))
            except: rest = 60
            db.session.add(PlanExercise(plan_id=plan.id, exercise_id=ex.id,
                sets=sets, reps=str(ex_data.get('repeticoes', '10-12')),
                rest_seconds=rest, order=j))
        created.append(plan.name)
    db.session.commit()
    return created


# ── AI providers ──────────────────────────────────────────────────────────────

PROMPT = """Analise este conteúdo de treino e extraia todos os planos encontrados.
Retorne SOMENTE um JSON válido, sem markdown, no formato:
{"planos":[{"nome":"Treino A","descricao":"","exercicios":[{"nome":"Nome","series":3,"repeticoes":"10-12","descanso_segundos":60,"grupo_muscular":"Peito"}]}]}
Regras: extraia TODOS os treinos; grupo_muscular deve ser um de: Abdominais, Costas, Bíceps, Peito, Pernas, Ombros, Tríceps, Panturrilha; retorne apenas o JSON."""


def _parse_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0]
    return json.loads(text.strip()).get('planos', [])


def _extract_pdf_text(pdf_bytes):
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return '\n'.join(page.extract_text() or '' for page in reader.pages).strip()


def _call_gemini(pdf_bytes):
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key: raise ValueError('GEMINI_API_KEY não configurada.')
    payload = {"contents": [{"parts": [
        {"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(pdf_bytes).decode()}},
        {"text": PROMPT}
    ]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192}}
    r = http_requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}", json=payload, timeout=60)
    r.raise_for_status()
    return _parse_json(r.json()['candidates'][0]['content']['parts'][0]['text'])


def _call_groq(pdf_bytes):
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key: raise ValueError('GROQ_API_KEY não configurada.')
    from groq import Groq
    text = _extract_pdf_text(pdf_bytes)
    if not text: raise ValueError('Não foi possível extrair texto do PDF.')
    c = Groq(api_key=api_key).chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[{"role":"system","content":"Responda APENAS com JSON válido."},
                  {"role":"user","content":f"{PROMPT}\n\nPDF:\n{text[:12000]}"}],
        temperature=0.1, max_tokens=4096)
    return _parse_json(c.choices[0].message.content)


def _call_cloudflare(pdf_bytes):
    account_id = os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')
    api_token = os.environ.get('CLOUDFLARE_API_TOKEN', '')
    if not account_id or not api_token: raise ValueError('Cloudflare não configurado.')
    text = _extract_pdf_text(pdf_bytes)
    if not text: raise ValueError('Não foi possível extrair texto do PDF.')
    r = http_requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        headers={"Authorization": f"Bearer {api_token}"},
        json={"messages": [{"role":"system","content":"Responda APENAS com JSON válido."},
                            {"role":"user","content":f"{PROMPT}\n\nPDF:\n{text[:12000]}"}],
              "max_tokens": 4096, "temperature": 0.1},
        timeout=90)
    r.raise_for_status()
    data = r.json()
    if not data.get('success'): raise ValueError(f'Cloudflare: {data.get("errors")}')
    return _parse_json(data['result']['response'])


def _analyze_pdf(pdf_bytes):
    errors = []
    for name, fn in [('Gemini', _call_gemini), ('Groq', _call_groq), ('Cloudflare', _call_cloudflare)]:
        try:
            planos = fn(pdf_bytes)
            if planos: return planos, name
            errors.append(f'{name}: lista vazia')
        except http_requests.exceptions.HTTPError as e:
            errors.append(f'{name}: HTTP {e.response.status_code}')
        except Exception as e:
            errors.append(f'{name}: {e}')
    raise RuntimeError('Todos os provedores falharam:\n' + '\n'.join(f'  • {e}' for e in errors))


# ── Routes ────────────────────────────────────────────────────────────────────

@workouts_bp.route('/plans')
@login_required
def index():
    plans = WorkoutPlan.query.filter_by(user_id=current_user.id)\
        .order_by(WorkoutPlan.sort_order, WorkoutPlan.created_at).all()
    groups = MuscleGroup.query.all()
    return render_template('workouts/index.html', plans=plans, groups=groups)


@workouts_bp.route('/plans/<int:plan_id>/edit', methods=['POST'])
@login_required
def edit(plan_id):
    plan = WorkoutPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    name = request.form.get('name', '').strip()
    group_ids = [int(g) for g in request.form.getlist('muscle_group_ids') if g.isdigit()]
    if name:
        plan.name = name
    _set_plan_groups(plan, group_ids)
    db.session.commit()
    flash('Plano atualizado.', 'success')
    return redirect(url_for('workouts.index'))


@workouts_bp.route('/plans/reorder', methods=['POST'])
@login_required
def reorder():
    """Receive ordered list of plan IDs and update sort_order."""
    order = request.json.get('order', [])
    for i, plan_id in enumerate(order):
        plan = WorkoutPlan.query.filter_by(id=int(plan_id), user_id=current_user.id).first()
        if plan:
            plan.sort_order = i
    db.session.commit()
    return jsonify({'ok': True})


@workouts_bp.route('/plans/import-pdf', methods=['GET', 'POST'])
@login_required
def import_pdf():
    if request.method == 'POST':
        if 'pdf' not in request.files or not request.files['pdf'].filename:
            flash('Selecione um PDF.', 'error')
            return redirect(url_for('workouts.import_pdf'))
        pdf_file = request.files['pdf']
        if not pdf_file.filename.lower().endswith('.pdf'):
            flash('O arquivo deve ser PDF.', 'error')
            return redirect(url_for('workouts.import_pdf'))
        pdf_bytes = pdf_file.read()
        if len(pdf_bytes) > 20 * 1024 * 1024:
            flash('PDF muito grande. Máx 20MB.', 'error')
            return redirect(url_for('workouts.import_pdf'))
        try:
            planos, provider = _analyze_pdf(pdf_bytes)
            nomes = _save_plans(planos, current_user.id)
            flash(f'✅ {len(nomes)} plano(s) via {provider}: {", ".join(nomes)}', 'success')
            return redirect(url_for('workouts.index'))
        except json.JSONDecodeError:
            flash('Formato inesperado. Tente novamente.', 'error')
        except Exception as e:
            flash(str(e), 'error')
        return redirect(url_for('workouts.import_pdf'))
    return render_template('workouts/import_pdf.html')


@workouts_bp.route('/plans/new', methods=['GET', 'POST'])
@login_required
def new():
    groups = MuscleGroup.query.all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        exercise_ids = request.form.getlist('exercise_ids')
        sets_list = request.form.getlist('sets')
        reps_list = request.form.getlist('reps')
        rest_list = request.form.getlist('rest')
        group_ids = [int(g) for g in request.form.getlist('muscle_group_ids') if g.isdigit()]
        if not name:
            flash('Nome obrigatório.', 'error')
            return render_template('workouts/new.html', groups=groups)
        max_order = db.session.query(db.func.max(WorkoutPlan.sort_order))\
            .filter_by(user_id=current_user.id).scalar() or 0
        plan = WorkoutPlan(name=name, description=description,
                           user_id=current_user.id, sort_order=max_order + 1)
        db.session.add(plan)
        db.session.flush()
        _set_plan_groups(plan, group_ids)
        for i, ex_id in enumerate(exercise_ids):
            db.session.add(PlanExercise(
                plan_id=plan.id, exercise_id=int(ex_id),
                sets=int(sets_list[i]) if i < len(sets_list) else 3,
                reps=reps_list[i] if i < len(reps_list) else '10-12',
                rest_seconds=int(rest_list[i]) if i < len(rest_list) else 60,
                order=i))
        db.session.commit()
        flash(f'Plano "{name}" criado!', 'success')
        return redirect(url_for('workouts.index'))
    return render_template('workouts/new.html', groups=groups)


@workouts_bp.route('/plans/<int:plan_id>')
@login_required
def detail(plan_id):
    plan = WorkoutPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    return render_template('workouts/detail.html', plan=plan)


@workouts_bp.route('/plans/<int:plan_id>/delete', methods=['POST'])
@login_required
def delete(plan_id):
    plan = WorkoutPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    db.session.delete(plan)
    db.session.commit()
    flash('Plano removido.', 'success')
    return redirect(url_for('workouts.index'))


@workouts_bp.route('/api/exercises/by-group/<int:group_id>')
@login_required
def exercises_by_group(group_id):
    exercises = Exercise.query.filter_by(muscle_group_id=group_id).all()
    return jsonify([{'id': e.id, 'name': e.name, 'difficulty': e.difficulty} for e in exercises])
