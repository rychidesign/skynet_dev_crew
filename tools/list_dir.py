import os
from typing import ClassVar, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ListDirInput(BaseModel):
    directory: str = Field(
        description=(
            "Directory path to list. Can be relative to project root "
            "(e.g. 'src/components') or empty string '' to list the project root."
        )
    )
    recursive: bool = Field(
        default=False,
        description="List contents recursively (max depth 3). Default is flat listing.",
    )


class ListDirTool(BaseTool):
    name: str = "list_dir"
    description: str = (
        "List files and subdirectories in a directory. "
        "Use to explore project structure and discover file locations. "
        "Provide 'directory' as path relative to project root. "
        "Use recursive=true to see full subtree (max depth 3)."
    )
    args_schema: Type[BaseModel] = ListDirInput

    project_path: Optional[str] = None

    MAX_DEPTH: ClassVar[int] = 3
    MAX_ENTRIES: ClassVar[int] = 200

    def _run(self, directory: str, recursive: bool = False) -> str:
        resolved = self._resolve_dir(directory)
        if resolved is None:
            candidates = [directory]
            if self.project_path:
                candidates.append(os.path.join(self.project_path, directory))
            return (
                f"❌ Adresář '{directory}' neexistuje.\n"
                f"   Hledané cesty: {candidates}\n"
                f"   Tip: Použij '' pro výpis project root nebo cestu relativní k projektu."
            )

        if recursive:
            return self._tree(resolved, max_depth=self.MAX_DEPTH)
        return self._flat(resolved)

    def _resolve_dir(self, directory: str) -> Optional[str]:
        """Resolve directory path, always scoped to project_path."""
        if not directory or directory in (".", ""):
            root = self.project_path or os.getcwd()
            return root if os.path.isdir(root) else None

        # Always resolve relative to project_path for security
        if self.project_path:
            candidate = os.path.join(self.project_path, directory)
            # Prevent path traversal outside project_path
            candidate = os.path.realpath(candidate)
            root = os.path.realpath(self.project_path)
            if candidate.startswith(root) and os.path.isdir(candidate):
                return candidate

        # Fallback: exact path if it exists (and still under project root)
        if os.path.isdir(directory):
            return directory

        return None

    def _flat(self, path: str) -> str:
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return f"❌ Přístup odepřen: {path}"

        lines = [f"📁 {path}/"]
        count = 0
        for entry in entries:
            if count >= self.MAX_ENTRIES:
                lines.append(f"   ... (výpis zkrácen, více než {self.MAX_ENTRIES} položek)")
                break
            prefix = "  [DIR] " if entry.is_dir() else "  [FILE]"
            size = ""
            if entry.is_file():
                try:
                    size = f"  ({entry.stat().st_size:,} B)"
                except OSError:
                    pass
            lines.append(f"{prefix} {entry.name}{size}")
            count += 1

        lines.append(f"\n  Celkem: {count} položek")
        return "\n".join(lines)

    def _tree(self, root: str, max_depth: int = 3) -> str:
        lines = [f"📁 {root}/"]
        total = [0]

        def _walk(path: str, prefix: str, depth: int) -> None:
            if depth > max_depth:
                return
            try:
                entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name))
            except PermissionError:
                lines.append(f"{prefix}[přístup odepřen]")
                return

            for i, entry in enumerate(entries):
                if total[0] >= self.MAX_ENTRIES:
                    lines.append(f"{prefix}... (zkráceno)")
                    return
                connector = "└── " if i == len(entries) - 1 else "├── "
                if entry.is_dir():
                    lines.append(f"{prefix}{connector}[DIR] {entry.name}/")
                    extension = "    " if i == len(entries) - 1 else "│   "
                    _walk(entry.path, prefix + extension, depth + 1)
                else:
                    try:
                        size = f"  ({entry.stat().st_size:,} B)"
                    except OSError:
                        size = ""
                    lines.append(f"{prefix}{connector}{entry.name}{size}")
                    total[0] += 1

        _walk(root, "", 1)
        return "\n".join(lines)


def create_list_dir(project_path: str = "") -> ListDirTool:
    """Factory that creates a ListDirTool bound to a specific project."""
    return ListDirTool(project_path=project_path)


ListDir = ListDirTool()
