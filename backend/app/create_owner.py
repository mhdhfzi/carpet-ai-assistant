"""Create a dashboard login for the business owner, or for a worker.

Run with:  python -m app.create_owner owner@example.com "Owner Name"
           python -m app.create_owner worker@example.com "Worker Name" --staff

The password is typed at a hidden prompt, so it never appears in shell history. A staff
login records orders and moves them along; prices, discounts, chats and reports stay the
owner's (see app/api/deps.py).
"""

import argparse
from getpass import getpass

from app.db.models import OwnerRole
from app.db.session import SessionLocal
from app.services.errors import ConflictError
from app.services.owners import create_owner


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a dashboard login.")
    parser.add_argument("email")
    parser.add_argument("name")
    parser.add_argument("--staff", action="store_true", help="a worker, not the owner")
    args = parser.parse_args()

    password = getpass("Password: ")
    if password != getpass("Repeat password: "):
        raise SystemExit("Passwords don't match")
    role = OwnerRole.STAFF if args.staff else OwnerRole.OWNER
    try:
        with SessionLocal() as db:
            owner = create_owner(db, args.email, args.name, password, role=role)
    except (ValueError, ConflictError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"{'Staff' if args.staff else 'Owner'} login created: {owner.email}")


if __name__ == "__main__":
    main()
