"""Create a dashboard login for the business owner.

Run with:  python -m app.create_owner owner@example.com "Owner Name"
The password is typed at a hidden prompt, so it never appears in shell history.
"""

import sys
from getpass import getpass

from app.db.session import SessionLocal
from app.services.errors import ConflictError
from app.services.owners import create_owner


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python -m app.create_owner <email> "<name>"')
    email, name = sys.argv[1], sys.argv[2]
    password = getpass("Password: ")
    if password != getpass("Repeat password: "):
        raise SystemExit("Passwords don't match")
    try:
        with SessionLocal() as db:
            owner = create_owner(db, email, name, password)
    except (ValueError, ConflictError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Owner created: {owner.email}")


if __name__ == "__main__":
    main()
