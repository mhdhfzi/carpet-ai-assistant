"""See or change whether the chat is paused for lack of AI credit.

Run with:  python -m app.chat_switch status
           python -m app.chat_switch resume    (straight after topping up)

On Cloud Run, through the one-off command job, e.g.:
  gcloud run jobs execute cc-manage --region asia-southeast1 --args=-m,app.chat_switch,resume --wait

To switch the chat off on purpose, set CHAT_ENABLED=false on the service instead.
"""

import argparse

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services import assistant_status


def main() -> None:
    parser = argparse.ArgumentParser(description="See or end an out-of-credit pause.")
    parser.add_argument("action", choices=["status", "resume"])
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.action == "resume":
            assistant_status.resume(db)
            print("Pause cleared: the chat is shown again (if switched on and under the cap).")
        until = assistant_status.paused_until(db)
        print(f"Switched on (CHAT_ENABLED): {get_settings().chat_enabled}")
        print(f"Paused for lack of credit: {f'until {until.isoformat()}' if until else 'no'}")
        print(f"Daily reply cap reached: {assistant_status.daily_limit_reached(db)}")
        print(f"Chat shown to customers: {assistant_status.is_available(db)}")


if __name__ == "__main__":
    main()
