import bcrypt
import streamlit as st


def get_admin_password_hash() -> str | None:
    try:
        return str(st.secrets.get("ADMIN_PASSWORD_HASH"))
    except Exception:
        return None


def is_admin_password(password: str) -> bool:
    hashed = get_admin_password_hash()
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False
