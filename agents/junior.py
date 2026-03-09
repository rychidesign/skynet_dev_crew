import os
from crewai import Agent, LLM
from tools.ask_human import AskHuman
from tools.file_reader import create_file_reader
from tools.file_writer import create_file_writer


def create_junior_agent(project_path: str):
    """Create the Junior developer agent."""

    llm = LLM(model="gemini/gemini-2.5-flash", api_key=os.getenv("GOOGLE_API_KEY"))

    return Agent(
        role="Junior vývojář",
        goal="Dokončit testy, dokumentaci a drobné úpravy kódu",
        backstory=f"""
        Jsi mladý, nadšený vývojář, který se snaží učit a zlepšovat.
        Pečlivě píšeš testy a dokumentaci.
        Jsi zodpovědný za kvalitu a detaily.
        
        Pracuješ na projektu v adresáři: {project_path}
        Pokud si nejsi jistý něčím, neboj se zeptat zkušenějšího kolegy (kodéra)
        nebo člověka.
        """,
        verbose=True,
        allow_delegation=False,
        llm=llm,
        tools=[AskHuman, create_file_reader(project_path), create_file_writer(project_path)],
        max_iterations=30,
    )
