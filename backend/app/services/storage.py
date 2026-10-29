from pathlib import Path
from uuid import UUID


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, object_id: UUID, filename: str, content: bytes) -> Path:
        safe_name = Path(filename).name
        destination = self.root / f"{object_id}_{safe_name}"
        destination.write_bytes(content)
        destination.chmod(0o600)
        return destination

    def delete(self, path: Path) -> None:
        path.unlink(missing_ok=True)

