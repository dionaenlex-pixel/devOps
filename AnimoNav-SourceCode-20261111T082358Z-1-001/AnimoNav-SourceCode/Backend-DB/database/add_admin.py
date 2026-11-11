"""Add an admin account, or change an admin's password.

Usage (run it in the animonav folder, on the laptop or in a PythonAnywhere Bash console):
    python add_admin.py juan          # asks for juan's password
    python add_admin.py --list        # shows the admin usernames
    python add_admin.py --unlock juan # lets juan log in again before the 24-hour lock ends

The password is typed without showing on screen. Ask the groupmate to type it themselves.
"""

import argparse
import getpass

from werkzeug.security import generate_password_hash

from database import db


def main():
    parser = argparse.ArgumentParser(description="Add an AnimoNav admin account.")
    parser.add_argument("username", nargs="?", help="the new admin's username")
    parser.add_argument("--list", action="store_true", help="show the admin usernames")
    parser.add_argument("--unlock", action="store_true", help="unlock an account locked after 3 wrong passwords")
    args = parser.parse_args()

    conn = db.connect()
    db.add_login_lock_columns(conn)
    if args.unlock and args.username:
        n = conn.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE username = ?",
                         (args.username.strip(),)).rowcount
        conn.commit()
        print(f"Unlocked {args.username}." if n else f"There's no admin called {args.username}.")
        return
    if args.list or not args.username:
        names = [r["username"] for r in conn.execute("SELECT username FROM users ORDER BY username")]
        print("Admins:", ", ".join(names) or "none")
        return

    username = args.username.strip()
    password = getpass.getpass(f"Password for {username} (at least 8 characters): ")
    if len(password) < 8:
        raise SystemExit("Not saved: use a password with at least 8 characters.")
    if password != getpass.getpass("Type it again: "):
        raise SystemExit("Not saved: the two passwords don't match.")

    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.execute("UPDATE users SET password_hash = ?, failed_logins = 0, locked_until = NULL WHERE id = ?",
                     (generate_password_hash(password), existing["id"]))
        print(f"Changed the password for {username} (and unlocked it).")
    else:
        conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                     (username, generate_password_hash(password)))
        print(f"Added admin {username}. They can log in at /admin.")
    conn.commit()


if __name__ == "__main__":
    main()
