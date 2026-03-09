import os
from crewai import Agent, LLM
from tools.ask_human import AskHuman
from tools.file_reader import create_file_reader


def create_architect_agent(project_path: str):
    """Architect (Planner) — Claude Sonnet 4.6.

    Analyzes specs, breaks tasks into subtasks, designs file/component
    structure, defines interfaces and types. Does NOT write production code.
    """
    llm = LLM(
        model="anthropic/claude-sonnet-4-6",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        max_tokens=4096,
    )

    return Agent(
        role="Architekt",
        goal=(
            "Analyzovat specifikaci, rozložit úkol na subtasky, "
            "navrhnout strukturu souborů a komponent, definovat interfaces a typy. "
            "Nepíšeš produkční kód — vytváříš detailní plán pro Kodéra."
        ),
        backstory=f"""Jsi senior software architect s 20+ lety zkušeností.
Specializuješ se na návrh škálovatelných systémů, správnou dekompozici úkolů
a definici čistých rozhraní mezi moduly.

Tvůj výstup je vždy strukturovaný plán obsahující:
- Seznam souborů k vytvoření/úpravě s popisem obsahu
- TypeScript interfaces a typy
- Závislosti mezi komponentami
- Pořadí implementace

Pracuješ na projektu v: {project_path}
Pokud si nejsi jistý, zeptej se člověka přes ask_human.""",
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
