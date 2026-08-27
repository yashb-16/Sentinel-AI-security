"""SECURITY: an Employee-role user must never receive HR-confidential
documents, even from within their own tenant. HR/admin roles can.
"""

from tests.conftest import login


def test_employee_cannot_retrieve_hr_confidential_document_in_own_tenant(client, seeded):
    token = login(client, "employee@acme-corp.dev")

    response = client.post(
        "/ask",
        json={"question": "What is the Acme Salary Bands for engineering L4?"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    hr_doc = seeded["documents"]["acme_hr"]
    source_ids = {source["doc_id"] for source in body["sources"]}
    assert str(hr_doc.id) not in source_ids


def test_hr_role_can_retrieve_hr_confidential_document_in_own_tenant(client, seeded):
    token = login(client, "hr@acme-corp.dev")

    response = client.post(
        "/ask",
        json={"question": "What is the Acme Salary Bands for engineering L4?"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    hr_doc = seeded["documents"]["acme_hr"]
    source_ids = {source["doc_id"] for source in body["sources"]}
    assert str(hr_doc.id) in source_ids


def test_admin_role_can_retrieve_hr_confidential_document_in_own_tenant(client, seeded):
    token = login(client, "admin@acme-corp.dev")

    response = client.post(
        "/ask",
        json={"question": "What is the Acme Salary Bands for engineering L4?"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    hr_doc = seeded["documents"]["acme_hr"]
    source_ids = {source["doc_id"] for source in body["sources"]}
    assert str(hr_doc.id) in source_ids
