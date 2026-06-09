from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sessions = db.relationship('WorkoutSession', backref='user', lazy=True, cascade='all, delete-orphan')
    plans = db.relationship('WorkoutPlan', backref='user', lazy=True, cascade='all, delete-orphan')


class MuscleGroup(db.Model):
    __tablename__ = 'muscle_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(50))
    exercises = db.relationship('Exercise', backref='muscle_group', lazy=True)

    def exercise_count(self):
        return len(self.exercises)


class Exercise(db.Model):
    __tablename__ = 'exercises'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)
    difficulty = db.Column(db.String(20), default='Intermediário')
    equipment = db.Column(db.String(100))
    muscle_group_id = db.Column(db.Integer, db.ForeignKey('muscle_groups.id'), nullable=False)


class WorkoutPlan(db.Model):
    __tablename__ = 'workout_plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sort_order = db.Column(db.Integer, default=0)
    muscle_groups = db.relationship('MuscleGroup', secondary='plan_muscle_groups', lazy=True)
    plan_exercises = db.relationship('PlanExercise', backref='plan', lazy=True, cascade='all, delete-orphan')


class PlanExercise(db.Model):
    __tablename__ = 'plan_exercises'
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('workout_plans.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)
    sets = db.Column(db.Integer, default=3)
    reps = db.Column(db.String(20), default='10-12')
    rest_seconds = db.Column(db.Integer, default=60)
    order = db.Column(db.Integer, default=0)
    exercise = db.relationship('Exercise')


# Junction table: muscle groups associated with a plan
plan_muscle_groups = db.Table(
    'plan_muscle_groups',
    db.Column('plan_id', db.Integer, db.ForeignKey('workout_plans.id'), primary_key=True),
    db.Column('muscle_group_id', db.Integer, db.ForeignKey('muscle_groups.id'), primary_key=True)
)

# Junction table: which muscle groups were trained in a session (explicit, user-selected)
session_muscle_groups = db.Table(
    'session_muscle_groups',
    db.Column('session_id', db.Integer, db.ForeignKey('workout_sessions.id'), primary_key=True),
    db.Column('muscle_group_id', db.Integer, db.ForeignKey('muscle_groups.id'), primary_key=True)
)


class WorkoutSession(db.Model):
    __tablename__ = 'workout_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('workout_plans.id'), nullable=True)
    # Custom name shown in history (overrides plan name)
    custom_name = db.Column(db.String(150), nullable=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    notes = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Explicit muscle groups selected by user
    muscle_groups = db.relationship('MuscleGroup', secondary=session_muscle_groups, lazy=True)
    session_exercises = db.relationship('SessionExercise', backref='session', lazy=True, cascade='all, delete-orphan')
    plan = db.relationship('WorkoutPlan')

    @property
    def display_name(self):
        if self.custom_name:
            return self.custom_name
        if self.plan:
            return self.plan.name
        return 'Treino Avulso'

    @property
    def effective_muscle_groups(self):
        """Explicit groups first; fall back to groups inferred from exercises."""
        if self.muscle_groups:
            return self.muscle_groups
        seen = {}
        for se in self.session_exercises:
            mg = se.exercise.muscle_group
            seen[mg.id] = mg
        return list(seen.values())


class SessionExercise(db.Model):
    __tablename__ = 'session_exercises'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('workout_sessions.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)
    sets_done = db.Column(db.Integer, default=0)
    reps_done = db.Column(db.String(20))
    weight_kg = db.Column(db.Float)
    notes = db.Column(db.Text)
    exercise = db.relationship('Exercise')


def seed_data():
    if MuscleGroup.query.count() > 0:
        return

    groups_data = [
        ('Abdominais', '🔥', [
            ('Abdominal Crunch', 'Exercício básico para reto abdominal.', 'Deite-se de costas, joelhos flexionados. Eleve o tronco contraindo o abdômen.', 'Iniciante', 'Sem equipamento'),
            ('Prancha', 'Fortalece todo o core.', 'Apoie os antebraços e pontas dos pés. Mantenha o corpo alinhado por 30-60 segundos.', 'Iniciante', 'Sem equipamento'),
            ('Levantamento de Pernas em Suspensão', 'Trabalha o reto abdominal inferior.', 'Suspenda-se numa barra. Eleve as pernas até a horizontal mantendo o core contraído.', 'Avançado', 'Barra'),
            ('Abdominal Lateral com Haltere', 'Foca nos oblíquos.', 'Em pé com haltere numa mão, incline o tronco lateralmente de forma controlada.', 'Intermediário', 'Haltere'),
            ('Flexões', 'Trabalha core, peito e tríceps.', 'Apoie mãos e pontas dos pés. Flexione os cotovelos descendo o peito ao chão.', 'Intermediário', 'Sem equipamento'),
            ('Elevação de Pernas', 'Abdômen inferior.', 'Deitado, eleve as pernas juntas até 90°, baixe sem tocar o chão.', 'Intermediário', 'Colchonete'),
            ('Mountain Climber', 'Cardio e core.', 'Posição de prancha, alterne joelhos em direção ao peito rapidamente.', 'Intermediário', 'Sem equipamento'),
            ('Roda Abdominal', 'Exercício avançado de core.', 'Ajoelhado, role a roda à frente mantendo o core contraído.', 'Avançado', 'Roda abdominal'),
        ]),
        ('Costas', '💪', [
            ('Puxada na Barra', 'Trabalha grande dorsal.', 'Suspenda-se na barra com pegada pronada. Puxe até o queixo ultrapassar a barra.', 'Avançado', 'Barra'),
            ('Remada Curvada', 'Costas médias e inferiores.', 'Incline o tronco ~45°, puxe a barra em direção ao abdômen.', 'Intermediário', 'Barra'),
            ('Remada Unilateral com Haltere', 'Isola cada lado das costas.', 'Apoie um joelho e mão no banco. Puxe o haltere até o quadril.', 'Iniciante', 'Haltere, banco'),
            ('Pulldown', 'Grande dorsal.', 'No cabo, puxe a barra até a altura do queixo mantendo o peito alto.', 'Iniciante', 'Cabo'),
            ('Levantamento Terra', 'Costas completas e posterior.', 'Barra no chão, quadril baixo, costas retas. Levante até ficar em pé.', 'Avançado', 'Barra'),
            ('Hiperextensão', 'Lombar.', 'No banco de hiperextensão, desça o tronco e retorne à posição neutra.', 'Iniciante', 'Banco romano'),
        ]),
        ('Bíceps', '💪', [
            ('Rosca Direta', 'Exercício clássico de bíceps.', 'Em pé, cotovelos fixos ao corpo. Curl com a barra até os ombros.', 'Iniciante', 'Barra ou halteres'),
            ('Rosca Concentrada', 'Isolamento do bíceps.', 'Sentado, cotovelo apoiado na coxa. Curl com haltere de forma controlada.', 'Iniciante', 'Haltere'),
            ('Rosca Martelo', 'Braquial e bíceps.', 'Curl com pegada neutra (polegar para cima).', 'Iniciante', 'Halteres'),
            ('Rosca 21', 'Alta intensidade para bíceps.', '7 repetições parciais inferiores, 7 superiores, 7 completas.', 'Intermediário', 'Barra ou halteres'),
            ('Rosca no Cabo', 'Tensão constante.', 'Posicionado na polia baixa, execute o curl mantendo o cotovelo fixo.', 'Iniciante', 'Cabo'),
        ]),
        ('Peito', '🫀', [
            ('Supino Reto', 'Exercício principal de peito.', 'Deitado no banco, desça a barra até o peito e empurre de volta.', 'Intermediário', 'Barra, banco'),
            ('Supino Inclinado', 'Parte superior do peito.', 'Banco inclinado ~30-45°. Mesma execução do supino reto.', 'Intermediário', 'Barra, banco'),
            ('Crucifixo', 'Isolamento do peito.', 'Deitado, abra os braços com halteres em semicírculo e retorne.', 'Iniciante', 'Halteres, banco'),
            ('Flexão de Braço', 'Peito e tríceps com peso corporal.', 'Apoio em mãos e pés, desça o peito até próximo do chão.', 'Iniciante', 'Sem equipamento'),
            ('Peck Deck', 'Isolamento do peitoral.', 'No aparelho, una os antebraços à frente do peito.', 'Iniciante', 'Aparelho'),
            ('Crossover', 'Definição do peito.', 'Nas polias altas, cruze os braços à frente do corpo.', 'Intermediário', 'Cabo'),
        ]),
        ('Pernas', '🦵', [
            ('Agachamento', 'Exercício rei do treino de pernas.', 'Pés na largura dos ombros, desça até a coxa ficar paralela ao chão.', 'Intermediário', 'Barra ou peso corporal'),
            ('Leg Press', 'Quadríceps e glúteos.', 'No aparelho, empurre a plataforma sem travar os joelhos.', 'Iniciante', 'Aparelho'),
            ('Avanço', 'Quadríceps e equilíbrio.', 'Dê um passo à frente e desça o joelho traseiro ao chão.', 'Iniciante', 'Sem equipamento ou halteres'),
            ('Mesa Flexora', 'Bíceps femoral.', 'No aparelho, flexione os joelhos trazendo os calcanhares ao glúteo.', 'Iniciante', 'Aparelho'),
            ('Extensão de Pernas', 'Quadríceps isolado.', 'No aparelho, estenda os joelhos até a horizontal.', 'Iniciante', 'Aparelho'),
            ('Stiff', 'Posterior de coxa e glúteos.', 'Com a barra, incline o tronco mantendo as costas retas.', 'Intermediário', 'Barra'),
        ]),
        ('Ombros', '🏋️', [
            ('Desenvolvimento com Barra', 'Deltoides completo.', 'Empurre a barra acima da cabeça a partir dos ombros.', 'Intermediário', 'Barra'),
            ('Elevação Lateral', 'Deltoide médio.', 'Eleve os halteres lateralmente até a altura dos ombros.', 'Iniciante', 'Halteres'),
            ('Elevação Frontal', 'Deltoide anterior.', 'Eleve o haltere à frente até a altura do ombro.', 'Iniciante', 'Haltere ou barra'),
            ('Desenvolvimento Arnold', 'Deltoides completo.', 'Inicie com palmas para você e gire ao empurrar acima da cabeça.', 'Intermediário', 'Halteres'),
            ('Encolhimento', 'Trapézio.', 'Eleve os ombros em direção às orelhas com halteres ou barra.', 'Iniciante', 'Halteres ou barra'),
        ]),
        ('Tríceps', '💪', [
            ('Tríceps Testa', 'Isolamento do tríceps.', 'Deitado, baixe a barra em direção à testa flexionando os cotovelos.', 'Intermediário', 'Barra, banco'),
            ('Tríceps Pulley', 'Tríceps no cabo.', 'No cabo alto, empurre a barra para baixo mantendo os cotovelos fixos.', 'Iniciante', 'Cabo'),
            ('Mergulho (Dip)', 'Peito e tríceps.', 'Nas barras paralelas, desça e suba o corpo pelo movimento dos braços.', 'Avançado', 'Barras paralelas'),
            ('Kickback', 'Isolamento do tríceps.', 'Inclinado, estenda o braço para trás mantendo o cotovelo fixo.', 'Iniciante', 'Haltere'),
        ]),
        ('Panturrilha', '🦵', [
            ('Elevação de Panturrilha em Pé', 'Gastrocnêmio.', 'Em pé, suba na ponta dos pés e desça controladamente.', 'Iniciante', 'Sem equipamento ou halteres'),
            ('Elevação de Panturrilha Sentado', 'Sóleo.', 'Sentado com peso nas coxas, eleve os calcanhares.', 'Iniciante', 'Aparelho ou halteres'),
            ('Leg Press Panturrilha', 'Gastrocnêmio no aparelho.', 'No leg press, empurre com as pontas dos pés apenas.', 'Iniciante', 'Aparelho'),
        ]),
    ]

    for group_name, icon, exercises in groups_data:
        group = MuscleGroup(name=group_name, icon=icon)
        db.session.add(group)
        db.session.flush()
        for ex_data in exercises:
            ex = Exercise(
                name=ex_data[0], description=ex_data[1], instructions=ex_data[2],
                difficulty=ex_data[3], equipment=ex_data[4], muscle_group_id=group.id
            )
            db.session.add(ex)

    db.session.commit()
    print('✅ Seed data inserted successfully!')
