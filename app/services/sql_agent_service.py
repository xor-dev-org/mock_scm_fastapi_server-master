import logging
import os
import threading
from typing import Any, Dict, Optional

from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_openai import AzureChatOpenAI

from app.utils.prompts import PROMPT, SYS_PROMPT

logger = logging.getLogger(__name__)

SQL_DATABASE_URI = os.getenv("DATABASE_URI")
SQL_AGENT_TABLES = ["purchase_orders", "items", "suppliers", "locations"]

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")


class SQLAgentService:
    """Singleton wrapper around a LangChain SQL agent scoped to four tables.

    The agent is restricted to purchase_orders, items, suppliers, and locations
    so it cannot introspect or query any other table in the database.
    """

    _instance: Optional["SQLAgentService"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "SQLAgentService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._db: Optional[SQLDatabase] = None
        self._agent = None

        if not SQL_DATABASE_URI:
            logger.warning("sql_agent.disabled reason=missing_SQL_DATABASE_URI")
            return

        try:
            self._db = SQLDatabase.from_uri(
                SQL_DATABASE_URI,
                include_tables=SQL_AGENT_TABLES,
            )
            llm = AzureChatOpenAI(
                azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME,
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_API_KEY,
                api_version=AZURE_OPENAI_API_VERSION,
                temperature=0,
            )
            toolkit = SQLDatabaseToolkit(db=self._db, llm=llm)
            self._agent = create_sql_agent(
                llm=llm,
                toolkit=toolkit,
                agent_type="tool-calling",
                prefix=SYS_PROMPT,
                suffix=PROMPT,
                verbose=False,
            )
            logger.info("sql_agent.initialized tables=%s", SQL_AGENT_TABLES)
        except Exception:
            logger.exception("sql_agent.initialization_failed")
            self._db = None
            self._agent = None

    @property
    def enabled(self) -> bool:
        return self._agent is not None

    def ask(self, question: str) -> Dict[str, Any]:
        agent = self._agent
        if agent is None:
            return {"error": "SQL agent is not configured."}

        try:
            result = agent.invoke({"input": question})
            return {"output": result.get("output", "")}
        except Exception:
            logger.exception("sql_agent.query_failed question=%s", question)
            return {"error": "Failed to answer the question using the SQL agent."}