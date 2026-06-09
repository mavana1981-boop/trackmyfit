from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import WorkoutPlan, PlanExercise, Exercise, MuscleGroup
import os, base64, json, io
import requests as http_requests

workouts_bp = Blueprint('workouts', __name__)


# ── Exercise helpers ──────────────────────────────────────────────────────────

def _find_or_create_exercise(name, muscle_group_hint=None):
    name = name.strip()
    name_lower = name.lower()
    ex_map = {e.name.lower(): e for e in Exercise.query.all()}
    if name_lower in ex_map:
        return ex_map[name_lower]
    for key, ex in ex_map.items():
        if name_lower in key or key in name_lower:
            return ex
    group = None
    if muscle_group_hint:
        group = MuscleGroup.query.filter(MuscleGroup.name.ilike(f'%{muscle_group_hint}%')).first()
    if not group:
        group = MuscleGroup.query.first()
    new_ex = Exercise(
        name=name,
        description='Exercício importado via PDF.',
        instructions='Consulte o PDF original para instruções detalhadas.',
        difficulty='Intermediário',
        equipment='Consulte o plano',
        muscle_group_id=group.id
    )
    db.session.add(new_ex)
    db.session.flush()
    return new_ex


def _save_plans(planos, user_id):
    created = []
    for p in planos:
        plan = WorkoutPlan(
            name=p.get('nome', 'Plano Importado'),
            description=p.get('descricao', ''),
            user_id=user_id
        )
        db.session.add(plan)
        db.session.flush()
        for i, ex_data in enumerate(p.get('exercicios', [])):
            ex = _find_or_create_exercise(ex_data.get('nome', 'Exercício'), ex_data.get('grupo_muscular'))
            try: sets = int(ex_data.get('series', 3))
            except: sets = 3
            try: rest = int(ex_data.get('descanso_segundos', 60))
            except: rest = 60
            pe = PlanExercise(
                plan_id=plan.id, exercise_id=ex.id,
                sets=sets, reps=str(ex_data.get('repeticoes', '10-12')),
                rest_seconds=rest, order=i
            )
            db.session.add(pe)
        created.append(plan.name)
    db.session.commit()
    return created


# ── PDF text extraction (for Groq fallback) ───────────────────────────────────

def _extract_pdf_text(pdf_bytes):
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        return text.strip()
    except Exception as e:
        raise ValueError(f'Erro ao extrair texto do PDF: {e}')


# ── Shared prompt ─────────────────────────────────────────────────────────────

PROMPT = """Analise este conteúdo de treino e extraia todos os planos encontrados.

Retorne SOMENTE um JSON válido, sem markdown, sem texto extra, no formato:
{
  "planos": [
    {
      "nome": "Treino A",
      "descricao": "Descrição opcional",
      "exercicios": [
        {
          "nome": "Nome do exercício",
          "series": 3,
          "repeticoes": "10-12",
          "descanso_segundos": 60,
          "grupo_muscular": "Peito"
        }
      ]
    }
  ]
}

Regras:
- Extraia TODOS os treinos (A, B, C ou qualquer nomenclatura usada)
- Se não encontrar séries/repetições, use valores padrão razoáveis
- grupo_muscular deve ser um de: Abdominais, Costas, Bíceps, Peito, Pernas, Ombros, Tríceps, Panturrilha
- Retorne apenas o JSON, sem explicações"""


def _parse_json_response(text):
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        text = text.rsplit('```', 1)[0]
    parsed = json.loads(text.strip())
    return parsed.get('planos', [])


# ── Gemini (primary) ──────────────────────────────────────────────────────────

def _call_gemini(pdf_bytes):
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('GEMINI_API_KEY não configurada.')

    pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "application/pdf", "data": pdf_b64}},
                {"text": PROMPT}
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192}
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    resp = http_requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    text = resp.json()['candidates'][0]['content']['parts'][0]['text']
    return _parse_json_response(text)


# ── Groq (fallback) ───────────────────────────────────────────────────────────

