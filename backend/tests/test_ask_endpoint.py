from tests.conftest import login


def test_ask_without_token_returns_401(client, seeded):
    response = client.post("/ask", json={"question": "What is the vacation policy?"})

    assert response.status_code == 401


def test_ask_with_malformed_token_returns_401(client, seeded):
    response = client.post(
        "/ask",
        json={"question": "What is the vacation policy?"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_ask_with_valid_token_returns_expected_shape(client, seeded):
    token = login(client, "employee@acme-corp.dev")

    response = client.post(
        "/ask",
        json={"question": "What is the Acme Vacation Policy?"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "answer" in body and isinstance(body["answer"], str)
    assert "sources" in body and isinstance(body["sources"], list)
    for source in body["sources"]:
        assert "doc_id" in source
        assert "title" in source
