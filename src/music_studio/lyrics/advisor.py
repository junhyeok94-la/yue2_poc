from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class Suggestion:
    id: str
    type: str
    section_id: str
    line_index: int
    original: str
    suggested: str
    reason: str
    source_revision: str
    severity: str = 'info'

class LyricsAdvisor(Protocol):
    def review_section(self, section, context) -> list[Suggestion]: ...
    def suggest_lines(self, section, context) -> list[Suggestion]: ...
    def review_song(self, song) -> list[Suggestion]: ...
