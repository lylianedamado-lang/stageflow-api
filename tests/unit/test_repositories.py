import pytest

from app.core.errors import BusinessRuleError, NotFoundError
from app.models.application import ApplicationStatus
from app.models.offer import OfferStatus
from app.repositories.application_repository import ApplicationRepository
from app.repositories.offer_repository import OfferRepository


@pytest.fixture()
def offer_repo(db_session) -> OfferRepository:
    return OfferRepository(db_session)


@pytest.fixture()
def app_repo(db_session) -> ApplicationRepository:
    return ApplicationRepository(db_session)


@pytest.fixture()
def offre_publiee(offer_repo, company_a):
    """Une offre complète, soumise puis publiée."""
    offre = offer_repo.create_draft(
        company=company_a,
        title="Stage NLP",
        mission="Entraîner des modèles",
        skills="Python, PyTorch",
        location="Dakar",
    )
    offer_repo.submit(offre)
    offer_repo.review(offre, decision="publish", comment=None)
    return offre


class TestCycleDeVieOffre:
    def test_une_offre_nait_en_brouillon(self, offer_repo, company_a):
        offre = offer_repo.create_draft(company=company_a, title="Titre")
        assert offre.status is OfferStatus.DRAFT
        assert offre.company_id == company_a.id

    def test_soumission_refusee_si_champs_manquants(self, offer_repo, company_a):
        offre = offer_repo.create_draft(company=company_a, title="Titre seul")
        with pytest.raises(BusinessRuleError, match="manquants"):
            offer_repo.submit(offre)
        assert offre.status is OfferStatus.DRAFT

    def test_soumission_reussie_si_offre_complete(self, offer_repo, company_a):
        offre = offer_repo.create_draft(
            company=company_a, title="T", mission="M", skills="S"
        )
        offer_repo.submit(offre)
        assert offre.status is OfferStatus.SUBMITTED

    def test_double_soumission_refusee(self, offer_repo, company_a):
        offre = offer_repo.create_draft(
            company=company_a, title="T", mission="M", skills="S"
        )
        offer_repo.submit(offre)
        with pytest.raises(BusinessRuleError, match="Transition invalide"):
            offer_repo.submit(offre)

    def test_modification_refusee_hors_brouillon(self, offer_repo, company_a):
        offre = offer_repo.create_draft(
            company=company_a, title="T", mission="M", skills="S"
        )
        offer_repo.submit(offre)
        with pytest.raises(BusinessRuleError, match="brouillon"):
            offer_repo.update_draft(offre, title="Nouveau")

    def test_arbitrage_refuse_sur_un_brouillon(self, offer_repo, company_a):
        offre = offer_repo.create_draft(company=company_a, title="T")
        with pytest.raises(BusinessRuleError, match="soumise"):
            offer_repo.review(offre, decision="publish", comment=None)

    def test_publication(self, offer_repo, company_a):
        offre = offer_repo.create_draft(
            company=company_a, title="T", mission="M", skills="S"
        )
        offer_repo.submit(offre)
        offer_repo.review(offre, decision="publish", comment="OK")
        assert offre.status is OfferStatus.PUBLISHED
        assert offre.review_comment == "OK"

    def test_refus(self, offer_repo, company_a):
        offre = offer_repo.create_draft(
            company=company_a, title="T", mission="M", skills="S"
        )
        offer_repo.submit(offre)
        offer_repo.review(offre, decision="reject", comment="Trop vague")
        assert offre.status is OfferStatus.REJECTED

    def test_double_arbitrage_refuse(self, offer_repo, offre_publiee):
        with pytest.raises(BusinessRuleError):
            offer_repo.review(offre_publiee, decision="reject", comment=None)

    def test_get_or_404_sur_offre_absente(self, offer_repo):
        with pytest.raises(NotFoundError):
            offer_repo.get_or_404(9999)


