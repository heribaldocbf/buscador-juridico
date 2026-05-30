"""Carrega DB_CONNECTION_STRING de variável de ambiente ou arquivo .env local."""
import os


def get_db_connection_string() -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    conn = os.environ.get("DB_CONNECTION_STRING")
    if not conn:
        raise ValueError(
            "DB_CONNECTION_STRING não configurada. "
            "Crie um arquivo .env na raiz do projeto (veja .env.example) "
            "ou defina a variável de ambiente."
        )
    return conn


def create_db_engine():
    from sqlalchemy import create_engine
    return create_engine(get_db_connection_string())
