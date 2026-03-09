import os
from typing import ClassVar, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class FileWriterInput(BaseModel):
    file_path: str = Field(
        default="",
        description=(
            "Path to the file to write, relative to the project root. "
            "Examples: 'src/components/Button.tsx', 'supabase/migrations/001_schema.sql'"
        ),
    )
    content: str = Field(
        default="",
        description=(
            "The COMPLETE file content to write. "
            "Must contain the full file — do NOT truncate or summarize. "
            "Write the entire content in one call."
        ),
    )


class FileWriterTool(BaseTool):
    name: str = "file_writer"
    description: str = (
        "Write a file to disk. Provide TWO arguments:\n"
        "  file_path: path relative to project root (e.g. 'src/App.tsx')\n"
        "  content: the COMPLETE file content (do not truncate)\n"
        "Parent directories are created automatically.\n"
        "IMPORTANT: Always include both file_path AND content. "
        "If the file is large, write it completely — do not split across calls."
    )
    args_schema: Type[BaseModel] = FileWriterInput

    project_path: Optional[str] = None
    MAX_FILE_SIZE: ClassVar[int] = 50_000

    def _run(self, file_path: str = "", content: str = "") -> str:
        """Write content to file_path, creating parent dirs as needed."""
        if not file_path and not content:
            return (
                "❌ Error: both 'file_path' and 'content' are empty. "
                "Provide file_path (e.g. 'src/App.tsx') and content (the full file text)."
            )

        if not file_path:
            return (
                "❌ Error: 'file_path' is missing. "
                "Provide the path as the first argument, e.g. 'src/App.tsx'."
            )

        if not content:
            return (
                f"❌ Error: 'content' is empty for '{file_path}'. "
                "Provide the complete file content as the second argument. "
                "Do NOT call file_writer without content."
            )

        if len(content) > self.MAX_FILE_SIZE:
            return (
                f"❌ Content příliš velký ({len(content):,} znaků, max {self.MAX_FILE_SIZE:,}). "
                f"Rozděl soubor na menší části a zapiš každou zvlášť."
            )

        resolved = self._resolve_path(file_path.strip())

        parent = os.path.dirname(resolved)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)

        lines = content.count("\n") + 1
        return f"✅ Written '{resolved}' ({lines} lines)."

    def _resolve_path(self, file_path: str) -> str:
        """Prepend project_path, stripping duplicate output/ prefix if present."""
        if not self.project_path:
            return file_path
        if file_path.startswith(self.project_path):
            return file_path

        rel = file_path
        if self.project_path.endswith("/output") or self.project_path.endswith("\\output"):
            output_prefix = os.path.basename(self.project_path) + "/"
            while rel.startswith(output_prefix):
                rel = rel[len(output_prefix):]

        return os.path.join(self.project_path, rel)


def create_file_writer(project_path: str = "") -> FileWriterTool:
    """Factory that creates a FileWriterTool bound to a specific project."""
    return FileWriterTool(project_path=project_path)


FileWriter = FileWriterTool()
