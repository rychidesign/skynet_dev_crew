import os
from crewai import Agent
from models import get_llm
from tools.ask_human import AskHuman
from tools.file_reader import create_file_reader
from tools.file_writer import create_file_writer


def create_junior_agent(project_path: str):
    """Junior developer — model per models.AGENT_MODELS['junior']."""
    llm = get_llm("junior")

    return Agent(
        role="Junior vývojář",
        goal="Complete tests, documentation, and minor code adjustments",
        backstory=f"""You are a young, enthusiastic developer eager to learn and improve.
You carefully write tests and documentation. You are responsible for quality and details.

You are working on a project in: {project_path}
If unsure about anything, don't hesitate to ask a more experienced colleague
or the human.""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        tools=[AskHuman, create_file_reader(project_path), create_file_writer(project_path)],
        max_iterations=30,
    )
