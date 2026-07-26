"""Amorcage : cree les comptes a privileges et un jeu de donnees de demonstration.

Usage : python scripts_seed.py
Idempotent : relancable sans creer de doublons.
"""

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.role import UserRole
from app.repositories.application_repository import ApplicationRepository
from app.repositories.offer_repository import OfferRepository
from app.repositories.user_repository import UserRepository
from app.utils.hashing import hash_password

MDP_DEMO = "Passw0rd!"

COMPTES = [
    ("admin@dsia.fr", UserRole.ADMIN, "Administrateur DSIA", None),
    ("resp@dsia.fr", UserRole.PROGRAM_MANAGER, "Responsable Pedagogique", None),
    ("contact@dataforge.fr", UserRole.COMPANY, "DataForge", "DataForge SAS"),
    ("rh@analytika.fr", UserRole.COMPANY, "Analytika", "Analytika SARL"),
    ("eleve@dsia.fr", UserRole.STUDENT, "Etudiant DSIA", None),
]


def main() -> None:
    if settings.environment == "production":
        raise SystemExit("Seed interdit en production.")

    db = SessionLocal()
    users = UserRepository(db)
    offers = OfferRepository(db)
    applications = ApplicationRepository(db)

    crees = {}
    for email, role, nom, entreprise in COMPTES:
        existant = users.get_by_email(email)
        if existant:
            crees[email] = existant
            print(f"  = {email:28} {role.value:16} (deja present)")
            continue
        crees[email] = users.create(
            email=email,
            hashed_password=hash_password(MDP_DEMO),
            full_name=nom,
            role=role,
            company_name=entreprise,
        )
        print(f"  + {email:28} {role.value:16} cree")

    # Une offre publiee et une candidature, pour une demo immediate.
    entreprise = crees["contact@dataforge.fr"]
    etudiant = crees["eleve@dsia.fr"]

    _, total = offers.list_by_company(entreprise.id, limit=1, offset=0)
    if total == 0:
        offre = offers.create_draft(
            company=entreprise,
            title="Stage Data Scientist - Prevision de la demande",
            mission="Concevoir et evaluer des modeles de prevision de series temporelles.",
            skills="Python, pandas, scikit-learn, SQL",
            location="Dakar",
        )
        offers.submit(offre)
        offers.review(offre, decision="publish", comment="Offre conforme.")
        applications.create(
            offer=offre,
            student_id=etudiant.id,
            motivation=(
                "Ce stage correspond a mon projet professionnel en science des "
                "donnees et aux competences travaillees durant le Master DSIA."
            ),
        )
        print(f"  + offre #{offre.id} publiee et candidature #1 deposee")

    db.close()
    print(f"\nMot de passe commun : {MDP_DEMO}")


if __name__ == "__main__":
    main()
