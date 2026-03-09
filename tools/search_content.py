import os
import re
from pathlib import Path
from typing import ClassVar, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class SearchContentInput(BaseModel):
    query: str = Field(
        description=(
            "String or regex pattern to search for in file contents. "
            "Examples: 'useAuth', 'import.*supabase', 'TODO:', 'function handleSubmit'."
        )
    )
    file_pattern: str = Field(
        default="*",
        description=(
            "Glob pattern to filter which files to search. "
            "Examples: '*.ts', '*.tsx', '*.md', '*.json'. Default '*' searches all text files."
        ),
    )
    case_sensitive: bool = Field(
        default=False,
        description="Whether the search is case-sensitive. Default is case-insensitive.",
    )


class SearchContentTool(BaseTool):
    name: str = "search_content"
    description: str = (
        "Search for a string or regex pattern across files in the project. "
        "Returns matching file paths with the matching lines and surrounding context. "
        "Use to find where a function/component/variable is defined or used. "
        "Provide 'file_pattern' to narrow search (e.g. '*.tsx' for React components only)."
    )
    args_schema: Type[BaseModel] = SearchContentInput

    project_path: Optional[str] = None

    MAX_MATCHES: ClassVar[int] = 20
    CONTEXT_LINES: ClassVar[int] = 2
    MAX_FILE_SIZE: ClassVar[int] = 512 * 1024  # 512 KB — skip binary/huge files

    BINARY_EXTENSIONS: ClassVar[set] = {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
        ".woff", ".woff2", ".ttf", ".eot",
        ".zip", ".tar", ".gz", ".lock",
        ".map", ".bin", ".exe", ".dll",
    }

    def _run(self, query: str, file_pattern: str = "*", case_sensitive: bool = False) -> str:
        root = self.project_path or os.getcwd()

        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(query, flags)
        except re.error as e:
            return f"❌ Neplatný regex: '{query}' — {e}"

        candidate_files = list(Path(root).rglob(file_pattern))
        candidate_files = [f for f in candidate_files if f.is_file()]

        results: list[str] = []
        files_searched = 0
        files_skipped = 0

        for filepath in sorted(candidate_files):
            if len(results) >= self.MAX_MATCHES:
                break

            if filepath.suffix.lower() in self.BINARY_EXTENSIONS:
                files_skipped += 1
                continue

            try:
                if filepath.stat().st_size > self.MAX_FILE_SIZE:
                    files_skipped += 1
                    continue
                text = filepath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                files_skipped += 1
                continue

            files_searched += 1
            lines = text.splitlines()
            file_hits: list[str] = []

            for line_no, line in enumerate(lines):
                if pattern.search(line):
                    # Collect context lines
                    start = max(0, line_no - self.CONTEXT_LINES)
                    end = min(len(lines), line_no + self.CONTEXT_LINES + 1)
                    block = []
                    for i in range(start, end):
                        marker = ">>>" if i == line_no else "   "
                        block.append(f"  {marker} {i + 1:4d} | {lines[i]}")
                    file_hits.append("\n".join(block))

                    if len(results) + len(file_hits) >= self.MAX_MATCHES:
                        break

            if file_hits:
                display_path = self._relative(filepath)
                results.append(
                    f"📄 {display_path}\n" + "\n  ---\n".join(file_hits)
                )

        if not results:
            return (
                f"🔍 Vzor '{query}' nenalezen v souborech '{file_pattern}' "
                f"(prohledáno {files_searched} souborů, přeskočeno {files_skipped})."
            )

        header = (
            f"🔍 Nalezeno {len(results)} shod pro '{query}' "
            f"(prohledáno {files_searched} souborů, přeskočeno {files_skipped}):"
        )
        if len(results) >= self.MAX_MATCHES:
            header += f" — zobrazeno max {self.MAX_MATCHES}, zpřesni dotaz pro více."

        return header + "\n\n" + "\n\n".join(results)

    def _relative(self, path: Path) -> str:
        """Return path relative to project_path if possible."""
        if self.project_path:
            try:
                return str(path.relative_to(self.project_path))
            except ValueError:
                pass
        return str(path)


def create_search_content(project_path: str = "") -> SearchContentTool:
    """Factory that creates a SearchContentTool bound to a specific project."""
    return SearchContentTool(project_path=project_path)


SearchContent = SearchContentTool()
