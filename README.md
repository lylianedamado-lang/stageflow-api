# StageFlow API

## Institut Supérieur d'Informatique

API interne de gestion sécurisée des stages data
Master 1 DSIA, Conception d'API REST.

Suivi des offres de stage, des candidatures, des validations pédagogiques et des
habilitations par rôle.

## Stack technique

| Composant | Choix |
|---|---|
| Framework | FastAPI |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Base de données | PostgreSQL (production), SQLite (tests) |
| Authentification | OAuth2 password flow, JWT (PyJWT), bcrypt |
| Tests | pytest, pytest-cov |
| Conteneurisation | Docker, docker-compose |
| CI | GitHub Actions, Codecov, GHCR |

## Architecture

```
app/
  main.py                 point d'entrée FastAPI, middlewares, routers
  api/routes/             couche HTTP : reçoit, délègue, renvoie
  core/                   configuration, sécurité JWT, permissions, erreurs
  db/                     moteur SQLAlchemy et session par requête
  models/                 tables SQLAlchemy
  schemas/                DTO Pydantic d'entrée et de sortie
  repositories/           seul accès SQL + invariants métier
  middlewares/            request_id, security_headers
  utils/                  pagination, hachage, temps
tests/
  unit/                   sécurité, schémas, repositories
  integration/            authentification, permissions, workflow complet
alembic/                  migrations versionnées
```

Règle structurante : **aucune route n'appelle SQLAlchemy directement**.
Toute lecture ou écriture du domaine passe par un repository.

## Rôles et habilitations

| Rôle | Droits |
|---|---|
| `student` | Consulter les offres publiées, déposer une candidature, retirer sa candidature tant qu'elle n'est pas acceptée |
| `company` | Créer des offres en brouillon, les soumettre, consulter les candidatures de ses propres offres |
| `program_manager` | Publier ou refuser une offre, accepter ou refuser une candidature, consulter les statistiques |
| `admin` | Gérer les comptes, forcer un changement de rôle (trace dans les logs applicatifs) |

L'inscription publique n'autorise que `student` et `company`.
Les rôles à privilèges sont attribués uniquement via `PATCH /users/{id}/role`.

## Invariants métier

- Une offre ne peut être soumise que si `title`, `mission` et `skills` sont renseignés.
- Transitions d'une offre : `draft -> submitted -> published | rejected`.
- Transitions d'une candidature : `pending -> accepted | rejected | withdrawn`.
- Un étudiant ne peut avoir qu'une candidature active par offre (contrainte
  d'unicité en base + vérification applicative).
- Une candidature acceptée ne peut plus être retirée par l'étudiant.
- Une entreprise ne peut jamais consulter les candidatures d'une autre entreprise.

## Codes HTTP

| Code | Signification |
|---|---|
| 400 | Règle métier non respectée |
| 401 | Non authentifié : jeton absent, invalide ou expiré |
| 403 | Authentifié mais non habilité |
| 404 | Ressource absente **ou non visible** pour l'appelant |
| 422 | Payload invalide (validation Pydantic) |

Le 404 sur une ressource existante mais non visible est délibéré : répondre 403
confirmerait son existence.

## Variables d'environnement

Copier `.env.example` vers `.env` et adapter les valeurs.

| Variable | Description | Défaut |
|---|---|---|
| `APP_NAME` | Nom affiché dans OpenAPI | `StageFlow API` |
| `ENVIRONMENT` | `development`, `test` ou `production` | `development` |
| `DEBUG` | Logs verbeux | `false` |
| `DATABASE_URL` | URL SQLAlchemy | `sqlite:///./stageflow.db` |
| `JWT_SECRET_KEY` | Clé de signature — **obligatoire, sans défaut** | — |
| `JWT_ALGORITHM` | Algorithme de signature | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Durée de validité du jeton | `60` |

Générer une clé :

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`.env` n'est jamais commité.

## Installation locale

```bash
python3.11 -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # puis renseigner JWT_SECRET_KEY
alembic upgrade head
uvicorn app.main:app --reload
```

Documentation interactive : http://127.0.0.1:8000/docs

### Jeu de données de démonstration

Les rôles `admin` et `program_manager` ne peuvent pas être obtenus par
inscription publique (protection contre le *mass assignment*). Un script
d'amorçage crée les comptes à privilèges ainsi qu'un jeu de données couvrant
les différents statuts du workflow :

```bash
python scripts_seed.py
```

| Compte | Rôle |
|---|---|
| `admin@isi.sn` | admin |
| `resp@isi.sn` | program_manager |
| `contact@teranga-analytics.sn` | company |
| `rh@baobab-data.sn` | company |
| `eleve@isi.sn` | student |
| `eleve2@isi.sn` | student |

