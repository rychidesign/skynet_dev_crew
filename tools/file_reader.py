import os
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class FileReaderInput(BaseModel):
    file_path: str = Field(
        description=(
            "Path to the file to read. Can be a full relative path from cwd "
            "(e.g. 'projects/taskmanager/specs/technical.md') or a short path "
            "that will be resolved against the project directory automatically."
        )
    )


class FileReaderTool(BaseTool):
    name: str = "file_reader"
    description: str = (
        "Read the content of a text file. Provide 'file_path' as the path to the file. "
        "The tool will first try the exact path, then look inside the project directory."
    )
    args_schema: Type[BaseModel] = FileReaderInput

    project_path: Optional[str] = None

    def _run(self, file_path: str) -> str:
        """Read content from a file, resolving against project_path if needed."""
        resolved = self._resolve_path(file_path)
        if resolved is None:
            candidates = [file_path]
            if self.project_path:
                candidates.append(os.path.join(self.project_path, file_path))
            return (
                f"❌ Soubor '{file_path}' neexistuje.\n"
                f"   Hledané cesty: {candidates}\n"
                f"   Tip: Použij plnou relativní cestu, např. '{self.project_path or 'projects/<name>'}/specs/soubor.md'"
            )

        with open(resolved, "r", encoding="utf-8") as f:
            content = f.read()

        return f"--- {resolved} ---\n{content}\n--- KONEC ---"

    def _resolve_path(self, file_path: str) -> Optional[str]:
        """Try exact path first, then relative to project_path."""
        if os.path.isfile(file_path):
            return file_path

        if self.project_path:
            candidate = os.path.join(self.project_path, file_path)
            if os.path.isfile(candidate):
                return candidate

        return None


def create_file_reader(project_path: str = "") -> FileReaderTool:
    """Factory that creates a FileReaderTool bound to a specific project."""
    return FileReaderTool(project_path=project_path)


FileReader = FileReaderTool()
