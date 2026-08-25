import json
from typing import Any, Union, List


def clean_llm_json_response(raw_response: str) -> str:
    """Strip markdown code fences from LLM output before JSON parsing.

    Many LLMs wrap their JSON output in ```json ... ``` blocks despite
    being told not to. This utility normalizes the raw string so
    json.loads() can consume it cleanly.
    """
    raw = raw_response.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


def parse_llm_json(raw_response: str) -> Union[dict, list]:
    """Clean and parse LLM response into a Python dict or list.

    Raises json.JSONDecodeError if the cleaned output is not valid JSON.
    """
    cleaned = clean_llm_json_response(raw_response)
    return json.loads(cleaned)
