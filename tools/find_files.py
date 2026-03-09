import os
from pathlib import Path
from typing import ClassVar, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class FindFilesInput(BaseModel):
    pattern: str = Field(
        description=(
            "Glob pattern to match filenames. Examples: '*.tsx', '*.ts', "
            "'**/auth*.ts', '**/components/**/*.tsx', 'package.json'."
        )
    )
    search_from: str = Field(
        default="",
        description=(
            "Subdirectory to start the search from (relative to project root). "
            "Empty string '' means search from project root."
        ),
    )


class FindFilesTool(BaseTool):
    name: str = "find_files"
    description: str = (
        "Find files matching a glob pattern recursively within the project. "
        "Use to locate files when you don't know their exact path. "
        "Examples: find all '*.tsx' files, find '**/auth*.ts', find 'package.json'. "
        "Returns a list of matching file paths."
    )
    args_schema: Type[BaseModel] = FindFilesInput

    project_path: Optional[str] = None

    MAX_RESULTS: ClassVar[int] = 100

    def _run(self, pattern: str, search_from: str = "") -> str:
        root = self._resolve_search_root(search_from)
        if root is None:
            return (
                f"❌ Adresář '{search_from}' neexistuje v projektu.\n"
                f"   Tip: Ponech search_from prázdný pro hledání od project root."
            )

        try:
            # Strip leading **/ if present — rglob adds it automatically
            clean_pattern = pattern.lstrip("/")
            matches = list(Path(root).rglob(clean_pattern))
        except Exception as e:
            return f"❌ Chyba při hledání: {e}"

        # Filter out directories, only files
        file_matches = [p for p in matches if p.is_file()]

        if not file_matches:
            return (
                f"🔍 Žádné soubory nenalezeny pro vzor '{pattern}' v '{root}'.\n"
                f"   Zkus obecnější vzor nebo jiný search_from."
            )

        # Sort by path for readability
        file_matches.sort()
        truncated = file_matches[: self.MAX_RESULTS]

        lines = [f"🔍 Nalezeno {len(file_matches)} souborů pro '{pattern}':"]
        if len(file_matches) > self.MAX_RESULTS:
            lines[0] += f" (zobrazeno prvních {self.MAX_RESULTS})"

        for path in truncated:
            # Show path relative to project_path for readability
            display = self._relative(path)
            try:
                size = path.stat().st_size
                lines.append(f"  {display}  ({size:,} B)")
            except OSError:
                lines.append(f"  {display}")

        return "\n".join(lines)

    def _resolve_search_root(self, search_from: str) -> Optional[str]:
        """Return absolute search root, always scoped within project_path."""
        base = self.project_path or os.getcwd()

        if not search_from or search_from in (".", ""):
            return base if os.path.isdir(base) else None

        candidate = os.path.realpath(os.path.join(base, search_from))
        base_real = os.path.realpath(base)

        # Security: prevent traversal outside project
        if not candidate.startswith(base_real):
            return None

        return candidate if os.path.isdir(candidate) else None

    def _relative(self, path: Path) -> str:
        """Return path relative to project_path if possible."""
        if self.project_path:
            try:
                return str(path.relative_to(self.project_path))
            except ValueError:
                pass
        return str(path)


def create_find_files(project_path: str = "") -> FindFilesTool:
    """Factory that creates a FindFilesTool bound to a specific project."""
    return FindFilesTool(project_path=project_path)


FindFiles = FindFilesTool()
