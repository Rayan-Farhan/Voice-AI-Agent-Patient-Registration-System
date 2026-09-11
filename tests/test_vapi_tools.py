"""Smoke coverage for the agent-facing webhook.

Payloads mirror Vapi's documented shape: message.toolCallList entries carrying
id/name/arguments, answered with a results array keyed by toolCallId.
"""

SECRET = "test-secret"  # matches tests/conftest.py
HEADERS = {"x-vapi-secret": SECRET}


def tool_call(name, arguments, call_id="call-1", tool_call_id="tc-1"):
    return {
        "message": {
            "type": "tool-calls",
            "call": {"id": call_id},
            "toolCallList": [{"id": tool_call_id, "name": name, "arguments": arguments}],
        }
    }


def test_tool_call_without_secret_is_rejected(client, valid_patient):
    response = client.post("/vapi/tools", json=tool_call("create_patient", valid_patient))

    assert response.status_code == 401


def test_create_patient_via_tool_persists_and_is_readable_over_rest(client, valid_patient):
    response = client.post(
        "/vapi/tools", json=tool_call("create_patient", valid_patient), headers=HEADERS
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["toolCallId"] == "tc-1"
    assert result["result"]["success"] is True

    listed = client.get("/patients").json()["data"]
    assert len(listed) == 1
    assert listed[0]["patient_id"] == result["result"]["patient_id"]


def test_invalid_field_returns_spoken_guidance_not_an_error_status(client, valid_patient):
    """A non-2xx would leave the agent with nothing to say, so bad input comes
    back as 200 with text naming the offending field."""
    bad = {**valid_patient, "phone_number": "555"}

    response = client.post("/vapi/tools", json=tool_call("create_patient", bad), headers=HEADERS)

    assert response.status_code == 200
    result = response.json()["results"][0]["result"]
    assert "phone number" in result
    assert "10-digit" in result


def test_lookup_recognises_a_returning_caller(client, valid_patient):
    client.post("/vapi/tools", json=tool_call("create_patient", valid_patient), headers=HEADERS)

    response = client.post(
        "/vapi/tools",
        json=tool_call("lookup_patient_by_phone", {"phone_number": "415-555-0142"}),
        headers=HEADERS,
    )

    result = response.json()["results"][0]["result"]
    assert result["found"] is True
    assert result["patient"]["first_name"] == "Jane"


def test_lookup_of_unknown_number_reports_not_found(client):
    response = client.post(
        "/vapi/tools",
        json=tool_call("lookup_patient_by_phone", {"phone_number": "2125550000"}),
        headers=HEADERS,
    )

    assert response.json()["results"][0]["result"]["found"] is False
