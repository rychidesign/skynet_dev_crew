import os
from crewai import Agent, LLM
from tools.file_reader import create_file_reader
from tools.file_writer import create_file_writer
from tools.list_dir import create_list_dir
from tools.search_content import create_search_content


def create_coder_agent(project_path: str, output_path: str = ""):
    """Coder (Implementer) — Gemini 2.5 Flash.

    Receives detailed instructions from Architect and writes actual code:
    React components, hooks, API routes, Supabase queries, config files.
    """
    llm = LLM(
        model="gemini/gemini-2.5-flash",
        api_key=os.getenv("GOOGLE_API_KEY"),
        max_tokens=8192,
    )

    # Use output_path for reading/writing code (project_path for specs/docs)
    code_base = output_path or project_path

    return Agent(
        role="Kodér",
        goal=(
            "Implementovat kód přesně podle plánu od Architekta. "
            "Psát čisté, funkční React komponenty, hooky, services, "
            "Supabase queries a konfigurační soubory."
        ),
        backstory=f"""Jsi zkušený full-stack vývojář se specializací na
TypeScript, React, Tailwind CSS, Supabase a Vite.

Dostáváš jasné zadání od Architekta — tvým úkolem je ho implementovat.
Píšeš KOMPLETNÍ soubory — nikdy nezkracuješ, nevynecháváš a nepoužíváš
komentáře typu "... rest of code".

DŮLEŽITÉ: Když se task vrátí od Reviewera s FAIL verdictem:
- Pečlivě si přečti feedback co tě kritizuje
- Uprav kód na základě kritiky
- Zkus znovu s opravami
- Supervisor automaticky spustí retry (max 3× v jedné session)

Pravidla pro file_writer:
- Vždy poskytni KOMPLETNÍ obsah souboru
- Pokud je soubor příliš velký (SQL migrace), rozděl ho do více souborů
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
            create_search_content(code_base),
        ],
        max_iterations=30,
        max_execution_time=3600,  # 1 hour (increased from 600s to handle long LLM calls with retries)
    )
