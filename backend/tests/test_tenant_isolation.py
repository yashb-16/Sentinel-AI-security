"""SECURITY: a user in one tenant must never receive content, or even a
`sources` reference, belonging to another tenant -- even when the question
directly quotes the other tenant's document text.
"""

from tests.conftest import login


def test_acme_user_cannot_retrieve_globex_document(client, seeded):
    token = login(client, "employee@acme-corp.dev")

    response = client.post(
        "/ask",
        json={"question": "What is the Globex Vacation Policy for employees?"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    globex_doc = seeded["documents"]["globex_general"]
    source_ids = {source["doc_id"] for source in body["sources"]}
    assert str(globex_doc.id) not in source_ids


def test_globex_user_cannot_retrieve_acme_document_even_quoting_its_content(client, seeded):
    token = login(client, "employee@globex-corp.dev")

    response = client.post(
        "/ask",
        json={
            "question": "Acme employees get 20 days of paid vacation per year, is that true here?"
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    acme_doc = seeded["documents"]["acme_general"]
    source_ids = {source["doc_id"] for source in body["sources"]}
    assert str(acme_doc.id) not in source_ids


def test_acme_user_only_sees_acme_documents_in_sources(client, seeded):
    token = login(client, "admin@acme-corp.dev")

    response = client.post(
        "/ask",
        json={"question": "Tell me about vacation policy and salary bands."},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    acme_doc_ids = {str(doc.id) for key, doc in seeded["documents"].items() if key.startswith("acme_")}
    source_ids = {source["doc_id"] for source in body["sources"]}
    assert source_ids.issubset(acme_doc_ids)
