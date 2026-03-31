import sqlite3

def get_user(username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # SQL injection vulnerability
    cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
    return cursor.fetchone()

def divide(a, b):
    # missing zero division check
    return a / b

class UserService:
    def __init__(self):
        self.users = []

    def add_user(self, user):
        self.users.append(user)
        # no duplicate check, no validation