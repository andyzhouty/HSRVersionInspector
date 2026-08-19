"""Format-neutral models produced by version comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JsonChange:
    path: str
    before: Any
    after: Any


@dataclass(frozen=True)
class ResourceDiff:
    resource_id: str
    status: str
    change_count: int
    changes: tuple[JsonChange, ...]


@dataclass(frozen=True)
class DiffReport:
    version_one: str
    version_two: str
    mode: str
    resources: tuple[ResourceDiff, ...]

    @property
    def changed_resources(self) -> tuple[ResourceDiff, ...]:
        return tuple(
            resource
            for resource in self.resources
            if resource.status in {"changed", "added", "removed"}
        )


@dataclass(frozen=True)
class CharacterChange:
    label: str
    before: str | None
    after: str | None
    kind: str


@dataclass(frozen=True)
class CharacterSectionDiff:
    name: str
    status: str
    changes: tuple[CharacterChange, ...]


@dataclass(frozen=True)
class CharacterDiffReport:
    version_one: str
    version_two: str
    character_id_one: str
    character_id_two: str
    name_one: str
    name_two: str
    sections: tuple[CharacterSectionDiff, ...]

    @property
    def changed_sections(self) -> tuple[CharacterSectionDiff, ...]:
        return tuple(section for section in self.sections if section.status != "unchanged")

@dataclass(frozen=True)
class LightConeChange:
    label: str
    before: str | None
    after: str | None
    kind: str


@dataclass(frozen=True)
class LightConeSectionDiff:
    name: str
    status: str
    changes: tuple[LightConeChange, ...]


@dataclass(frozen=True)
class LightConeDiffReport:
    version_one: str
    version_two: str
    lightcone_id_one: str
    lightcone_id_two: str
    name_one: str
    name_two: str
    sections: tuple[LightConeSectionDiff, ...]

    @property
    def changed_sections(self) -> tuple[LightConeSectionDiff, ...]:
        return tuple(section for section in self.sections if section.status != "unchanged")


@dataclass(frozen=True)
class HighModeChange:
    category: str
    label: str
    before: str | None
    after: str | None
    kind: str
    wave: int | None = None
    subject: str | None = None


@dataclass(frozen=True)
class HighModeSectionDiff:
    name: str
    status: str
    changes: tuple[HighModeChange, ...]


@dataclass(frozen=True)
class HighModeDiffReport:
    version_one: str
    version_two: str
    mode: str
    sections: tuple[HighModeSectionDiff, ...]

    @property
    def changed_sections(self) -> tuple[HighModeSectionDiff, ...]:
        return tuple(section for section in self.sections if section.status != "unchanged")
