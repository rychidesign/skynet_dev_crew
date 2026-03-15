import os
from crewai import Agent
from models import get_llm
from tools.file_reader import create_file_reader
from tools.file_writer import create_file_writer
from tools.list_dir import create_list_dir
from tools.search_content import create_search_content
from tools.image_generator import create_image_generator
from tools.file_size_check import create_file_size_check


def create_coder_agent(project_path: str, output_path: str = ""):
    """Coder (Implementer) — model per models.AGENT_MODELS['coder']."""
    llm = get_llm("coder")
    code_base = output_path or project_path

    return Agent(
        role="Kodér",
        goal=(
            "Implement code exactly according to the Architect's plan. "
            "Write clean, functional, and complete files using the technologies "
            "the project requires."
        ),
        backstory=f"""You are an experienced full-stack developer capable of working
with any tech stack — from simple HTML/CSS through React/Vue/Svelte to backends
in Node.js, Python, Go, or any other language.

Adapt to the project's technologies — read SPECS.md and rules/ to determine
what stack is used. Do not implement anything the project does not require.

You receive clear instructions from the Architect — your job is to implement them.
You write COMPLETE files — never truncate, skip, or use comments like
"... rest of code".

CRITICAL FILE SIZE LIMITS (from rules/do-not.md and rules/general.md):
- Backend files (.py, .go, .rs, .java, .rb, .php): MAX 200 LINES
- Frontend files (.tsx, .ts, .jsx, .js, .vue, .svelte, .css): MAX 150 LINES

If your implementation would exceed these limits, you MUST:
1. Split the file into smaller modules
2. Extract helper functions into separate utility files
3. Create separate files for different concerns

BEFORE submitting your code, use file_size_check tool to verify each file
does not exceed the line limit. If it does, refactor immediately.

IMPORTANT: When a task comes back from the Reviewer with a FAIL verdict:
- Carefully read the feedback
- Fix the code based on the criticism
- Try again with the fixes

Rules for file_writer:
- Always provide COMPLETE file content
- If a file is too large, split it into multiple files BEFORE writing
- Never call file_writer with empty content
- Always specify BOTH file_path AND content
- After writing, use file_size_check to verify the file is within limits

You are working on a project in: {project_path}""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        tools=[
            create_file_reader(code_base),
            create_file_writer(code_base),
            create_list_dir(code_base),
            create_search_content(code_base),
            create_image_generator(code_base),
            create_file_size_check(code_base),
        ],
        max_iterations=30,
        max_execution_time=3600,
    )
