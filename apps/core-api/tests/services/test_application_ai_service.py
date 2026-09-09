import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4


CORE_API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CORE_API_ROOT))
SERVICE_PATH = CORE_API_ROOT / "src" / "services" / "application_ai_service.py"
SERVICE_SPEC = spec_from_file_location("application_ai_service_under_test", SERVICE_PATH)
assert SERVICE_SPEC and SERVICE_SPEC.loader
application_ai_service = module_from_spec(SERVICE_SPEC)
SERVICE_SPEC.loader.exec_module(application_ai_service)


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"status": "success", "job_fit_analysis": {"match_score": 8}}


class _Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self) -> "_Client":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def post(self, url: str, *, json: dict) -> _Response:
        self.calls.append((url, json))
        return _Response()


def test_call_match_resume_jd_sends_parsed_documents_without_skill_normalization(
    monkeypatch,
) -> None:
    """Missing per-skill years must not be replaced with global JD experience."""
    client = _Client()
    monkeypatch.setattr(application_ai_service.httpx, "Client", lambda **_: client)
    parsed_jd = {
        "experience_required": {"min_years": 3},
        "skills": {
            "must_have": [
                {"skill": "Python", "required_years": None},
                "SQL",
            ],
            "good_to_have": [{"skill": "Docker", "required_years": None}],
        },
    }
    parsed_resume = {"skills": ["Python", "SQL"], "total_years": 5}

    result = application_ai_service.call_match_resume_jd(
        application_id=uuid4(),
        job_id=uuid4(),
        parsed_jd=parsed_jd,
        parsed_resume=parsed_resume,
    )

    assert result["status"] == "success"
    assert len(client.calls) == 1
    _, payload = client.calls[0]
    assert payload["parsed_jd"] == parsed_jd
    assert payload["parsed_resume"] == parsed_resume
