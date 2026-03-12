#!/usr/bin/env python3
"""
Live monitor for multiagent supervisor — no flicker, activity timeline, cost tracking.
Usage: python monitor.py [logfile]
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


def _find_latest_log() -> str:
    """Find the most recently modified .log file in logs/ directory."""
    logs_dir = "logs"
    if not os.path.isdir(logs_dir):
        return "logs/taskmanager.log"
    
    log_files = [
        os.path.join(logs_dir, f) for f in os.listdir(logs_dir)
        if f.endswith(".log")
    ]
    
    if not log_files:
        return "logs/taskmanager.log"
    
    return max(log_files, key=os.path.getmtime)


LOG_FILE = sys.argv[1] if len(sys.argv) > 1 else _find_latest_log()
USAGE_FILE = "logs/usage.json"

# ---------------------------------------------------------------------------
# Multi-instance support for monitor — allow multiple monitors same log file
# ---------------------------------------------------------------------------
# Unlike supervisor (max 1 instance), monitor CAN běž v multiple terminals
# Each monitor instance gets its own unique lock file
_LOCK_FILE = f"/tmp/multiagent_monitor_{os.getpid()}.lock"

def _register_cleanup() -> None:
    """Register cleanup on exit."""
    import atexit
    atexit.register(lambda: os.path.exists(_LOCK_FILE) and os.remove(_LOCK_FILE))

# Just register cleanup, don't prevent multiple instances
_register_cleanup()
with open(_LOCK_FILE, "w") as f:
    f.write(f"{os.getpid()}\n{LOG_FILE}")

# ── ANSI helpers ──────────────────────────────────────────────────────────────
HIDE_CURSOR  = "\033[?25l"
SHOW_CURSOR  = "\033[?25h"
ALT_ENTER    = "\033[?1049h"
ALT_EXIT     = "\033[?1049l"
CLEAR_SCREEN = "\033[2J"
HOME         = "\033[H"
BOLD        = "\033[1m"
DIM         = "\033[2m"
RESET       = "\033[0m"
RED         = "\033[91m"
GREEN       = "\033[92m"
YELLOW      = "\033[93m"
BLUE        = "\033[94m"
MAGENTA     = "\033[95m"
CYAN        = "\033[96m"
WHITE       = "\033[97m"

AGENT_COLOR = {
    "Architekt":  BLUE,
    "Kodér":      GREEN,
    "Reviewer":   MAGENTA,
    "Integrátor": CYAN,
}

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

STUCK_THRESHOLD = 120
ACTIVITY_LINES  = 30


# ── Data model ────────────────────────────────────────────────────────────────
@dataclass
class UsageInfo:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    agents: dict = field(default_factory=dict)
    updated: float = 0.0


@dataclass
class State:
    agent: str = "—"
    phase: str = "Startování..."
    tool: Optional[str] = None
    tool_args: Optional[str] = None
    files_written: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    activity: deque = field(default_factory=lambda: deque(maxlen=ACTIVITY_LINES))  # (text, ansi_color)
    tasks_done: int = 0
    current_task: str = "—"
    last_activity_ts: float = field(default_factory=time.time)
    log_size: int = 0
    usage: UsageInfo = field(default_factory=UsageInfo)
    # Multi-line pattern state (persists across parse_log calls)
    _pending_task_start: bool = False
    _pending_task_done: bool = False


# ── Usage reader ──────────────────────────────────────────────────────────────
def read_usage(path: str) -> UsageInfo:
    info = UsageInfo()
    try:
        with open(path, "r") as f:
            data = json.load(f)
        total = data.get("_total", {})
        info.input_tokens = total.get("input_tokens", 0)
        info.output_tokens = total.get("output_tokens", 0)
        info.cost_usd = total.get("cost_usd", 0.0)
        info.updated = data.get("_updated", 0.0)
        for key, val in data.items():
            if key.startswith("_"):
                continue
            info.agents[key] = val
    except Exception:
        pass
    return info


# ── PROGRESS.md reader ────────────────────────────────────────────────────────
def _find_progress_file() -> Optional[str]:
    log_dir = os.path.dirname(LOG_FILE) or "."
    base = os.path.dirname(log_dir) if os.path.basename(log_dir) == "logs" else log_dir
    for subdir in os.listdir(os.path.join(base, "projects")) if os.path.isdir(os.path.join(base, "projects")) else []:
        for candidate in [
            os.path.join(base, "projects", subdir, "PROGRESS.md"),
            os.path.join(base, "projects", subdir, "specs", "PROGRESS.md"),
        ]:
            if os.path.isfile(candidate):
                return candidate
    return None

PROGRESS_FILE = _find_progress_file()


def read_current_task_from_progress() -> str:
    if not PROGRESS_FILE or not os.path.isfile(PROGRESS_FILE):
        return "—"
    try:
        fallback_current = None
        first_pending = None
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                has_current = "← CURRENT" in s
                has_marker = "**" in s
                if has_current and has_marker:
                    name = s.split("**")[1]
                    if s.startswith("- [ ]"):
                        return name
                    fallback_current = name
                if first_pending is None and s.startswith("- [ ]") and has_marker:
                    first_pending = s.split("**")[1]
        return fallback_current or first_pending or "—"
    except Exception:
        return "—"


# ── Log parser ────────────────────────────────────────────────────────────────
def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def parse_log(path: str, prev_size: int, state: State) -> State:
    if not os.path.exists(path):
        return state

    size = os.path.getsize(path)
    if size == prev_size:
        return state

    state.log_size = size
    state.last_activity_ts = time.time()

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        if prev_size > 0 and prev_size < size:
            f.seek(prev_size)
        lines = f.readlines()

    now_str = datetime.now().strftime("%H:%M:%S")

    def _agent_color() -> str:
        return AGENT_COLOR.get(state.agent, WHITE)

    for raw in lines:
        line = strip_ansi(raw).strip()
        if not line or line in ("│", "╭", "╰"):
            continue

        # ── Multi-line pattern resolution (supervisor writes task name on next line) ──
        if state._pending_task_start and line and not line.startswith("›"):
            state._pending_task_start = False
            state.current_task = line
            state.phase = "Task běží"
            state.activity.append((f"{now_str}  🚀 {line}", WHITE))
            continue

        if state._pending_task_done and "⌊" in line:
            state._pending_task_done = False
            done_name = re.sub(r"^[⌊\s]+", "", line).strip()
            state.tasks_done += 1
            state.phase = f"✅ {done_name} dokončen"
            state.activity.append((f"{now_str}  ✅ {done_name}", GREEN))
            continue

        if "Crew Execution Started" in line:
            state.phase = "Crew spuštěn"

        # Supervisor: "›› Začínám ›› " — task name follows on next line
        if "›› Začínám" in line or "Začínám ›" in line:
            state._pending_task_start = True

        # Fallback: legacy/emoji pattern (kept for compatibility)
        m_start = re.search(r"🚀 Začínám:\s*(.+)", line)
        if m_start:
            task_name = m_start.group(1).split("\n")[0].strip()
            state.current_task = task_name
            state.phase = "Task běží"
            state.activity.append((f"{now_str}  🚀 {task_name}", WHITE))

        if "Task Started" in line or "🤖 AGENTI PRACUJÍ" in line:
            state.phase = "Task běží"

        # Supervisor: "✓ Hotovo:" — done task name follows on next line with "⌊"
        if re.search(r"[✓✅]\s*Hotovo:", line):
            state._pending_task_done = True

        # Supervisor single-line completion: "✅ HOTOVO!"
        if "✅ HOTOVO!" in line and not state._pending_task_done:
            state.tasks_done += 1
            label = state.current_task if state.current_task != "—" else f"Task #{state.tasks_done}"
            state.phase = f"✅ {label} dokončen"
            state.activity.append((f"{now_str}  ✅ {label}", GREEN))

        # Fallback: legacy/emoji pattern
        m_done = re.search(r"✅ Hotovo:\s*(.+)", line)
        if m_done:
            done_name = m_done.group(1).split("\n")[0].strip()
            state.tasks_done += 1
            state.phase = f"✅ {done_name} dokončen"
            state.activity.append((f"{now_str}  ✅ {done_name}", GREEN))
        elif "Task Completed" in line:
            state.tasks_done += 1
            label = state.current_task if state.current_task != "—" else f"Task #{state.tasks_done}"
            state.phase = f"✅ {label} dokončen"
            state.activity.append((f"{now_str}  ✅ {label}", GREEN))

        # Supervisor: "Další: → {task}" (inside "⌊ Další: → ..." line)
        m_next_sv = re.search(r"Další: → (.+)", line)
        if m_next_sv:
            next_name = m_next_sv.group(1).split("\n")[0].strip()
            state.current_task = next_name

        # Fallback: legacy/emoji pattern
        m_next = re.search(r"➡️ Další:\s*(.+)", line)
        if m_next:
            next_name = m_next.group(1).split("\n")[0].strip()
            state.current_task = next_name

        if "Crew Execution Completed" in line or "KOMPLETNĚ hotový" in line:
            state.phase = "✅ VŠECHNO HOTOVO"
            state.activity.append((f"{now_str}  🎉 Crew dokončen!", GREEN))

        m = re.search(r"Agent:\s+([A-ZÁa-záčďéěíňóřšťúůýžÄÖÜ][^\n│]{2,35}?)[\s│]*$", line)
        if m:
            name = m.group(1).strip().rstrip("│ ")
            if name and name not in ("Started", "Completed") and len(name) < 40:
                if name != state.agent:
                    color = AGENT_COLOR.get(name, WHITE)
                    state.activity.append((f"{now_str}  🤖 {name}", color))
                state.agent = name

        m = re.search(r"Tool:\s+([a-z_]+)", line)
        if m and "Tool Execution Started" not in state.phase:
            tool_name = m.group(1)
            state.tool = tool_name
            state.tool_args = None
            color = _agent_color()
            state.activity.append((f"{now_str}  🔧 {state.agent} → {tool_name}", color))

        m = re.search(r"Args:\s+(\{.+|\'.+)", line)
        if m:
            raw_args = m.group(1)[:160]
            fp = re.search(r"'(?:file_path|file)':\s*['\"]([^'\"]{1,80})", raw_args)
            state.tool_args = fp.group(1).split("\n")[0] if fp else raw_args[:80]

        if "✅ Written" in line:
            fm = re.search(r"✅ Written '([^']+)'", line)
            if fm:
                fpath = fm.group(1).replace("projects/taskmanager/output/", "")
                if fpath not in state.files_written:
                    state.files_written.append(fpath)
                state.activity.append((f"{now_str}  📄 {state.agent} → {fpath}", _agent_color()))
                state.tool = None
                state.tool_args = None

        if "Tool Failed" in line or "Error executing tool" in line:
            state.errors.append(f"{now_str}  {line[:90]}")
            state.activity.append((f"{now_str}  ⚠️  {state.agent} tool selhal", RED))
        if "rate_limit_error" in line or ("429" in line and "error" in line.lower()):
            msg = f"{now_str}  ⏳ Rate limit — čekám..."
            state.errors.append(msg)
            state.activity.append((msg, YELLOW))
        if "Fatální chyba" in line or "fatal" in line.lower():
            state.errors.append(f"{now_str}  ❌ {line[:90]}")
            state.activity.append((f"{now_str}  ❌ Fatální chyba!", RED))
        if "credit balance" in line.lower():
            msg = f"{now_str}  💳 Chybí kredit!"
            state.errors.append(msg)
            state.activity.append((msg, RED))
        if "⏳ Přechodná chyba" in line:
            state.activity.append((f"{now_str}  ⏳ Retry po chybě...", YELLOW))

    return state


# ── Formatting helpers ────────────────────────────────────────────────────────
def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def fmt_cost(usd: float) -> str:
    if usd >= 1.0:
        return f"${usd:.2f}"
    return f"${usd:.4f}"


ERASE_LINE = "\033[K"
ERASE_DOWN = "\033[J"


# ── Background alive-checker (avoids blocking the render loop) ────────────────
_alive_lock = threading.Lock()
_alive_value = False

def _alive_checker_loop():
    global _alive_value
    while True:
        try:
            result = subprocess.run(
                ["pgrep", "-f", "supervisor.py"],
                capture_output=True, timeout=3,
            )
            val = bool(result.stdout.strip())
        except Exception:
            val = False
        with _alive_lock:
            prev_val = _alive_value
            _alive_value = val
        time.sleep(3)

def _start_alive_checker():
    t = threading.Thread(target=_alive_checker_loop, daemon=True)
    t.start()

def _get_alive() -> bool:
    with _alive_lock:
        return _alive_value


# ── Render ────────────────────────────────────────────────────────────────────
def render(state: State, spinner_idx: int, rows: int, cols: int):
    W = min(cols, 90)
    EL = ERASE_LINE

    spin = SPINNERS[spinner_idx % len(SPINNERS)]
    elapsed = time.time() - state.last_activity_ts
    stuck = elapsed > STUCK_THRESHOLD

    alive = _get_alive()

    u = state.usage

    # ── Build fixed sections (everything except activity) ─────────────────
    header: list[str] = []
    bottom: list[str] = []

    # Header
    header.append(f"{BOLD}{'═' * W}{RESET}")
    header.append(f"  {BOLD}🤖 Multiagent Monitor{RESET}   {DIM}{LOG_FILE}{RESET}")
    header.append(f"{'─' * W}")

    proc_indicator = f"{GREEN}● BĚŽÍ{RESET}" if alive else f"{RED}● NEBĚŽÍ{RESET}"
    header.append(f"  Proces:  {proc_indicator}   Soubory: {BOLD}{len(state.files_written)}{RESET}   Hotovo: {BOLD}{state.tasks_done}{RESET}")
    header.append(f"  Task:    {YELLOW}{BOLD}{state.current_task}{RESET}")

    # H3 fix: override displayed phase when process is not alive
    _active_phases = ("Task běží", "Crew spuštěn", "Startování", "Agenti pracují")
    if not alive and any(p in state.phase for p in _active_phases):
        displayed_phase = "Supervisor zastavil práci"
        phase_color = RED
        phase_icon = "●"
    else:
        displayed_phase = state.phase
        phase_color = GREEN if "HOTOVO" in state.phase else (YELLOW if stuck else WHITE)
        phase_icon = "✅" if "HOTOVO" in state.phase else spin
    header.append(f"  Stav:    {phase_color}{BOLD}{phase_icon}  {displayed_phase}{RESET}")

    agent_color = AGENT_COLOR.get(state.agent, WHITE)
    header.append(f"  Agent:   {agent_color}{BOLD}{state.agent}{RESET}")

    if state.tool:
        args_str = f"  {DIM}→ {state.tool_args}{RESET}" if state.tool_args else ""
        header.append(f"  Tool:    {CYAN}{BOLD}{state.tool}{RESET}{args_str}")
    else:
        header.append(f"  Tool:    {DIM}(čeká na LLM...){RESET}")

    if stuck and alive:
        header.append(f"  {YELLOW}{BOLD}⚠️  ZASEKNUTÉ?{RESET}  {YELLOW}Žádná aktivita {int(elapsed)}s.{RESET}")
    elif not alive and state.phase != "✅ VŠECHNO HOTOVO":
        header.append(f"  {RED}{BOLD}⚠️  Supervisor neběží!{RESET}")
    else:
        header.append(f"  {DIM}Poslední aktivita: před {int(elapsed)}s{RESET}")

    header.append("")
    header.append(f"{'─' * W}")

    # Token usage

    header.append("")
    if u.agents:
        header.append(f"  {DIM}{'Agent':<14} {'Model':<28} {'Input':>8} {'Output':>8} {'Cena':>10}{RESET}")
        header.append(f"  {DIM}{'─' * 14} {'─' * 28} {'─' * 8} {'─' * 8} {'─' * 10}{RESET}")
        for name, info in u.agents.items():
            a_color = AGENT_COLOR.get(name, WHITE)
            model_short = info.get("model", "?").split("/")[-1][:26]
            inp = fmt_tokens(info.get("input_tokens", 0))
            out = fmt_tokens(info.get("output_tokens", 0))
            cost = fmt_cost(info.get("cost_total", 0))
            header.append(f"  {a_color}{name:<14}{RESET} {DIM}{model_short:<28}{RESET} {inp:>8} {out:>8} {YELLOW}{cost:>10}{RESET}")
        header.append(f"  {'─' * 14} {'─' * 28} {'─' * 8} {'─' * 8} {'─' * 10}")
        header.append(f"  {BOLD}{'CELKEM':<14}{RESET} {'':<28} {BOLD}{fmt_tokens(u.input_tokens):>8}{RESET} {BOLD}{fmt_tokens(u.output_tokens):>8}{RESET} {YELLOW}{BOLD}{fmt_cost(u.cost_usd):>10}{RESET}")
    else:
        header.append(f"  {DIM}(čeká se na data — aktualizuje se každých 10s){RESET}")

    header.append("")
    header.append(f"{'─' * W}")

    # Bottom: footer
    bottom.append("")
    bottom.append(f"  {DIM}Ctrl+C ukončí monitor (agenti dál běží)   {datetime.now().strftime('%H:%M:%S')}{RESET}")

    # ── Activity: fixed last 10 events ──────────────────────────────────
    events = list(state.activity)
    last6 = list(reversed(events[-6:])) if events else []

    # ── Assemble frame ────────────────────────────────────────────────────
    buf: list[str] = []
    buf.append(HOME)

    for line in header:
        buf.append(f"{line}{EL}\n")

    buf.append(f"  {BOLD}Události:{RESET}{EL}\n")
    if last6:
        for entry in last6:
            text, color = entry if isinstance(entry, tuple) else (entry, DIM)
            buf.append(f"  {color}{text[:W-4]}{RESET}{EL}\n")
    else:
        buf.append(f"  {DIM}(zatím žádné události){RESET}{EL}\n")
    buf.append(f"{'─' * W}{EL}\n")

    for line in bottom:
        buf.append(f"{line}{EL}\n")

    buf.append(ERASE_DOWN)

    os.write(1, "".join(buf).encode("utf-8"))


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    try:
        os.write(1, (ALT_ENTER + HIDE_CURSOR + CLEAR_SCREEN + HOME).encode())
    except OSError:
        pass

    _start_alive_checker()

    state = State()
    state.current_task = read_current_task_from_progress()
    prev_size = 0
    spinner_idx = 0

    try:
        while True:
            try:
                rows, cols = os.get_terminal_size()
            except OSError:
                rows, cols = 24, 80
            state = parse_log(LOG_FILE, prev_size, state)
            prev_size = state.log_size

            if spinner_idx % 5 == 0:
                state.usage = read_usage(USAGE_FILE)

            # H1 fix: re-read PROGRESS.md every ~15s to keep current_task fresh
            if spinner_idx % 15 == 0:
                progress_task = read_current_task_from_progress()
                if progress_task != "—":
                    state.current_task = progress_task

            render(state, spinner_idx, rows, cols)
            spinner_idx += 1
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            os.write(1, (ALT_EXIT + SHOW_CURSOR).encode())
        except OSError:
            pass
        print("Monitor ukončen. Agenti dál běží na pozadí.")


if __name__ == "__main__":
    main()
