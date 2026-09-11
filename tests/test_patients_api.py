def test_create_returns_201_with_generated_id(client, valid_patient):
    response = client.post("/patients", json=valid_patient)

    assert response.status_code == 201
    body = response.json()
    assert body["error"] is None
    assert body["data"]["patient_id"]
    # Stored canonically even though it was submitted formatted.
    assert body["data"]["phone_number"] == "4155550142"


def test_get_by_id_round_trips(client, valid_patient):
    created = client.post("/patients", json=valid_patient).json()["data"]

    response = client.get(f"/patients/{created['patient_id']}")

    assert response.status_code == 200
    assert response.json()["data"]["last_name"] == "Doe"


def test_unknown_id_returns_404_in_envelope(client):
    response = client.get("/patients/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"data": None, "error": "No patient found with id does-not-exist"}


def test_invalid_payload_returns_422_in_envelope(client, valid_patient):
    response = client.post("/patients", json={**valid_patient, "date_of_birth": "2090-01-01"})

    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert "future" in body["error"]


def test_list_filters_by_last_name(client, valid_patient):
    client.post("/patients", json=valid_patient)
    client.post(
        "/patients",
        json={**valid_patient, "last_name": "Ramirez", "phone_number": "2125550188"},
    )

    response = client.get("/patients", params={"last_name": "Ramirez"})

    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["last_name"] == "Ramirez"


def test_partial_update_leaves_other_fields_untouched(client, valid_patient):
    created = client.post("/patients", json=valid_patient).json()["data"]

    response = client.put(f"/patients/{created['patient_id']}", json={"city": "Oakland"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["city"] == "Oakland"
    assert data["last_name"] == "Doe"


def test_delete_is_soft_and_hides_the_record(client, valid_patient):
    created = client.post("/patients", json=valid_patient).json()["data"]

    assert client.delete(f"/patients/{created['patient_id']}").status_code == 200
    assert client.get(f"/patients/{created['patient_id']}").status_code == 404
    assert client.get("/patients").json()["data"] == []
