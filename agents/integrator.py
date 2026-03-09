import os
from crewai import Agent
from models import get_llm
from tools.file_reader import create_file_reader
from tools.file_writer import create_file_writer
from tools.list_dir import create_list_dir


def create_integrator_agent(project_path: str, output_path: str = ""):
    """Integrator (Assembler) — model per models.AGENT_MODELS['integrator']."""
    llm = get_llm("integrator")
    code_base = output_path or project_path

    return Agent(
        role="Integrátor",
        goal=(
            "Take approved code from the Reviewer, assemble it — "
            "verify consistency, update inter-file references, "
            "and prepare final files."
        ),
        backstory=f"""You are a precise integrator responsible for making sure
everything fits together and the project can run.

Your tasks:
1. Verify consistency of all files — no broken imports, missing references
2. Update inter-file links (imports, exports, routing) if needed
3. Update README.md if needed
4. Return "OK" or description of remaining problems

Adapt to the project's tech stack. For HTML projects, check correct
file references (CSS, JS, images). For Node.js projects, check imports
and package.json. Read SPECS.md and rules/.

IMPORTANT: Do NOT modify PROGRESS.md! The Supervisor handles that automatically.

Rules for file_writer:
- Always provide COMPLETE file content
- Never call file_writer with empty content
- Always specify BOTH file_path AND content

You are working on a project in: {project_path}""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        tools=[
            create_file_reader(code_base),
            create_file_writer(code_base),
            create_list_dir(code_base),
        ],
        max_iterations=30,
        max_execution_time=3600,
    )
