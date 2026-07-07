"""
db.py
-----
Connexion à l'entrepôt PostgreSQL `churn_dw`, réutilisée par toutes les pages
de l'application. Mêmes conventions que `04_machine_learning/src/db.py` :
les paramètres de connexion sont lus depuis les *secrets* Streamlit en
priorité (déploiement cloud), puis depuis les variables d'environnement
(développement local), avec des valeurs par défaut pour un PostgreSQL local.

En local (développement) :
    export PGHOST=localhost PGPORT=5432 PGDATABASE=churn_dw PGUSER=postgres PGPASSWORD=postgres

En déploiement (Streamlit Community Cloud) :
    Renseigner ces mêmes clés dans "Settings -> Secrets" de l'app, au format :
        PGHOST = "..."
        PGPORT = "5432"
        PGDATABASE = "churn_dw"
        PGUSER = "..."
        PGPASSWORD = "..."
    (voir DEPLOY.md pour le détail complet)
"""

from __future__ import annotations

import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def _get_param(key: str, default: str) -> str:
    """Cherche d'abord dans st.secrets (déploiement), puis dans les variables
    d'environnement (local), puis utilise la valeur par défaut."""
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass  # pas de secrets.toml en local, ce n'est pas une erreur
    return os.environ.get(key, default)


@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    """Crée (et met en cache) l'engine SQLAlchemy vers l'entrepôt `churn_dw`."""
    host = _get_param("PGHOST", "localhost")
    port = _get_param("PGPORT", "5432")
    database = _get_param("PGDATABASE", "churn_dw")
    user = _get_param("PGUSER", "postgres")
    password = _get_param("PGPASSWORD", "postgres")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=600, show_spinner=False)
def read_sql(query: str, params: dict | None = None) -> pd.DataFrame:
    """Exécute une requête SQL (mise en cache 10 min) et renvoie un DataFrame."""
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)


def check_connection() -> tuple[bool, str]:
    """Vérifie que l'entrepôt est accessible. Renvoie (ok, message)."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            n = conn.execute(text(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
            )).scalar()
        return True, f"Connexion OK — {n} tables trouvées."
    except Exception as exc:
        return False, f"Connexion échouée : {exc}"
