"""
RH Assistance - Flask Web UI
Company: IT Road Consulting
"""

import asyncio
import sqlite3
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session

from ..config import config
from ..data.cache import SimpleCache
from ..core.orchestrator import ChatbotOrchestrator
from ..llm.openrouter import OpenRouterLLM, MockLLM
from ..sync.auto_sync import DataSyncEngine

APP_NAME = "RH Assistance"
COMPANY_NAME = "IT Road Consulting"


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    if not config.SESSION_SECRET_KEY:
        raise RuntimeError("CHATBOT_SESSION_SECRET is required to start the chatbot web app.")
    app.secret_key = config.SESSION_SECRET_KEY

    # Auto-sync latest data from archive
    if config.AUTO_SYNC_ON_STARTUP:
        sync_engine = DataSyncEngine(
            db_path=config.DB_PATH,
            data_archive_dir=str(config.ARCHIVE_PATH),  # Action 227: DATA_ROOT/archive
        )
        sync_engine.sync()

    cache = SimpleCache(default_ttl=config.CACHE_TTL)

    db_conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    db_conn.row_factory = sqlite3.Row

    if config.OPENROUTER_API_KEY:
        llm = OpenRouterLLM(
            api_key=config.OPENROUTER_API_KEY,
            model=config.LLM_MODEL,
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
            timeout=config.LLM_TIMEOUT,
            max_requests_per_minute=config.LLM_MAX_REQUESTS_PER_MINUTE,
            retry_wait_seconds=config.LLM_RETRY_WAIT_SECONDS,
            max_retries=config.LLM_MAX_RETRIES,
        )
    else:
        llm = MockLLM()

    orchestrator = ChatbotOrchestrator(
        db_session=db_conn,
        chroma_client=None,
        cache=cache,
        llm_client=llm,
        db_path=str(config.DB_PATH),
    )

    def get_session_id() -> str:
        if "chat_session_id" not in session:
            session["chat_session_id"] = str(uuid.uuid4())
        return session["chat_session_id"]

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            app_name=APP_NAME,
            company_name=COMPANY_NAME,
        )

    @app.post("/api/chat")
    def chat():
        payload = request.get_json(force=True)
        message = (payload.get("message") or "").strip()
        if not message:
            return jsonify({"success": False, "error": "Message is empty"}), 400

        session_id = get_session_id()
        response = asyncio.run(
            orchestrator.chat(
                query=message,
                session_id=session_id,
            )
        )
        if not response.get("success"):
            return jsonify(response)

        # Return only the user prompt + LLM response (no metadata)
        return jsonify(
            {
                "success": True,
                "response": response.get("response", ""),
            }
        )

    @app.post("/api/session/clear")
    def clear_session():
        session_id = get_session_id()
        orchestrator.clear_session(session_id)
        return jsonify({"success": True})

    @app.get("/api/session/info")
    def session_info():
        session_id = get_session_id()
        info = orchestrator.get_session_info(session_id)
        return jsonify({"success": True, "info": info})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=config.DEBUG)
