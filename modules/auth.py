"""
用户认证模块 — 提供用户注册、登录、密码管理及操作日志功能
User authentication module
"""

import sqlite3
import hashlib
import os
from datetime import datetime

_DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'users.db')


def _hash_password(password: str, salt: str = None):
    """返回 (hash_hex, salt_hex) 使用 PBKDF2-HMAC-SHA256"""
    if salt is None:
        salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 200_000)
    return pwd_hash.hex(), salt


class UserDatabase:
    """SQLite-backed user store."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or _DEFAULT_DB
        self._init_db()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_db(self):
        conn = self._connect()
        c = conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                salt          TEXT    NOT NULL,
                role          TEXT    DEFAULT 'user',
                display_name  TEXT    DEFAULT '',
                email         TEXT    DEFAULT '',
                created_at    TEXT,
                last_login    TEXT,
                is_active     INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS activity_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                username  TEXT,
                action    TEXT,
                detail    TEXT,
                timestamp TEXT
            );
        """)
        conn.commit()
        # Seed default admin
        c.execute("SELECT COUNT(*) FROM users")
        if c.fetchone()[0] == 0:
            self._insert_user(c, 'admin', 'admin123', 'admin', '管理员')
            conn.commit()
        conn.close()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _insert_user(self, cursor, username, password, role='user', display_name=''):
        pwd_hash, salt = _hash_password(password)
        now = _now()
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt, role, display_name, created_at, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (username, pwd_hash, salt, role, display_name, now)
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def create_user(self, username: str, password: str,
                    role: str = 'user', display_name: str = '') -> tuple:
        """Return (ok: bool, msg: str)"""
        username = username.strip()
        if not username:
            return False, "用户名不能为空"
        if len(username) < 3:
            return False, "用户名至少需要 3 个字符"
        if len(password) < 6:
            return False, "密码至少需要 6 个字符"
        if not username.isidentifier():
            return False, "用户名只能包含字母、数字和下划线"
        try:
            conn = self._connect()
            c = conn.cursor()
            self._insert_user(c, username, password, role, display_name or username)
            conn.commit()
            conn.close()
            self.log_action('system', 'create_user', f'username={username} role={role}')
            return True, f"用户 '{username}' 创建成功"
        except sqlite3.IntegrityError:
            return False, f"用户名 '{username}' 已存在"
        except Exception as e:
            return False, str(e)

    def verify_user(self, username: str, password: str) -> tuple:
        """Return (ok: bool, info: dict)  info has keys: username, role, display_name"""
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "SELECT password_hash, salt, role, is_active, display_name FROM users WHERE username=?",
            (username,)
        )
        row = c.fetchone()
        conn.close()
        if not row:
            self.log_action(username, 'login_fail', 'user not found')
            return False, {}
        pwd_hash, salt, role, is_active, display_name = row
        if not is_active:
            self.log_action(username, 'login_fail', 'account disabled')
            return False, {'error': '账户已被禁用，请联系管理员'}
        computed, _ = _hash_password(password, salt)
        if computed == pwd_hash:
            conn2 = self._connect()
            conn2.execute("UPDATE users SET last_login=? WHERE username=?", (_now(), username))
            conn2.commit()
            conn2.close()
            self.log_action(username, 'login_success', '')
            return True, {'username': username, 'role': role,
                          'display_name': display_name or username}
        self.log_action(username, 'login_fail', 'wrong password')
        return False, {}

    def change_password(self, username: str, old_password: str, new_password: str) -> tuple:
        ok, _ = self.verify_user(username, old_password)
        if not ok:
            return False, "原密码错误"
        if len(new_password) < 6:
            return False, "新密码至少需要 6 个字符"
        pwd_hash, salt = _hash_password(new_password)
        conn = self._connect()
        conn.execute("UPDATE users SET password_hash=?, salt=? WHERE username=?",
                     (pwd_hash, salt, username))
        conn.commit()
        conn.close()
        self.log_action(username, 'change_password', 'success')
        return True, "密码修改成功"

    def admin_reset_password(self, username: str, new_password: str) -> tuple:
        if len(new_password) < 6:
            return False, "密码至少需要 6 个字符"
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        if not c.fetchone():
            conn.close()
            return False, "用户不存在"
        pwd_hash, salt = _hash_password(new_password)
        conn.execute("UPDATE users SET password_hash=?, salt=? WHERE username=?",
                     (pwd_hash, salt, username))
        conn.commit()
        conn.close()
        self.log_action('admin', 'reset_password', f'target={username}')
        return True, f"用户 '{username}' 的密码已重置"

    def list_users(self) -> list:
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT id, username, role, display_name, created_at, last_login, is_active FROM users")
        rows = c.fetchall()
        conn.close()
        return [
            {'id': r[0], 'username': r[1], 'role': r[2],
             'display_name': r[3], 'created_at': r[4],
             'last_login': r[5], 'is_active': bool(r[6])}
            for r in rows
        ]

    def set_user_active(self, username: str, active: bool) -> tuple:
        if username == 'admin':
            return False, "不能禁用管理员账户"
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        if not c.fetchone():
            conn.close()
            return False, "用户不存在"
        conn.execute("UPDATE users SET is_active=? WHERE username=?",
                     (1 if active else 0, username))
        conn.commit()
        conn.close()
        status = "启用" if active else "禁用"
        self.log_action('admin', f'{status}_user', f'username={username}')
        return True, f"用户 '{username}' 已{status}"

    def delete_user(self, username: str) -> tuple:
        if username == 'admin':
            return False, "不能删除超级管理员账户"
        conn = self._connect()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        if not c.fetchone():
            conn.close()
            return False, "用户不存在"
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()
        conn.close()
        self.log_action('admin', 'delete_user', f'username={username}')
        return True, f"用户 '{username}' 已删除"

    def log_action(self, username: str, action: str, detail: str = ''):
        try:
            conn = self._connect()
            conn.execute(
                "INSERT INTO activity_log (username, action, detail, timestamp) VALUES (?,?,?,?)",
                (username, action, detail, _now())
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_activity_log(self, limit: int = 200) -> list:
        conn = self._connect()
        c = conn.cursor()
        c.execute(
            "SELECT username, action, detail, timestamp FROM activity_log "
            "ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = c.fetchall()
        conn.close()
        return [{'username': r[0], 'action': r[1], 'detail': r[2], 'timestamp': r[3]}
                for r in rows]


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
