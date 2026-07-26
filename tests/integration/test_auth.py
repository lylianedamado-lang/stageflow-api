from app.models.role import UserRole

MDP = "Passw0rd!"


class TestInscription:
    def test_inscription_etudiant(self, client):
        r = client.post("/auth/register", json={
            "email": "nouveau@dsia.fr", "password": MDP, "full_name": "Nouveau",
        })
        assert r.status_code == 201
        assert r.json()["role"] == "student"

    def test_le_mot_de_passe_ne_ressort_jamais(self, client):
        r = client.post("/auth/register", json={
            "email": "n2@dsia.fr", "password": MDP, "full_name": "Nouveau",
        })
        corps = r.json()
        assert "password" not in corps
        assert "hashed_password" not in corps

    def test_email_deja_utilise_refuse(self, client, student):
        r = client.post("/auth/register", json={
            "email": student.email, "password": MDP, "full_name": "Doublon",
        })
        assert r.status_code == 400

    def test_inscription_admin_refusee(self, client):
        r = client.post("/auth/register", json={
            "email": "pirate@dsia.fr", "password": MDP,
            "full_name": "Pirate", "role": "admin",
        })
        assert r.status_code == 422

    def test_entreprise_sans_nom_refusee(self, client):
        r = client.post("/auth/register", json={
            "email": "c@boite.fr", "password": MDP,
            "full_name": "Boite", "role": "company",
        })
        assert r.status_code == 422


class TestConnexion:
    def test_connexion_reussie(self, client, student):
        r = client.post("/auth/login/json",
                        json={"email": student.email, "password": MDP})
        assert r.status_code == 200
        assert r.json()["token_type"] == "bearer"
        assert r.json()["access_token"]

    def test_connexion_formulaire_oauth2(self, client, student):
        r = client.post("/auth/login",
                        data={"username": student.email, "password": MDP})
        assert r.status_code == 200

    def test_mauvais_mot_de_passe(self, client, student):
        r = client.post("/auth/login/json",
                        json={"email": student.email, "password": "Faux1234!"})
        assert r.status_code == 401

    def test_email_inconnu(self, client):
        r = client.post("/auth/login/json",
                        json={"email": "fantome@dsia.fr", "password": MDP})
        assert r.status_code == 401

    def test_message_identique_pour_les_deux_echecs(self, client, student):
        r1 = client.post("/auth/login/json",
                         json={"email": student.email, "password": "Faux1234!"})
        r2 = client.post("/auth/login/json",
                         json={"email": "fantome@dsia.fr", "password": MDP})
        assert r1.json()["detail"] == r2.json()["detail"]

    def test_compte_desactive_refuse(self, client, make_user):
        u = make_user("off@dsia.fr", UserRole.STUDENT, is_active=False)
        r = client.post("/auth/login/json", json={"email": u.email, "password": MDP})
        assert r.status_code == 401


class TestProtectionDesRoutes:
    def test_sans_jeton(self, client):
        assert client.get("/users/me").status_code == 401

    def test_jeton_invalide(self, client):
        r = client.get("/users/me", headers={"Authorization": "Bearer nawak"})
        assert r.status_code == 401

    def test_jeton_valide(self, client, student, auth_headers):
        r = client.get("/users/me", headers=auth_headers(student.email))
        assert r.status_code == 200
        assert r.json()["email"] == student.email

    def test_liste_users_interdite_aux_non_admins(self, client, student, auth_headers):
        r = client.get("/users", headers=auth_headers(student.email))
        assert r.status_code == 403

    def test_liste_users_autorisee_a_l_admin(self, client, admin, auth_headers):
        r = client.get("/users", headers=auth_headers(admin.email))
        assert r.status_code == 200

    def test_admin_ne_peut_pas_changer_son_propre_role(
        self, client, admin, auth_headers
    ):
        r = client.patch(f"/users/{admin.id}/role", json={"role": "student"},
                         headers=auth_headers(admin.email))
        assert r.status_code == 400


class TestMiddlewaresEtSante:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_entete_request_id_present(self, client):
        assert client.get("/health").headers.get("X-Request-ID")

    def test_entetes_de_securite_presents(self, client):
        h = client.get("/health").headers
        assert h["X-Content-Type-Options"] == "nosniff"
        assert h["X-Frame-Options"] == "DENY"

    def test_openapi_accessible(self, client):
        assert client.get("/openapi.json").status_code == 200
