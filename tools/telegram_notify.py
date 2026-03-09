import asyncio
import os
import requests
import threading
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

pending_responses = {}


def send_telegram_message(message: str, chat_id: str = None, parse_mode: str = None) -> bool:
    """Send a message to Telegram."""
    token = BOT_TOKEN
    chat = chat_id or CHAT_ID

    if not token or not chat:
        print("⚠️ Telegram: Chybí TOKEN nebo CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat, "text": message}
    if parse_mode:
        data["parse_mode"] = parse_mode

    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code != 200:
            print(f"❌ Telegram chyba {response.status_code}: {response.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"❌ Telegram chyba: {e}")
        return False


async def handle_telegram_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages from Telegram (for HITL)."""
    user_message = update.message.text
    user_id = str(update.effective_user.id)

    print(f"📨 Telegram odpověď od {user_id}: {user_message}")

    if user_id in pending_responses:
        pending_responses[user_id] = user_message
        pending_responses[user_id + "_event"].set()
    else:
        await update.message.reply_text(
            "Odpověď zaznamenána. Pokud čekáš na odpověď od agenta, "
            "tato zpráva bude předána."
        )


def _run_bot_loop(application: Application) -> None:
    """Run the Telegram bot in a dedicated asyncio event loop.

    run_polling() registers OS signal handlers via loop.add_signal_handler(),
    which is only allowed in the main thread. Using the lower-level async API
    directly avoids that restriction entirely.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _start() -> None:
        await application.initialize()
        await application.updater.start_polling(drop_pending_updates=True)
        await application.start()
        # Block forever; the daemon thread will be killed on process exit.
        await asyncio.get_event_loop().create_future()

    try:
        loop.run_until_complete(_start())
    except (RuntimeError, Exception) as e:
        # Telegram bot errors are non-fatal background thread errors
        print(f"⚠️ Telegram bot runtime error (non-fatal): {str(e)[:100]}")
        # Don't re-raise - this is a background thread, don't crash the main process
    finally:
        try:
            loop.close()
        except:
            pass


# Global application instance to prevent multiple bots
_bot_application = None
_bot_lock = threading.Lock()


def setup_telegram_listener():
    """Start Telegram bot in a separate thread to listen for responses.
    
    Uses a global lock to prevent multiple bot instances from starting simultaneously.
    If a bot is already running, returns the existing instance without starting a new one.
    """
    global _bot_application
    
    if not BOT_TOKEN:
        print("⚠️ Telegram bot neběží - chybí TELEGRAM_BOT_TOKEN")
        return None

    with _bot_lock:
        # If bot is already initialized, return it (prevent multiple instances)
        if _bot_application is not None:
            print("✅ Telegram bot již běží - používám existující instanci")
            return _bot_application

        import time
        time.sleep(1)  # Small delay to avoid rapid restarts

        try:
            application = Application.builder().token(BOT_TOKEN).build()

            application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram_response)
            )

            thread = threading.Thread(target=_run_bot_loop, args=(application,), daemon=True)
            thread.start()

            print("✅ Telegram bot naslouchá pro HITL odpovědi")
            
            # Store the application globally to prevent multiple instances
            _bot_application = application
            return application
        except Exception as e:
            print(f"❌ Telegram bot init error: {e}")
            return None