class TestListesEtStatistiques:
    def test_seules_les_offres_publiees_sont_listees(
        self, offer_repo, company_a, offre_publiee
    ):
        offer_repo.create_draft(company=company_a, title="Brouillon cache")
        items, total = offer_repo.list_published(limit=10, offset=0)
        assert total == 1
        assert items[0].id == offre_publiee.id

    def test_liste_par_entreprise_inclut_les_brouillons(
        self, offer_repo, company_a, offre_publiee
    ):
        offer_repo.create_draft(company=company_a, title="Brouillon")
        _, total = offer_repo.list_by_company(company_a.id, limit=10, offset=0)
        assert total == 2

    def test_une_entreprise_ne_voit_pas_les_offres_d_une_autre(
        self, offer_repo, company_b, offre_publiee
    ):
        _, total = offer_repo.list_by_company(company_b.id, limit=10, offset=0)
        assert total == 0

    def test_pagination(self, offer_repo, company_a):
        for i in range(5):
            offre = offer_repo.create_draft(
                company=company_a, title=f"T{i}", mission="M", skills="S"
            )
            offer_repo.submit(offre)
            offer_repo.review(offre, decision="publish", comment=None)
        page1, total = offer_repo.list_published(limit=2, offset=0)
        page2, _ = offer_repo.list_published(limit=2, offset=2)
        assert total == 5
        assert len(page1) == 2
        assert {o.id for o in page1}.isdisjoint({o.id for o in page2})

    def test_comptage_par_statut(self, offer_repo, offre_publiee):
        counts = offer_repo.count_by_status()
        assert counts["published"] == 1
        assert counts["draft"] == 0
        assert set(counts) == {"draft", "submitted", "published", "rejected"}


class TestInvariantsCandidature:
    def test_candidature_refusee_sur_offre_non_publiee(
        self, offer_repo, app_repo, company_a, student
    ):
        brouillon = offer_repo.create_draft(company=company_a, title="T")
        with pytest.raises(BusinessRuleError, match="non publiée"):
            app_repo.create(
                offer=brouillon, student_id=student.id, motivation="m" * 30
            )

    def test_candidature_creee_en_attente(self, app_repo, offre_publiee, student):
        candidature = app_repo.create(
            offer=offre_publiee, student_id=student.id, motivation="m" * 30
        )
        assert candidature.status is ApplicationStatus.PENDING

    def test_une_seule_candidature_active_par_offre(
        self, app_repo, offre_publiee, student
    ):
        app_repo.create(offer=offre_publiee, student_id=student.id, motivation="m" * 30)
        with pytest.raises(BusinessRuleError, match="déjà"):
            app_repo.create(
                offer=offre_publiee, student_id=student.id, motivation="autre" * 10
            )

    def test_acceptation(self, app_repo, offre_publiee, student):
        candidature = app_repo.create(
            offer=offre_publiee, student_id=student.id, motivation="m" * 30
        )
        app_repo.decide(candidature, decision="accept", comment="Bon profil")
        assert candidature.status is ApplicationStatus.ACCEPTED
        assert candidature.decision_comment == "Bon profil"

    def test_refus(self, app_repo, offre_publiee, student):
        candidature = app_repo.create(
            offer=offre_publiee, student_id=student.id, motivation="m" * 30
        )
        app_repo.decide(candidature, decision="reject", comment=None)
        assert candidature.status is ApplicationStatus.REJECTED

    def test_double_arbitrage_refuse(self, app_repo, offre_publiee, student):
        candidature = app_repo.create(
            offer=offre_publiee, student_id=student.id, motivation="m" * 30
        )
        app_repo.decide(candidature, decision="accept", comment=None)
        with pytest.raises(BusinessRuleError, match="en attente"):
            app_repo.decide(candidature, decision="reject", comment=None)

    def test_retrait_possible_tant_que_en_attente(
        self, app_repo, offre_publiee, student
    ):
        candidature = app_repo.create(
            offer=offre_publiee, student_id=student.id, motivation="m" * 30
        )
        app_repo.withdraw(candidature)
        assert candidature.status is ApplicationStatus.WITHDRAWN

    def test_retrait_impossible_apres_acceptation(
        self, app_repo, offre_publiee, student
    ):
        candidature = app_repo.create(
            offer=offre_publiee, student_id=student.id, motivation="m" * 30
        )
        app_repo.decide(candidature, decision="accept", comment=None)
        with pytest.raises(BusinessRuleError, match="acceptée"):
            app_repo.withdraw(candidature)
        assert candidature.status is ApplicationStatus.ACCEPTED

    def test_double_retrait_refuse(self, app_repo, offre_publiee, student):
        candidature = app_repo.create(
            offer=offre_publiee, student_id=student.id, motivation="m" * 30
        )
        app_repo.withdraw(candidature)
        with pytest.raises(BusinessRuleError):
            app_repo.withdraw(candidature)

    def test_get_or_404_sur_candidature_absente(self, app_repo):
        with pytest.raises(NotFoundError):
            app_repo.get_or_404(9999)

    def test_comptage_par_statut(self, app_repo, offre_publiee, student):
        app_repo.create(offer=offre_publiee, student_id=student.id, motivation="m" * 30)
        counts = app_repo.count_by_status()
        assert counts["pending"] == 1
        assert set(counts) == {"pending", "accepted", "rejected", "withdrawn"}