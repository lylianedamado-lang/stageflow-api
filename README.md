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
| Base de donnees | PostgreSQL (production), SQLite (tests) |
| Authentification | OAuth2 password flow, JWT (PyJWT), bcrypt |
| Tests | pytest, pytest-cov |
| Conteneurisation | Docker, docker-compose |
| CI | GitHub Actions, Codecov, GHCR |

## Architecture
Regle structurante : **aucune route n'appelle SQLAlchemy directement**.
Toute lecture ou écriture du domaine passe par un repository.

## Rôles et habilitations

| Role | Droits |
|---|---|
| `student` | Consulter les offres publiées, deposer une candidature, retirer sa candidature tant qu'elle n'est pas acceptée |
| `company` | Créer des offres en brouillon, les soumettre, consulter les candidatures de ses propres offres |
| `program_manager` | Publier ou refuser une offre, accepter ou refuser une candidature, consulter les statistiques |
| `admin` | Gerer les comptes, forcer un changement de rôle (trace dans les logs applicatifs) |

L'inscription publique n'autorise que `student` et `company`.
Les rôles à priviléges sont attribues uniquement via `PATCH /users/{id}/role`.

## Invariants métier

- Une offre ne peut être soumise que si `title`, `mission` et `skills` sont renseignes.
- Transitions d'une offre : `draft -> submitted -> published | rejected`.
- Transitions d'une candidature : `pending -> accepted | rejected | withdrawn`.
- Un étudiant ne peut avoir qu'une candidature active par offre (contrainte
  d'unicité en base + vérification applicative).
- Une candidature acceptée ne peut plus etre retirée par l'étudiant.
- Une entreprise ne peut jamais consulter les candidatures d'une autre entreprise.

## Codes HTTP

| Code | Signification |
|---|---|
| 400 | Règle métier non respectee |
| 401 | Non authentifie : jeton absent, invalide ou expire |
| 403 | Authentifié mais non habilité |
| 404 | Ressource absente **ou non visible** pour l'appelant |
| 422 | Payload invalide (validation Pydantic) |

Le 404 sur une ressource existante mais non visible est déliberé : répondre 403
confirmerait son existence.

## Variables d'environnement

Copier `.env.example` vers `.env` et adapter les valeurs.

| Variable | Description | Défaut |
|---|---|---|
| `APP_NAME` | Nom affiche dans OpenAPI | `StageFlow API` |
| `ENVIRONMENT` | `development`, `test` ou `production` | `development` |
| `DEBUG` | Logs verbeux | `false` |
| `DATABASE_URL` | URL SQLAlchemy | `sqlite:///./stageflow.db` |
| `JWT_SECRET_KEY` | Cle de signature — **obligatoire, sans defaut** | — |
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

### Jeu de donnees de demonstration

Les roles `admin` et `program_manager` ne peuvent pas être obtenus par
inscription publique (protection contre le *mass assignment*). Un script
d'amorcage crée les comptes à privilégés :

```bash
python scripts_seed.py
```

| Compte | Rôle |
|---|---|
| `admin@dsia.fr` | admin |
| `resp@dsia.fr` | program_manager |
| `contact@dataforge.fr` | company |
| `rh@analytika.fr` | company |
| `eleve@dsia.fr` | student |

Mot de passe commun : `Passw0rd!`. Le script est idempotent et refuse de
s'executer si `ENVIRONMENT=production`.

## Lancement avec Docker

```bash
docker compose up -d --build
```

Lance PostgreSQL, applique les migrations, puis démarre l'API sur
http://localhost:8000. La base est exposée sur le port hote 5433.

```bash
docker compose logs -f api
docker compose down
```

L'image de production tourne sous un utilisateur non privilégié (`appuser`) et
expose une sonde `/health` utilisee par le `HEALTHCHECK` Docker.

## Tests

```bash
pytest                                              # tous les tests
pytest tests/unit -v                                # unitaires
pytest tests/integration -v                         # integration
pytest --cov=app --cov-report=term-missing          # avec couverture
```

Les tests utilisent une base SQLite en mémoire, recréée pour chaque test via
`dependency_overrides`. Aucune configuration préalable n'est requise.

Couverture actuelle : ~94 %.

## Endpoints

### Authentification
| Methode | Chemin | Acces |
|---|---|---|
| POST | `/auth/register` | public |
| POST | `/auth/login` | public (formulaire OAuth2) |
| POST | `/auth/login/json` | public (JSON) |

### Utilisateurs
| Methode | Chemin | Accès |
|---|---|---|
| GET | `/users/me` | authentifie |
| GET | `/users` | admin |
| PATCH | `/users/{id}/role` | admin |

### Offres
| Méthode | Chemin | Accès |
|---|---|---|
| POST | `/offers` | company |
| GET | `/offers` | authentifie |
| GET | `/offers/{id}` | authentifie (visibilité selon rôle) |
| PATCH | `/offers/{id}` | company proprietaire |
| PATCH | `/offers/{id}/submit` | company proprietaire |
| PATCH | `/offers/{id}/review` | program_manager |
| GET | `/offers/stats` | program_manager, admin |

### Candidatures
| Methode | Chemin | Acces |
|---|---|---|
| POST | `/offers/{id}/applications` | student |
| GET | `/offers/{id}/applications` | company proprietaire, staff |
| GET | `/applications/me` | student |
| PATCH | `/applications/{id}/decision` | program_manager |
| DELETE | `/applications/{id}` | student proprietaire |

### Supervision
| Methode | Chemin | Acces |
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
- JWT signes HS256 avec expiration ; le jeton est signé, non chiffré — il ne
  contient aucune donnée sensible.
- Autorisation centralisée dans `app/core/permissions.py` via des dépendances
  FastAPI ; aucune logique RBAC dispersée dans les routes.
- Message d'erreur identique pour un email inconnu et un mot de passe erroné,
  afin d'empecher l'enumeration de comptes.
- Middleware `security_headers` : `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `X-Permitted-Cross-Domain-Policies`.
- Middleware `request_id` : identifiant unique par requête, journalise et
  renvoye dans l'en-tete `X-Request-ID`.

## Auteur

Lyliane Fat-nelle G. DAMADO