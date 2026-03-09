from crewai.tools import BaseTool
from pydantic import BaseModel
from typing import Type
import sys
import os
import threading
import select


TIMEOUT_SECONDS = None


class AskHumanInput(BaseModel):
    question: str


class AskHumanTool(BaseTool):
    name: str = "ask_human"
    description: str = (
        "Ask a question to a human and wait for their response. "
        "Use this when you need clarification or guidance. "
        "If no response arrives within 2 minutes, automatically continue with best judgment."
    )
    args_schema: Type[BaseModel] = AskHumanInput

    def _run(self, question: str) -> str:
        """Ask human and wait for response. Auto-continues after TIMEOUT_SECONDS."""
        from tools.telegram_notify import send_telegram_message, pending_responses

        user_id = os.getenv("TELEGRAM_CHAT_ID", "")

        event = threading.Event()
        if user_id:
            pending_responses[user_id] = None
            pending_responses[user_id + "_event"] = event

        sent = send_telegram_message(
            f"🤔 *AGENT SE PTÁ*\n\n{question}\n\n_Odpověz prosím v této zprávě nebo v terminálu._",
            parse_mode="Markdown",
        )
        if not sent:
            print("⚠️ Telegram zpráva se neodeslala — zkontroluj TOKEN a CHAT_ID")

        print(f"\n🤔 AGENT SE PTÁ:")
        print(f"   {question}")
        print(f"   ⏳ Čekám na odpověď (neomezeně)...\n")

        while not event.is_set():
            event.wait(timeout=1)

            if sys.platform != "win32":
                try:
                    if select.select([sys.stdin], [], [], 0)[0]:
                        terminal_input = sys.stdin.readline().strip()
                        if terminal_input:
                            print(f"   📝 Odpověď z terminálu: {terminal_input}")
                            return f"Human response: {terminal_input}"
                except Exception:
                    pass

        response = pending_responses.get(user_id) if user_id else None
        if response:
            print(f"   📨 Odpověď z Telegramu: {response}")
            return f"Human response: {response}"

        return "No response received"


AskHuman = AskHumanTool()
