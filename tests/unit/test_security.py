from datetime import timedelta

import pytest

from app.core.errors import AuthenticationError
from app.core.security import create_access_token, decode_access_token
from app.utils.hashing import hash_password, verify_password


class TestHashing:
    def test_le_hash_ne_contient_pas_le_mot_de_passe(self):
        hashe = hash_password("Passw0rd123!")
        assert "Passw0rd123!" not in hashe
        assert hashe.startswith("$2b$")

    def test_deux_hash_du_meme_mot_de_passe_different(self):
        assert hash_password("Passw0rd123!") != hash_password("Passw0rd123!")

    def test_verification_reussit_avec_le_bon_mot_de_passe(self):
        assert verify_password("Passw0rd123!", hash_password("Passw0rd123!")) is True

    def test_verification_echoue_avec_un_mauvais_mot_de_passe(self):
        assert verify_password("Mauvais", hash_password("Passw0rd123!")) is False

    def test_verification_ne_leve_pas_sur_un_hash_invalide(self):
        assert verify_password("Passw0rd123!", "pas-un-hash") is False


class TestJWT:
    def test_le_jeton_contient_le_sujet_et_le_role(self):
        payload = decode_access_token(create_access_token(subject=42, role="student"))
        assert payload["sub"] == "42"
        assert payload["role"] == "student"
        assert payload["type"] == "access"

    def test_le_sujet_est_serialise_en_chaine(self):
        payload = decode_access_token(create_access_token(subject=7, role="admin"))
        assert isinstance(payload["sub"], str)

    def test_un_jeton_falsifie_est_rejete(self):
        jeton = create_access_token(subject=1, role="student")
        with pytest.raises(AuthenticationError):
            decode_access_token(jeton[:-6] + "AAAAAA")

    def test_un_jeton_expire_est_rejete(self):
        jeton = create_access_token(
            subject=1, role="student", expires_delta=timedelta(seconds=-10)
        )
        with pytest.raises(AuthenticationError, match="expiré"):
            decode_access_token(jeton)

    def test_une_chaine_quelconque_est_rejetee(self):
        with pytest.raises(AuthenticationError):
            decode_access_token("nimportequoi")
