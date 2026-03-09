import os
import subprocess
from typing import ClassVar, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class LintCheckInput(BaseModel):
    command: str = Field(
        default="npx tsc --noEmit",
        description=(
            "Lint or type-check command to run. "
            "Allowed: 'npx tsc --noEmit', 'npm run lint', 'npm run test'."
        ),
    )


class LintCheckTool(BaseTool):
    name: str = "lint_check"
    description: str = (
        "Run TypeScript type-check or lint on the project output directory. "
        "Returns compiler/lint errors if any. "
        "Use to objectively verify code correctness before issuing PASS/FAIL verdict."
    )
    args_schema: Type[BaseModel] = LintCheckInput

    project_path: Optional[str] = None

    ALLOWED_COMMANDS: ClassVar[list[str]] = [
        "npx tsc --noEmit",
        "npm run lint",
        "npm run test",
    ]

    TIMEOUT: ClassVar[int] = 60

    def _run(self, command: str = "npx tsc --noEmit") -> str:
        if command not in self.ALLOWED_COMMANDS:
            return (
                f"❌ Command '{command}' není povolený.\n"
                f"   Povolené: {', '.join(self.ALLOWED_COMMANDS)}"
            )

        cwd = self.project_path or os.getcwd()

        try:
            result = subprocess.run(
                command.split(),
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )
            output = (result.stdout + "\n" + result.stderr).strip()

            if result.returncode == 0:
                return f"✅ Žádné chyby. Command: '{command}'"

            if len(output) > 3000:
                output = output[:3000] + "\n... (zkráceno)"

            return (
                f"⚠️ Nalezeny chyby (exit code {result.returncode}):\n"
                f"Command: {command}\n\n{output}"
            )

        except subprocess.TimeoutExpired:
            return f"❌ Timeout po {self.TIMEOUT}s pro '{command}'."
        except FileNotFoundError:
            return f"❌ Command '{command.split()[0]}' nenalezen. Je nainstalován?"
        except Exception as e:
            return f"❌ Chyba při spuštění: {e}"


def create_lint_check(project_path: str = "") -> LintCheckTool:
    """Factory that creates a LintCheckTool bound to a specific project."""
    return LintCheckTool(project_path=project_path)
