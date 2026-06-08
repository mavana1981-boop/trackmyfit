# 🏋️ FitTrack

App de treino com Flask + PostgreSQL para Railway.

## Funcionalidades

- **Login/Cadastro** — autenticação segura com bcrypt
- **Exercícios** — 8 grupos musculares com 50+ exercícios pré-cadastrados
- **Planos** — monte treinos personalizados (A/B/C etc.)
- **Registro** — registre cada sessão com séries, reps e carga
- **Histórico** — lista de treinos por data (igual ao app)
- **Dashboard** — estatísticas semanais e frequência

## Deploy no Railway

### 1. PostgreSQL
1. No Railway, crie um novo projeto
2. Adicione um plugin **PostgreSQL**
3. Copie a variável `DATABASE_URL`

### 2. App Flask
1. Faça upload do código (ou conecte ao GitHub)
2. Configure as variáveis de ambiente:

```
DATABASE_URL=postgresql://...   (gerado automaticamente pelo Railway)
SECRET_KEY=uma-chave-secreta-longa-e-aleatoria
```

### 3. Deploy
O Railway detecta automaticamente o `Procfile` e sobe a aplicação.  
O banco é criado e populado automaticamente no primeiro boot.

## Desenvolvimento local

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis
export DATABASE_URL="postgresql://localhost/fittrack"
export SECRET_KEY="dev-secret"

# Rodar
python app.py
```

## Estrutura

```
fittrack/
├── app.py              # Factory + configuração Flask
├── models.py           # SQLAlchemy models + seed data
├── routes/
│   ├── auth.py         # Login, cadastro, logout
│   ├── main.py         # Dashboard
│   ├── exercises.py    # Grupos musculares e exercícios
│   ├── workouts.py     # Planos de treino
│   └── history.py      # Registro e histórico
├── templates/
│   ├── base.html       # Layout base com nav inferior
│   ├── auth/           # Login e cadastro
│   ├── main/           # Dashboard
│   ├── exercises/      # Exercícios por grupo
│   ├── workouts/       # Planos
│   └── history/        # Registro e histórico
├── requirements.txt
├── Procfile
└── railway.toml
```