Le script crée également cinq offres — trois publiées, une soumise en attente
d'arbitrage, une en brouillon incomplet — ainsi que trois candidatures en
attente. Les offres sont amenées à leur statut en passant par `submit()` et
`review()`, donc les invariants métier sont respectés y compris pour les
données de démonstration.

Mot de passe commun : `Passw0rd123!`. Le script est idempotent et refuse de
s'exécuter si `ENVIRONMENT=production`.

Avec Docker (la base PostgreSQL du conteneur est distincte de la base locale) :

```bash
docker compose exec api python scripts_seed.py
```

## Lancement avec Docker

```bash
docker compose up -d --build
```

Lance PostgreSQL, applique les migrations, puis démarre l'API sur
http://localhost:8000. La base est exposée sur le port hôte 5433.

```bash
docker compose logs -f api
docker compose down
```

L'image de production tourne sous un utilisateur non privilégié (`appuser`) et
expose une sonde `/health` utilisée par le `HEALTHCHECK` Docker.

## Tests

```bash
pytest                                              # tous les tests
pytest tests/unit -v                                # unitaires
pytest tests/integration -v                         # intégration
pytest --cov=app --cov-report=term-missing          # avec couverture
```

Les tests utilisent une base SQLite en mémoire, recréée pour chaque test via
`dependency_overrides`. Aucune configuration préalable n'est requise.

Couverture actuelle : environ 94 %.

## Endpoints

### Authentification

| Méthode | Chemin | Accès |
|---|---|---|
| POST | `/auth/register` | public |
| POST | `/auth/login` | public (formulaire OAuth2) |
| POST | `/auth/login/json` | public (JSON) |

### Utilisateurs

| Méthode | Chemin | Accès |
|---|---|---|
| GET | `/users/me` | authentifié |
| GET | `/users` | admin |
| PATCH | `/users/{id}/role` | admin |

### Offres

| Méthode | Chemin | Accès |
|---|---|---|
| POST | `/offers` | company |
| GET | `/offers` | authentifié |
| GET | `/offers/{id}` | authentifié (visibilité selon rôle) |
| PATCH | `/offers/{id}` | company propriétaire |
| PATCH | `/offers/{id}/submit` | company propriétaire |
| PATCH | `/offers/{id}/review` | program_manager |
| GET | `/offers/stats` | program_manager, admin |

### Candidatures

| Méthode | Chemin | Accès |
|---|---|---|
| POST | `/offers/{id}/applications` | student |
| GET | `/offers/{id}/applications` | company propriétaire, staff |
| GET | `/applications/me` | student |
| PATCH | `/applications/{id}/decision` | program_manager |
| DELETE | `/applications/{id}` | student propriétaire |

### Supervision

| Méthode | Chemin | Accès |
|---|---|---|
| GET | `/health` | public |

Toutes les listes acceptent `?limit=` (1-100) et `?offset=`.

## Intégration continue

`.github/workflows/ci.yml` s'exécute à chaque push et pull request sur `main` :

1. Installation des dépendances (Python 3.11)
2. `pytest --cov=app --cov-report=xml`
3. Envoi de la couverture à Codecov
4. Construction de l'image Docker et publication sur GHCR

Le secret `CODECOV_TOKEN` est déclaré dans
*Settings > Secrets and variables > Actions*.

## Sécurité

- Mots de passe hachés avec bcrypt (jamais stockés en clair, jamais renvoyés).
- JWT signés HS256 avec expiration ; le jeton est signé, non chiffré — il ne
  contient aucune donnée sensible.
- Autorisation centralisée dans `app/core/permissions.py` via des dépendances
  FastAPI ; aucune logique RBAC dispersée dans les routes.
- Message d'erreur identique pour un email inconnu et un mot de passe erroné,
  afin d'empêcher l'énumération de comptes.
- Middleware `security_headers` : `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `X-Permitted-Cross-Domain-Policies`.
- Middleware `request_id` : identifiant unique par requête, journalisé et
  renvoyé dans l'en-tête `X-Request-ID`.

## Limites connues et pistes d'amélioration

- Les statistiques sont calculées à la volée à chaque appel. Sur un volume
  important, il faudrait un cache ou une table d'agrégats.
- Pas de rafraîchissement de jeton : à expiration, l'utilisateur doit se
  reconnecter.
- La recherche sur les offres repose sur un simple `ILIKE`, sans index
  full-text ni gestion des accents.
- Les logs sont écrits sur la sortie standard. En production, il faudrait un
  format structuré et une collecte centralisée.
- `GET /offers` exige un jeton. Le sujet ne tranche pas sur ce point ; le
  choix retenu est de protéger la route, s'agissant d'une API interne.

## Auteur

Lyliane Fat-nelle G. DAMADO
