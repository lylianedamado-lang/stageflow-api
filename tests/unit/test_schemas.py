import pytest
from pydantic import ValidationError

from app.models.role import UserRole
from app.schemas.application import ApplicationCreate
from app.schemas.offer import OfferReviewRequest
from app.schemas.user import UserCreate, UserRead


class TestSeparationEntreeSortie:
    def test_le_schema_de_sortie_ne_contient_pas_le_hash(self, make_user):
        user = make_user("x@test.fr", UserRole.STUDENT)
        sortie = UserRead.model_validate(user).model_dump()
        assert "hashed_password" not in sortie
        assert "password" not in sortie

    def test_le_schema_de_sortie_expose_les_champs_attendus(self, make_user):
        user = make_user("y@test.fr", UserRole.STUDENT)
        sortie = UserRead.model_validate(user).model_dump()
        assert set(sortie) == {
            "id",
            "email",
            "full_name",
            "role",
            "company_name",
            "is_active",
            "created_at",
        }


class TestValidationInscription:
    def test_inscription_en_admin_refusee(self):
        with pytest.raises(ValidationError):
            UserCreate(
                email="p@test.fr",
                password="Passw0rd!",
                full_name="Pirate",
                role=UserRole.ADMIN,
            )

    def test_inscription_en_responsable_refusee(self):
        with pytest.raises(ValidationError):
            UserCreate(
                email="p@test.fr",
                password="Passw0rd!",
                full_name="Pirate",
                role=UserRole.PROGRAM_MANAGER,
            )

    def test_entreprise_sans_nom_refusee(self):
        with pytest.raises(ValidationError):
            UserCreate(
                email="c@test.fr",
                password="Passw0rd!",
                full_name="Boite",
                role=UserRole.COMPANY,
            )

    def test_etudiant_avec_nom_entreprise_refuse(self):
        with pytest.raises(ValidationError):
            UserCreate(
                email="e@test.fr",
                password="Passw0rd!",
                full_name="Eleve",
                role=UserRole.STUDENT,
                company_name="Boite",
            )

    def test_mot_de_passe_trop_court_refuse(self):
        with pytest.raises(ValidationError):
            UserCreate(email="e@test.fr", password="court", full_name="Eleve")

    def test_email_invalide_refuse(self):
        with pytest.raises(ValidationError):
            UserCreate(email="pas-un-email", password="Passw0rd!", full_name="Eleve")

    def test_inscription_etudiant_valide(self):
        dto = UserCreate(email="e@test.fr", password="Passw0rd!", full_name="Eleve")
        assert dto.role is UserRole.STUDENT


class TestValidationDecisions:
    @pytest.mark.parametrize("decision", ["publish", "reject"])
    def test_decisions_autorisees(self, decision):
        assert OfferReviewRequest(decision=decision).decision == decision

    @pytest.mark.parametrize("decision", ["supprimer", "accept", "", "PUBLISH"])
    def test_decisions_refusees(self, decision):
        with pytest.raises(ValidationError):
            OfferReviewRequest(decision=decision)

    def test_motivation_trop_courte_refusee(self):
        with pytest.raises(ValidationError):
            ApplicationCreate(motivation="trop court")

    def test_motivation_valide(self):
        assert ApplicationCreate(motivation="m" * 30).motivation
