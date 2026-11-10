from dataclasses import dataclass

@dataclass(frozen=True)
class Project:
    id: int
    name: str
    source_path: str
    status: str
    created_at: str
    duration: float
    metadata: str
