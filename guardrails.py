"""
CrewAI Task Guards pro Review Agent.

Každá guardrail funkce vrací Tuple[bool, Any]:
- (True, output) pokud validace projde
- (False, chybová zpráva) pokud validace selhá — CrewAI donutí agenta opravit

Guardraily se spouští sekvenčně:
1. validate_reviewer_verdict_format — kontroluje PASS/FAIL na prvním řádku
2. validate_reviewer_mentions_tools — kontroluje evidence použití nástrojů
"""

from typing import Tuple, Any


def validate_reviewer_verdict_format(result) -> Tuple[bool, Any]:
    """Ověří, že Reviewer output začíná PASS: nebo FAIL:.
    
    Kontroluje POUZE první neprázdný řádek outputu.
    
    Args:
        result: TaskOutput z CrewAI (má atribut .raw)
    
    Returns:
        (True, raw_output) pokud formát je správný
        (False, chybová_zpráva) pokud formát je špatný
    """
    raw = getattr(result, 'raw', None)
    if not raw or not raw.strip():
        return (
            False,
            "⚠️ Tvůj výstup je prázdný. Musíš vrátit review začínající 'PASS:' nebo 'FAIL:'."
        )
    
    first_line = ""
    for line in raw.strip().splitlines():
        stripped = line.strip()
        if stripped:
            first_line = stripped.upper()
            break
    
    if not first_line:
        return (
            False,
            "⚠️ Tvůj výstup je prázdný. Musíš vrátit review začínající 'PASS:' nebo 'FAIL:'."
        )
    
    if first_line.startswith("PASS:") or first_line.startswith("PASS "):
        return (True, raw)
    
    if first_line.startswith("FAIL:") or first_line.startswith("FAIL "):
        return (True, raw)
    
    return (
        False,
        f"⚠️ Tvůj výstup MUSÍ začínat na prvním řádku slovem 'PASS:' nebo 'FAIL:' "
        f"následovaným názvem tasku. Oprav formát a vrať review znovu.\n"
        f"Aktuální první řádek: '{first_line[:80]}'"
    )


def validate_reviewer_mentions_tools(result) -> Tuple[bool, Any]:
    """Ověří, že Reviewer zmínil výsledky z povinných nástrojů.
    
    Hledá evidence, že Reviewer skutečně:
    1. Prozkoumal adresářovou strukturu (list_dir)
    2. Zkontroloval velikosti souborů (directory_size_check / file_size_check)
    
    Args:
        result: TaskOutput z CrewAI (má atribut .raw)
    
    Returns:
        (True, raw_output) pokud evidence existuje
        (False, chybová_zpráva) pokud evidence chybí
    """
    raw = getattr(result, 'raw', None)
    if not raw or not raw.strip():
        return (False, "Výstup je prázdný.")
    
    text_lower = raw.lower()
    
    # Indikátory použití list_dir / directory listing
    dir_indicators = [
        "list_dir",
        "directory listing",
        "soubory v",
        "files in",
        "files in output",
        "file structure",
        "adresářová struktura",
        "directory structure",
        "├──",
        "└──",
        "──",
        "[dir]",
        "[file]",
    ]
    
    # Indikátory použití directory_size_check / file_size_check
    size_indicators = [
        "size_check",
        "directory_size",
        "file_size",
        "lines (max",
        "within size limits",
        "within limits",
        "exceed",
        "řádků",
        "lines",
        "file size",
        "velikost",
        "size limit",
    ]
    
    has_dir_evidence = any(indicator in text_lower for indicator in dir_indicators)
    has_size_evidence = any(indicator in text_lower for indicator in size_indicators)
    
    missing = []
    if not has_dir_evidence:
        missing.append("list_dir (musíš prozkoumat adresářovou strukturu)")
    if not has_size_evidence:
        missing.append("directory_size_check (musíš zkontrolovat velikosti souborů)")
    
    if missing:
        return (
            False,
            "⚠️ Tvůj review NEOBSAHUJE důkazy o použití povinných nástrojů:\n"
            + "\n".join(f"  - {m}" for m in missing) + "\n\n"
            "POVINNÉ KROKY před vydáním verdiktu:\n"
            "1. Použij list_dir na output adresář\n"
            "2. Použij directory_size_check na output adresář\n"
            "3. Přečti klíčové soubory pomocí file_reader\n"
            "Pak vrať review znovu s výsledky těchto kontrol."
        )
    
    return (True, raw)