"""Organization request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_FIT_LABELS: list[dict[str, Any]] = [
    {"id": "strong", "name": "Strong", "min_score": 8.0, "max_score": 10.0},
    {"id": "moderate", "name": "Moderate", "min_score": 6.0, "max_score": 7.9},
    {"id": "weak", "name": "Weak", "min_score": 0.0, "max_score": 5.9},
]


class FitLabel(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    min_score: float = Field(ge=0, le=10)
    max_score: float = Field(ge=0, le=10)

    @field_validator("id", "name", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def min_lte_max(self) -> FitLabel:
        if self.min_score > self.max_score:
            raise ValueError("min_score must be less than or equal to max_score")
        return self


class FitLabelsPayload(BaseModel):
    labels: list[FitLabel] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_labels(self) -> FitLabelsPayload:
        ids = [item.id for item in self.labels]
        if len(ids) != len(set(ids)):
            raise ValueError("Fit label ids must be unique")
        names = [item.name.casefold() for item in self.labels]
        if len(names) != len(set(names)):
            raise ValueError("Fit label names must be unique")

        ordered = sorted(self.labels, key=lambda item: (item.min_score, item.max_score))
        for index, current in enumerate(ordered):
            for other in ordered[index + 1 :]:
                if ranges_overlap(
                    current.min_score,
                    current.max_score,
                    other.min_score,
                    other.max_score,
                ):
                    raise ValueError(
                        f"Fit label ranges overlap: '{current.name}' and '{other.name}'"
                    )
        return self


def ranges_overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> bool:
    return a_min <= b_max and b_min <= a_max


def _labels_from_legacy_thresholds(raw: dict[str, Any]) -> list[FitLabel]:
    try:
        strong_min = float(raw.get("strong_min", 8))
        moderate_min = float(raw.get("moderate_min", 6))
    except (TypeError, ValueError):
        return [FitLabel.model_validate(item) for item in DEFAULT_FIT_LABELS]

    if not (0 <= moderate_min < strong_min <= 10):
        return [FitLabel.model_validate(item) for item in DEFAULT_FIT_LABELS]

    moderate_max = max(moderate_min, round(strong_min - 0.1, 1))
    weak_max = max(0.0, round(moderate_min - 0.1, 1))
    return [
        FitLabel(id="strong", name="Strong", min_score=strong_min, max_score=10.0),
        FitLabel(
            id="moderate",
            name="Moderate",
            min_score=moderate_min,
            max_score=moderate_max,
        ),
        FitLabel(id="weak", name="Weak", min_score=0.0, max_score=weak_max),
    ]


def fit_labels_from_settings(settings: dict[str, Any] | None) -> list[FitLabel]:
    settings = settings or {}
    raw_labels = settings.get("fit_labels")
    if isinstance(raw_labels, list) and raw_labels:
        try:
            return FitLabelsPayload(
                labels=[FitLabel.model_validate(item) for item in raw_labels]
            ).labels
        except (TypeError, ValueError):
            pass

    legacy = settings.get("fit_thresholds")
    if isinstance(legacy, dict):
        return _labels_from_legacy_thresholds(legacy)

    return [FitLabel.model_validate(item) for item in DEFAULT_FIT_LABELS]


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    logo_url: str | None = None

    @field_validator("name", "domain", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        domain = value.lower().removesuffix(".ezscreen.io")
        if not domain.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Domain must be alphanumeric (hyphens/underscores allowed)")
        return domain


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    logo_url: str | None = None
    is_active: bool | None = None
    fit_labels: list[FitLabel] | None = Field(default=None, min_length=1, max_length=12)

    @field_validator("name", "domain", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value == "":
            return None
        domain = value.lower().removesuffix(".ezscreen.io")
        if not domain.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Domain must be alphanumeric (hyphens/underscores allowed)")
        return domain

    @field_validator("fit_labels")
    @classmethod
    def validate_fit_labels(cls, value: list[FitLabel] | None) -> list[FitLabel] | None:
        if value is None:
            return None
        return FitLabelsPayload(labels=value).labels


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    domain: str | None
    logo_url: str | None
    is_active: bool
    fit_labels: list[FitLabel] = Field(
        default_factory=lambda: [FitLabel.model_validate(item) for item in DEFAULT_FIT_LABELS]
    )
    created_at: datetime | None = None
    user_count: int = 0
    job_count: int = 0
    application_count: int = 0


class OrganizationDeactivateResponse(BaseModel):
    id: UUID
    is_active: bool
    message: str
