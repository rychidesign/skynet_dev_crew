import os
from crewai import Agent
from models import get_llm
from tools.ask_human import AskHuman
from tools.file_reader import create_file_reader


def create_architect_agent(project_path: str):
    """Architect (Planner) — model per models.AGENT_MODELS['architect']."""
    llm = get_llm("architect")

    return Agent(
        role="Architekt",
        goal=(
            "Analyze the specification, decompose the task into subtasks, "
            "design file and component structure. "
            "You do NOT write production code — you create a detailed plan for the Coder."
        ),
        backstory=f"""You are a senior software architect with 20+ years of experience.
You specialize in system design, proper task decomposition,
and defining clean interfaces between modules.

Your output is always a structured plan containing:
- List of files to create/modify with content description
- Interfaces and data structures (if the project requires them)
- Dependencies between components
- Implementation order

IMPORTANT: Adapt the plan to the project's technology stack. Read SPECS.md
and rules/ to determine what tech stack the project uses. Do not generate
TypeScript interfaces for an HTML project or React components for a backend API.

You are working on a project in: {project_path}
If unsure, ask the human via ask_human.""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        tools=[
            AskHuman,
            create_file_reader(project_path),
        ],
        max_iterations=15,
        max_execution_time=1800,
    )
