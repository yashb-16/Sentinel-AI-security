from jose import jwt

from app.config import get_settings


def test_login_succeeds_with_correct_credentials(client, seeded):
    response = client.post(
        "/auth/login", json={"email": "employee@acme-corp.dev", "password": "password123"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_fails_with_wrong_password(client, seeded):
    response = client.post(
        "/auth/login", json={"email": "employee@acme-corp.dev", "password": "wrong-password"}
    )

    assert response.status_code == 401


def test_login_fails_with_unknown_email(client, seeded):
    response = client.post(
        "/auth/login", json={"email": "nobody@acme-corp.dev", "password": "password123"}
    )

    assert response.status_code == 401


def test_login_jwt_contains_expected_claims(client, seeded):
    response = client.post(
        "/auth/login", json={"email": "hr@acme-corp.dev", "password": "password123"}
    )
    token = response.json()["access_token"]

    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

    acme_user = seeded["users"]["acme_hr"]
    assert payload["sub"] == str(acme_user.id)
    assert payload["tenant_id"] == str(acme_user.tenant_id)
    assert payload["role"] == "hr"
    assert "exp" in payload
