"""Amorçage : crée les comptes à privilèges et un jeu de données de démonstration.

Usage : python scripts_seed.py
Idempotent : relançable sans créer de doublons.
"""

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.role import UserRole
from app.repositories.application_repository import ApplicationRepository
from app.repositories.offer_repository import OfferRepository
from app.repositories.user_repository import UserRepository
from app.utils.hashing import hash_password

MDP_DEMO = "Passw0rd123!"

COMPTES = [
    ("admin@isi.sn", UserRole.ADMIN, "Administrateur ISI", None),
    ("resp@isi.sn", UserRole.PROGRAM_MANAGER, "Responsable Pédagogique", None),
    ("contact@teranga-analytics.sn", UserRole.COMPANY,
     "Teranga Analytics", "Teranga Analytics SARL"),
    ("rh@baobab-data.sn", UserRole.COMPANY,
     "Baobab Data", "Baobab Data SUARL"),
    ("eleve@isi.sn", UserRole.STUDENT, "Étudiant DSIA", None),
    ("eleve2@isi.sn", UserRole.STUDENT, "Étudiante DSIA", None),
]

# (email entreprise, statut visé, champs de l'offre)
OFFRES = [
    ("contact@teranga-analytics.sn", "published", {
        "title": "Stage Data Scientist - Prévision de la demande en énergie",
        "mission": "Construire et évaluer des modèles de prévision de séries "
                   "temporelles sur les données de consommation électrique.",
        "skills": "Python, pandas, scikit-learn, statsmodels, SQL",
        "location": "Dakar",
    }),
    ("contact@teranga-analytics.sn", "published", {
        "title": "Stage Data Engineer - Industrialisation d'un pipeline de collecte",
        "mission": "Concevoir un pipeline d'ingestion et de nettoyage de données "
                   "hétérogènes, avec orchestration et supervision.",
        "skills": "Python, SQL, Airflow, Docker, PostgreSQL",
        "location": "Dakar",
    }),
    ("rh@baobab-data.sn", "published", {
        "title": "Stage Analyste BI - Tableaux de bord de suivi commercial",
        "mission": "Modéliser un entrepôt de données et produire des tableaux "
                   "de bord de pilotage pour les équipes commerciales.",
        "skills": "SQL, Power BI, modélisation dimensionnelle, Excel",
        "location": "Dakar",
    }),
    # Laissée au statut soumis : permet de démontrer l'arbitrage du responsable.
    ("rh@baobab-data.sn", "submitted", {
        "title": "Stage MLOps - Déploiement de modèles de scoring",
        "mission": "Mettre en production des modèles de scoring : conteneurisation, "
                   "exposition par API, suivi des performances en ligne.",
        "skills": "Python, FastAPI, Docker, MLflow, CI/CD",
        "location": "Dakar",
    }),
    # Laissée en brouillon : permet de démontrer le 404 sur une offre non visible.
    ("contact@teranga-analytics.sn", "draft", {
        "title": "Stage NLP - Analyse de verbatims clients en wolof et français",
        "mission": "Explorer des techniques de classification de texte multilingue "
                   "sur des retours clients.",
        "skills": None,
        "location": "Dakar",
    }),
]

# (email étudiant, début du titre de l'offre visée, motivation)
CANDIDATURES = [
    ("eleve@isi.sn", "Stage Data Scientist",
     "Ce stage correspond à mon projet professionnel en science des données "
     "et aux compétences travaillées durant le Master DSIA."),
    ("eleve2@isi.sn", "Stage Data Scientist",
     "Les séries temporelles ont été le sujet de mon projet de fin de semestre, "
     "je souhaite approfondir ce domaine en conditions réelles."),
    ("eleve@isi.sn", "Stage Analyste BI",
     "La modélisation dimensionnelle et la restitution sont les aspects du "
     "métier de la donnée qui m'intéressent le plus."),
]


def creer_comptes(users: UserRepository) -> dict:
    """Crée les comptes manquants et retourne tous les comptes par email."""
    comptes = {}
    for email, role, nom, entreprise in COMPTES:
        existant = users.get_by_email(email)
        if existant:
            comptes[email] = existant
            print(f"  = {email:32} {role.value:16} (déjà présent)")
            continue
        comptes[email] = users.create(
            email=email,
            hashed_password=hash_password(MDP_DEMO),
            full_name=nom,
            role=role,
            company_name=entreprise,
        )
        print(f"  + {email:32} {role.value:16} créé")
    return comptes


def creer_offres(offers: OfferRepository, comptes: dict) -> dict:
    """Crée les offres manquantes et les amène au statut visé."""
    par_titre = {}
    for email_entreprise, statut_vise, champs in OFFRES:
        entreprise = comptes[email_entreprise]
        existantes, _ = offers.list_by_company(entreprise.id, limit=100, offset=0)
        deja = next((o for o in existantes if o.title == champs["title"]), None)
        if deja:
            par_titre[deja.title] = deja
            print(f"  = offre #{deja.id:<3} {deja.status.value:10} (déjà présente)")
            continue

        offre = offers.create_draft(company=entreprise, **champs)
        if statut_vise in ("submitted", "published"):
            offers.submit(offre)
        if statut_vise == "published":
            offers.review(offre, decision="publish", comment="Offre conforme.")

        par_titre[offre.title] = offre
        print(f"  + offre #{offre.id:<3} {offre.status.value:10} {offre.title[:45]}")
    return par_titre


def creer_candidatures(
    applications: ApplicationRepository, comptes: dict, offres: dict
) -> None:
    """Dépose les candidatures de démonstration, toutes en attente d'arbitrage."""
    for email_etudiant, debut_titre, motivation in CANDIDATURES:
        offre = next(
            (o for titre, o in offres.items() if titre.startswith(debut_titre)), None
        )
        if offre is None:
            continue

        etudiant = comptes[email_etudiant]
        if applications.get_by_offer_and_student(offre.id, etudiant.id):
            print(f"  = candidature {email_etudiant} -> #{offre.id} (déjà présente)")
            continue

        candidature = applications.create(
            offer=offre, student_id=etudiant.id, motivation=motivation
        )
        print(f"  + candidature #{candidature.id} {email_etudiant} -> offre #{offre.id}")


def main() -> None:
    if settings.environment == "production":
        raise SystemExit("Seed interdit en production.")

    db = SessionLocal()
    try:
        comptes = creer_comptes(UserRepository(db))
        offres = creer_offres(OfferRepository(db), comptes)
        creer_candidatures(ApplicationRepository(db), comptes, offres)
    finally:
        db.close()

    print(f"\nMot de passe commun : {MDP_DEMO}")


if __name__ == "__main__":
    main()