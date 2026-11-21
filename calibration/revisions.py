from dataclasses import dataclass
from uuid import uuid4

from calibration.scenarios import ScenarioBatch


@dataclass(frozen=True, slots=True)
class RevisionRef:
    strip_id: str
    revision_id: str

    def __post_init__(self) -> None:
        for value in (self.strip_id, self.revision_id):
            if not isinstance(value, str) or not value.strip():
                raise ValueError('revision and strip references must be nonempty strings')


@dataclass(frozen=True, slots=True)
class ScenarioRevision:
    ref: RevisionRef
    previous: RevisionRef | None
    batch: ScenarioBatch


def build_revision(strip_id: str, batch: ScenarioBatch, previous: RevisionRef | None) -> ScenarioRevision:
    if previous is not None and (not isinstance(previous, RevisionRef) or previous.strip_id != strip_id):
        raise ValueError('the predecessor must be a revision of this strip')
    return ScenarioRevision(RevisionRef(strip_id, f'revision-{uuid4().hex}'), previous, batch)
