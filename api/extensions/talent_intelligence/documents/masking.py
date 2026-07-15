"""Local bilingual PII recognition, stable masking, and independent leak detection."""

import enum
import re
from collections import Counter
from dataclasses import dataclass


class PIIType(enum.StrEnum):
    PERSON = "PERSON"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    ADDRESS = "ADDRESS"
    DOB = "DOB"
    PERSONAL_URL = "PERSONAL_URL"
    LINKEDIN = "LINKEDIN"
    GITHUB = "GITHUB"
    VI_CITIZEN_ID = "VI_CITIZEN_ID"
    PASSPORT = "PASSPORT"


@dataclass(frozen=True)
class PIIEntity:
    kind: PIIType
    value: str
    start: int
    end: int
    confidence: float


@dataclass(frozen=True)
class MaskingResult:
    text: str
    placeholder_map: dict[str, str]
    entity_counts: dict[str, int]
    risk_score: float


@dataclass(frozen=True)
class LeakDetectionResult:
    safe: bool
    high_confidence_count: int
    entity_counts: dict[str, int]
    risk_score: float
    warnings: tuple[str, ...]
    manual_review_required: bool


class LocalPIIRecognizer:
    _PATTERNS: tuple[tuple[PIIType, re.Pattern[str], float], ...] = (
        (PIIType.EMAIL, re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE), 0.99),
        (PIIType.LINKEDIN, re.compile(r"https?://(?:www\.)?linkedin\.com/in/[\w%-]+/?", re.IGNORECASE), 0.98),
        (PIIType.GITHUB, re.compile(r"https?://(?:www\.)?github\.com/[\w.-]+/?", re.IGNORECASE), 0.98),
        (
            PIIType.PERSONAL_URL,
            re.compile(r"https?://(?![^\s]*(?:linkedin|github)\.com)[^\s<>()]+", re.IGNORECASE),
            0.90,
        ),
        (PIIType.PHONE, re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9,10}(?!\d)"), 0.97),
        (PIIType.VI_CITIZEN_ID, re.compile(r"(?<!\d)\d{12}(?!\d)"), 0.98),
        (PIIType.PASSPORT, re.compile(r"(?<![A-Z0-9])[A-Z][0-9]{7,8}(?![A-Z0-9])", re.IGNORECASE), 0.90),
        (
            PIIType.DOB,
            re.compile(r"(?<!\d)(?:0?[1-9]|[12]\d|3[01])[/-](?:0?[1-9]|1[0-2])[/-](?:19|20)\d{2}(?!\d)"),
            0.92,
        ),
        (PIIType.ADDRESS, re.compile(r"(?im)^(?:address|địa chỉ)\s*[:\-]\s*([^\n]{5,160})$"), 0.91),
        (
            PIIType.PERSON,
            re.compile(r"(?im)^(?:full\s*name|name|họ\s*(?:và\s*)?tên)\s*[:\-]\s*((?:[^\W\d_]+\s*){2,6})$"),
            0.88,
        ),
    )

    def recognize(self, text: str) -> list[PIIEntity]:
        entities: list[PIIEntity] = []
        for kind, pattern, confidence in self._PATTERNS:
            for match in pattern.finditer(text):
                group = 1 if match.lastindex else 0
                entities.append(
                    PIIEntity(kind, match.group(group).strip(), match.start(group), match.end(group), confidence)
                )
        return _remove_overlaps(entities)


def _remove_overlaps(entities: list[PIIEntity]) -> list[PIIEntity]:
    result: list[PIIEntity] = []
    for entity in sorted(entities, key=lambda item: (-item.confidence, -(item.end - item.start), item.start)):
        if not any(entity.start < saved.end and saved.start < entity.end for saved in result):
            result.append(entity)
    return sorted(result, key=lambda item: item.start)


class PIIMasker:
    def mask(self, text: str, entities: list[PIIEntity]) -> MaskingResult:
        counters: Counter[PIIType] = Counter()
        value_placeholders: dict[tuple[PIIType, str], str] = {}
        placeholder_map: dict[str, str] = {}
        pieces: list[str] = []
        cursor = 0
        normalized_entities = _remove_overlaps(entities)
        for entity in normalized_entities:
            key = (entity.kind, entity.value.casefold())
            placeholder = value_placeholders.get(key)
            if placeholder is None:
                counters[entity.kind] += 1
                placeholder = f"[{entity.kind.value}_{counters[entity.kind]}]"
                value_placeholders[key] = placeholder
                placeholder_map[placeholder] = entity.value
            pieces.extend((text[cursor : entity.start], placeholder))
            cursor = entity.end
        pieces.append(text[cursor:])
        counts = Counter(entity.kind.value for entity in normalized_entities)
        risk = max((entity.confidence for entity in normalized_entities), default=0.0)
        return MaskingResult("".join(pieces), placeholder_map, dict(counts), risk)


_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"\b[^\s@]+@[^\s@]+\.[A-Za-z]{2,}\b")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+84|0)[\d .-]{9,13}(?!\d)")),
    ("INTERNATIONAL_PHONE", re.compile(r"(?<!\d)\+[1-9](?:[ .-]?\d){7,14}(?!\d)")),
    ("VI_CITIZEN_ID", re.compile(r"(?<!\d)\d{12}(?!\d)")),
    ("PASSPORT", re.compile(r"(?<![A-Z0-9])[A-Z][0-9]{7,8}(?![A-Z0-9])", re.IGNORECASE)),
    ("LINKEDIN", re.compile(r"linkedin\.com/in/", re.IGNORECASE)),
    ("GITHUB", re.compile(r"github\.com/[\w.-]+", re.IGNORECASE)),
    ("PERSONAL_URL", re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)),
    ("ADDRESS", re.compile(r"(?im)^(?:address|địa chỉ)\s*[:\-]\s*[^\n]{5,160}$")),
)


def detect_masked_leaks(text: str) -> LeakDetectionResult:
    counts = {name: len(pattern.findall(text)) for name, pattern in _LEAK_PATTERNS}
    present = {name: count for name, count in counts.items() if count}
    total = sum(present.values())
    return LeakDetectionResult(
        safe=total == 0,
        high_confidence_count=total,
        entity_counts=present,
        risk_score=1.0 if total else 0.0,
        warnings=("high_confidence_pii_remains",) if total else (),
        manual_review_required=total > 0,
    )
