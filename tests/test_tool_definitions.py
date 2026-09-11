"""Guard against drift between the documented tool schema and the API schema.

The tool definitions in prompts/patient_intake.md are pasted into the Vapi
dashboard by hand. If they fall out of step with PatientCreate, the agent
collects the wrong things and every call fails at the point of saving - a
failure that only shows up on a live phone call. Cheaper to catch here.
"""

import json
import re
from pathlib import Path

import pytest

from app.schemas import PatientCreate

PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / "patient_intake.md"


@pytest.fixture(scope="module")
def tools():
    blocks = re.findall(r"```json\n(.*?)```", PROMPT_FILE.read_text(encoding="utf-8"), re.S)
    return {tool["function"]["name"]: tool["function"] for tool in json.loads(blocks[0])}


def test_all_three_tools_are_defined(tools):
    assert set(tools) == {"lookup_patient_by_phone", "create_patient", "update_patient"}


def test_create_tool_requires_exactly_the_schema_required_fields(tools):
    schema_required = {
        name for name, field in PatientCreate.model_fields.items() if field.is_required()
    }

    assert set(tools["create_patient"]["parameters"]["required"]) == schema_required


def test_create_tool_exposes_every_schema_field(tools):
    assert set(tools["create_patient"]["parameters"]["properties"]) == set(
        PatientCreate.model_fields
    )
