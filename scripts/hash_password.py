#!/usr/bin/env python3
"""Generate a bcrypt hash for Streamlit secrets."""

from getpass import getpass

import bcrypt


if __name__ == "__main__":
    password = getpass("Password to hash: ")
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    print(f'ADMIN_PASSWORD_HASH = "{hashed}"')