def _call_groq(pdf_bytes):
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        raise ValueError('GROQ_API_KEY não configurada.')

    pdf_text = _extract_pdf_text(pdf_bytes)
    if not pdf_text:
        raise ValueError('Não foi possível extrair texto do PDF para o Groq.')

    from groq import Groq
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[
            {"role": "system", "content": "Você é um especialista em análise de planilhas de treino. Responda APENAS com JSON válido, sem markdown."},
            {"role": "user", "content": f"{PROMPT}\n\nConteúdo do PDF:\n{pdf_text[:12000]}"}
        ],
        temperature=0.1,
        max_tokens=4096
    )
    text = completion.choices[0].message.content
    return _parse_json_response(text)


# ── Orchestrator with fallback ────────────────────────────────────────────────

def _analyze_pdf(pdf_bytes):
    """Try Gemini first, fall back to Groq on any error."""
    errors = []

    # 1. Try Gemini
    try:
        planos = _call_gemini(pdf_bytes)
        if planos:
            return planos, 'Gemini'
        errors.append('Gemini: retornou lista vazia')
    except ValueError as e:
        errors.append(f'Gemini: {e}')
    except http_requests.exceptions.HTTPError as e:
        errors.append(f'Gemini HTTP {e.response.status_code}')
    except Exception as e:
        errors.append(f'Gemini: {e}')

    # 2. Fall back to Groq
    try:
        planos = _call_groq(pdf_bytes)
        if planos:
            return planos, 'Groq'
        errors.append('Groq: retornou lista vazia')
    except ValueError as e:
        errors.append(f'Groq: {e}')
    except Exception as e:
        errors.append(f'Groq: {e}')

    raise RuntimeError('Ambas as IAs falharam: ' + ' | '.join(errors))


# ── Routes ────────────────────────────────────────────────────────────────────

@workouts_bp.route('/plans')
@login_required
def index():
    plans = WorkoutPlan.query.filter_by(user_id=current_user.id)\
        .order_by(WorkoutPlan.created_at.desc()).all()
    return render_template('workouts/index.html', plans=plans)


@workouts_bp.route('/plans/import-pdf', methods=['GET', 'POST'])
@login_required
def import_pdf():
    if request.method == 'POST':
        if 'pdf' not in request.files or request.files['pdf'].filename == '':
            flash('Selecione um arquivo PDF.', 'error')
            return redirect(url_for('workouts.import_pdf'))
        pdf_file = request.files['pdf']
        if not pdf_file.filename.lower().endswith('.pdf'):
            flash('O arquivo deve ser um PDF.', 'error')
            return redirect(url_for('workouts.import_pdf'))
        pdf_bytes = pdf_file.read()
        if len(pdf_bytes) > 20 * 1024 * 1024:
            flash('PDF muito grande. Máximo 20MB.', 'error')
            return redirect(url_for('workouts.import_pdf'))
        try:
            planos, provider = _analyze_pdf(pdf_bytes)
            nomes = _save_plans(planos, current_user.id)
            flash(f'✅ {len(nomes)} plano(s) importado(s) via {provider}: {", ".join(nomes)}', 'success')
            return redirect(url_for('workouts.index'))
        except json.JSONDecodeError:
            flash('A IA retornou um formato inesperado. Tente novamente.', 'error')
        except Exception as e:
            flash(f'Erro ao importar: {str(e)}', 'error')
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
        if not name:
            flash('Nome do plano é obrigatório.', 'error')
            return render_template('workouts/new.html', groups=groups)
        plan = WorkoutPlan(name=name, description=description, user_id=current_user.id)
        db.session.add(plan)
        db.session.flush()
        for i, ex_id in enumerate(exercise_ids):
            pe = PlanExercise(
                plan_id=plan.id, exercise_id=int(ex_id),
                sets=int(sets_list[i]) if i < len(sets_list) else 3,
                reps=reps_list[i] if i < len(reps_list) else '10-12',
                rest_seconds=int(rest_list[i]) if i < len(rest_list) else 60,
                order=i
            )
            db.session.add(pe)
        db.session.commit()
        flash(f'Plano "{name}" criado com sucesso!', 'success')
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
