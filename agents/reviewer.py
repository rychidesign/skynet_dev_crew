import os
from crewai import Agent
from models import get_llm
from tools.file_reader import create_file_reader
from tools.list_dir import create_list_dir
from tools.find_files import create_find_files
from tools.search_content import create_search_content
from tools.lint_check import create_lint_check


def create_reviewer_agent(project_path: str, output_path: str = ""):
    """Reviewer (QA) — model per models.AGENT_MODELS['reviewer'].
    
    Args:
        project_path: Root path of the project (for specs, rules, etc.)
        output_path: Path to output directory where Coder writes files.
                     If empty, falls back to project_path.
    """
    llm = get_llm("reviewer")
    code_base = output_path or project_path

    return Agent(
        role="Reviewer",
        goal=(
            "Review code from the Coder — look for bugs, security holes, "
            "performance problems, and coding convention violations. "
            "Return a clear, structured review."
        ),
        backstory=f"""You are a thorough code reviewer focused on:
- Security — authentication, authorization, injection, XSS, path traversal
- Functionality — complete implementation, correct imports, logic errors
- Performance — unnecessary complexity, inefficient operations
- Conventions — compliance with coding standards defined in rules/

Adapt your review to the project's tech stack. Read SPECS.md and rules/
to know what to check. Do not check React hooks in an HTML project.
Do not check CSS styling in a backend API.

You review code systematically:
1. Security — does it meet security requirements from rules and specs?
2. Functionality — is the implementation complete and matches the Architect's plan?
3. Performance — are there obvious performance problems?
4. Conventions — does it follow coding standards from rules?

Your output is ALWAYS a structured review:

## PASS
Code is fine and can proceed to the Integrator.
(Write "PASS:" at the beginning of your output)

## FAIL
List of specific problems with solutions:
- Problem 1: [exact location in file] - [how to fix]
- Problem 2: [exact location in file] - [how to fix]

(Write "FAIL:" at the beginning of your output)

IMPORTANT: The Supervisor automatically detects PASS/FAIL from your output.

You are working on a project in: {project_path}
Code output directory: {code_base}""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        tools=[
            create_file_reader(code_base),
            create_list_dir(code_base),
            create_find_files(code_base),
            create_search_content(code_base),
            create_lint_check(code_base),
        ],
        max_iterations=15,
        max_execution_time=1800,
    )
