import pytest

OFFRE_COMPLETE = {
    "title": "Stage Data Science",
    "mission": "Construire des modeles de prevision",
    "skills": "Python, SQL, scikit-learn",
    "location": "Dakar",
}
MOTIVATION = "Je suis tres motive par ce stage " * 3


@pytest.fixture()
def offre_publiee_id(client, company_a, manager, auth_headers):
    """Une offre complete, soumise et publiee, via l'API."""
    ha = auth_headers(company_a.email)
    hr = auth_headers(manager.email)
    oid = client.post("/offers", json=OFFRE_COMPLETE, headers=ha).json()["id"]
    client.patch(f"/offers/{oid}/submit", headers=ha)
    client.patch(f"/offers/{oid}/review", json={"decision": "publish"}, headers=hr)
    return oid


class TestParcoursNominalComplet:
    def test_de_la_creation_a_l_acceptation(
        self, client, company_a, manager, student, auth_headers
    ):
        ha, hr, he = (
            auth_headers(company_a.email),
            auth_headers(manager.email),
            auth_headers(student.email),
        )

        r = client.post("/offers", json=OFFRE_COMPLETE, headers=ha)
        assert r.status_code == 201
        assert r.json()["status"] == "draft"
        oid = r.json()["id"]

        assert client.patch(f"/offers/{oid}/submit", headers=ha).json()["status"] == "submitted"

        r = client.patch(f"/offers/{oid}/review",
                         json={"decision": "publish", "comment": "Validee"}, headers=hr)
        assert r.json()["status"] == "published"

        r = client.get("/offers", headers=he)
        assert r.json()["total"] == 1

        r = client.post(f"/offers/{oid}/applications",
                        json={"motivation": MOTIVATION}, headers=he)
        assert r.status_code == 201
        aid = r.json()["id"]
        assert r.json()["status"] == "pending"

        r = client.get("/applications/me", headers=he)
        assert r.json()["total"] == 1

        r = client.get(f"/offers/{oid}/applications", headers=ha)
        assert r.json()["total"] == 1

        r = client.patch(f"/applications/{aid}/decision",
                         json={"decision": "accept", "comment": "Bon profil"}, headers=hr)
        assert r.json()["status"] == "accepted"


class TestIsolationEntreEntreprises:
    """Test exige par le sujet."""

    def test_une_entreprise_ne_voit_pas_les_candidatures_d_une_autre(
        self, client, company_b, offre_publiee_id, student, auth_headers
    ):
        client.post(f"/offers/{offre_publiee_id}/applications",
                    json={"motivation": MOTIVATION},
                    headers=auth_headers(student.email))
        r = client.get(f"/offers/{offre_publiee_id}/applications",
                       headers=auth_headers(company_b.email))
        assert r.status_code == 403

    def test_une_entreprise_ne_peut_pas_soumettre_l_offre_d_une_autre(
        self, client, company_b, offre_publiee_id, auth_headers
    ):
        r = client.patch(f"/offers/{offre_publiee_id}/submit",
                         headers=auth_headers(company_b.email))
        assert r.status_code in (400, 403)

    def test_le_brouillon_d_une_autre_entreprise_renvoie_404(
        self, client, company_a, company_b, auth_headers
    ):
        oid = client.post("/offers", json=OFFRE_COMPLETE,
                          headers=auth_headers(company_a.email)).json()["id"]
        r = client.get(f"/offers/{oid}", headers=auth_headers(company_b.email))
        assert r.status_code == 404

    def test_un_etudiant_ne_voit_pas_les_brouillons(
        self, client, company_a, student, auth_headers
    ):
        oid = client.post("/offers", json=OFFRE_COMPLETE,
                          headers=auth_headers(company_a.email)).json()["id"]
        assert client.get(f"/offers/{oid}",
                          headers=auth_headers(student.email)).status_code == 404


class TestPermissionsParRole:
    def test_un_etudiant_ne_peut_pas_creer_d_offre(self, client, student, auth_headers):
        r = client.post("/offers", json=OFFRE_COMPLETE,
                        headers=auth_headers(student.email))
        assert r.status_code == 403

    def test_une_entreprise_ne_peut_pas_arbitrer(
        self, client, company_a, offre_publiee_id, auth_headers
    ):
        r = client.patch(f"/offers/{offre_publiee_id}/review",
                         json={"decision": "publish"},
                         headers=auth_headers(company_a.email))
        assert r.status_code == 403

    def test_une_entreprise_ne_peut_pas_candidater(
        self, client, company_a, offre_publiee_id, auth_headers
    ):
        r = client.post(f"/offers/{offre_publiee_id}/applications",
                        json={"motivation": MOTIVATION},
                        headers=auth_headers(company_a.email))
        assert r.status_code == 403

    def test_les_stats_sont_reservees_au_staff(self, client, student, auth_headers):
        assert client.get("/offers/stats",
                          headers=auth_headers(student.email)).status_code == 403

    def test_le_responsable_accede_aux_stats(self, client, manager, auth_headers):
        r = client.get("/offers/stats", headers=auth_headers(manager.email))
        assert r.status_code == 200
        assert "offers_by_status" in r.json()


class TestInvariantsViaAPI:
    def test_soumission_d_une_offre_incomplete_refusee(
        self, client, company_a, auth_headers
    ):
        ha = auth_headers(company_a.email)
        oid = client.post("/offers", json={"title": "Titre seul"}, headers=ha).json()["id"]
        assert client.patch(f"/offers/{oid}/submit", headers=ha).status_code == 400

    def test_double_candidature_refusee(
        self, client, offre_publiee_id, student, auth_headers
    ):
        he = auth_headers(student.email)
        client.post(f"/offers/{offre_publiee_id}/applications",
                    json={"motivation": MOTIVATION}, headers=he)
        r = client.post(f"/offers/{offre_publiee_id}/applications",
                        json={"motivation": MOTIVATION}, headers=he)
        assert r.status_code == 400

    def test_retrait_impossible_apres_acceptation(
        self, client, offre_publiee_id, student, manager, auth_headers
    ):
        he = auth_headers(student.email)
        aid = client.post(f"/offers/{offre_publiee_id}/applications",
                          json={"motivation": MOTIVATION}, headers=he).json()["id"]
        client.patch(f"/applications/{aid}/decision", json={"decision": "accept"},
                     headers=auth_headers(manager.email))
        assert client.delete(f"/applications/{aid}", headers=he).status_code == 400

    def test_retrait_reussi_avant_decision(
        self, client, offre_publiee_id, student, auth_headers
    ):
        he = auth_headers(student.email)
        aid = client.post(f"/offers/{offre_publiee_id}/applications",
                          json={"motivation": MOTIVATION}, headers=he).json()["id"]
        assert client.delete(f"/applications/{aid}", headers=he).status_code == 204

    def test_candidature_impossible_sur_offre_non_publiee(
        self, client, company_a, student, auth_headers
    ):
        oid = client.post("/offers", json=OFFRE_COMPLETE,
                          headers=auth_headers(company_a.email)).json()["id"]
        r = client.post(f"/offers/{oid}/applications", json={"motivation": MOTIVATION},
                        headers=auth_headers(student.email))
        assert r.status_code == 404

    def test_decision_invalide_refusee(
        self, client, offre_publiee_id, manager, auth_headers
    ):
        r = client.patch(f"/offers/{offre_publiee_id}/review",
                         json={"decision": "supprimer"},
                         headers=auth_headers(manager.email))
        assert r.status_code == 422
