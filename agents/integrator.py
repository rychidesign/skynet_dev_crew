import os
from crewai import Agent, LLM
from tools.file_reader import create_file_reader
from tools.file_writer import create_file_writer
from tools.list_dir import create_list_dir


def create_integrator_agent(project_path: str, output_path: str = ""):
    """Integrator (Assembler) — Gemini 2.5 Flash.

    Takes approved code from Reviewer, assembles it: updates imports,
    routing, Supabase migrations, and verifies overall consistency.
    
    NOTE: Does NOT modify PROGRESS.md — Supervisor handles that automatically
    based on Reviewer's verdict.
    """
    llm = LLM(
        model="gemini/gemini-2.5-flash",
        api_key=os.getenv("GOOGLE_API_KEY"),
        max_tokens=16384,
    )

    # Use output_path for reading/writing code (project_path for specs/docs)
    code_base = output_path or project_path

    return Agent(
        role="Integrátor",
        goal=(
            "Vzít schválený kód od Reviewera, složit ho dohromady — "
            "aktualizovat importy, routing, Supabase migrace, "
            "ověřit konzistenci a připravit final soubory."
        ),
        backstory=f"""Jsi precizní integrátor zodpovědný za to, aby vše
do sebe zapadalo a projekt šel spustit.

Tvoje úkoly:
1. Aktualizuj importy a barrel exporty (index.ts soubory)
2. Aktualizuj routing pokud je potřeba
3. Ověř konzistenci všech souborů — žádné broken importy, circular dependencies
4. Vytvoř/aktualizuj README.md
5. Vrať "OK" nebo popis zbývajících problémů

DŮLEŽITÉ: NEMĚŇ PROGRESS.md! To dělá Supervisor automaticky na základě
Reviewerova verdiktu. Tvoje jediná práce je konečná montáž a ověření.

Pravidla pro file_writer:
- Vždy poskytni KOMPLETNÍ obsah souboru
- Nikdy nevolej file_writer s prázdným content
- Vždy uveď BOTH file_path AND content

Pracuješ na projektu v: {project_path}""",
        verbose=True,
        allow_delegation=False,
        llm=llm,
        tools=[
            create_file_reader(code_base),
            create_file_writer(code_base),
            create_list_dir(code_base),
        ],
        max_iterations=30,
        max_execution_time=3600,  # 1 hour (increased from 600s to handle long LLM calls with retries)
    )
