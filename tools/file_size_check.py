"""Tool for checking file size limits (max lines per file)."""
import os
from typing import ClassVar, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class FileSizeCheckInput(BaseModel):
    file_path: str = Field(
        description="Path to the file to check (relative to project root)."
    )


class FileSizeCheckTool(BaseTool):
    name: str = "file_size_check"
    description: str = (
        "Check if a file exceeds the maximum allowed lines. "
        "Backend files: max 200 lines. Frontend files: max 150 lines. "
        "Returns PASS if file is within limits, FAIL with details if exceeded."
    )
    args_schema: Type[BaseModel] = FileSizeCheckInput

    project_path: Optional[str] = None

    # Limits per file type
    BACKEND_MAX_LINES: ClassVar[int] = 200
    FRONTEND_MAX_LINES: ClassVar[int] = 150

    # File extensions
    BACKEND_EXTENSIONS: ClassVar[set] = {'.py', '.go', '.rs', '.java', '.rb', '.php'}
    FRONTEND_EXTENSIONS: ClassVar[set] = {'.tsx', '.ts', '.jsx', '.js', '.vue', '.svelte', '.css', '.scss'}

    def _run(self, file_path: str = "") -> str:
        if not file_path:
            return "❌ No file path provided."

        cwd = self.project_path or os.getcwd()
        full_path = os.path.join(cwd, file_path) if not os.path.isabs(file_path) else file_path

        if not os.path.exists(full_path):
            return f"❌ File not found: {file_path}"

        # Count lines
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = len(f.readlines())
        except Exception as e:
            return f"❌ Error reading file: {e}"

        # Determine limit based on extension
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext in self.BACKEND_EXTENSIONS:
            max_lines = self.BACKEND_MAX_LINES
            file_type = "Backend"
        elif ext in self.FRONTEND_EXTENSIONS:
            max_lines = self.FRONTEND_MAX_LINES
            file_type = "Frontend"
        else:
            # Default to backend limit for unknown extensions
            max_lines = self.BACKEND_MAX_LINES
            file_type = "Unknown (using backend limit)"

        if lines <= max_lines:
            return f"✅ PASS: {file_path} has {lines} lines (max {max_lines} for {file_type})."
        else:
            return (
                f"❌ FAIL: {file_path} has {lines} lines, exceeds {max_lines} line limit for {file_type}.\n"
                f"   Current: {lines} lines\n"
                f"   Maximum: {max_lines} lines\n"
                f"   Exceeded by: {lines - max_lines} lines\n"
                f"   Solution: Split this file into smaller modules or extract helper functions."
            )


class DirectorySizeCheckInput(BaseModel):
    directory: str = Field(
        default="",
        description="Directory to check (relative to project root). Empty checks all files."
    )


class DirectorySizeCheckTool(BaseTool):
    name: str = "directory_size_check"
    description: str = (
        "Check all files in a directory for size limits. "
        "Returns a summary of files that exceed limits."
    )
    args_schema: Type[BaseModel] = DirectorySizeCheckInput

    project_path: Optional[str] = None

    BACKEND_MAX_LINES: ClassVar[int] = 200
    FRONTEND_MAX_LINES: ClassVar[int] = 150
    BACKEND_EXTENSIONS: ClassVar[set] = {'.py', '.go', '.rs', '.java', '.rb', '.php'}
    FRONTEND_EXTENSIONS: ClassVar[set] = {'.tsx', '.ts', '.jsx', '.js', '.vue', '.svelte', '.css', '.scss'}

    def _run(self, directory: str = "") -> str:
        cwd = self.project_path or os.getcwd()
        search_dir = os.path.join(cwd, directory) if directory else cwd

        if not os.path.exists(search_dir):
            return f"❌ Directory not found: {directory}"

        violations = []
        checked_files = 0

        for root, dirs, files in os.walk(search_dir):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {'node_modules', '__pycache__', '.git', 'venv', 'dist', 'build', '.next'}]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in self.BACKEND_EXTENSIONS and ext not in self.FRONTEND_EXTENSIONS:
                    continue

                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = len(f.readlines())
                except Exception:
                    continue

                checked_files += 1

                if ext in self.BACKEND_EXTENSIONS:
                    max_lines = self.BACKEND_MAX_LINES
                    file_type = "Backend"
                else:
                    max_lines = self.FRONTEND_MAX_LINES
                    file_type = "Frontend"

                if lines > max_lines:
                    rel_path = os.path.relpath(file_path, cwd)
                    violations.append({
                        'path': rel_path,
                        'lines': lines,
                        'max': max_lines,
                        'type': file_type
                    })

        if not violations:
            return f"✅ PASS: All {checked_files} files are within size limits."

        result = [f"❌ FAIL: {len(violations)} of {checked_files} files exceed size limits:\n"]
        for v in violations:
            result.append(f"   - {v['path']}: {v['lines']} lines (max {v['max']} for {v['type']})")
        
        result.append("\nSolution: Split large files into smaller modules or extract helper functions.")
        return '\n'.join(result)


def create_file_size_check(project_path: str = "") -> FileSizeCheckTool:
    """Factory that creates a FileSizeCheckTool bound to a specific project."""
    return FileSizeCheckTool(project_path=project_path)


def create_directory_size_check(project_path: str = "") -> DirectorySizeCheckTool:
    """Factory that creates a DirectorySizeCheckTool bound to a specific project."""
    return DirectorySizeCheckTool(project_path=project_path)
