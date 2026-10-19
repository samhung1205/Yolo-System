"""
Client-side form rules for the desktop app.

These mirror ``backend/app/schemas/user.py`` so the desktop never accepts a
value the API will reject (or rejects one the API would accept). The backend
remains the source of truth.
"""
import re

USERNAME_RE = re.compile(r"^[A-Za-z0-9]{3,32}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# Printable ASCII without spaces: letters + digits required, symbols allowed.
PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[\x21-\x7E]{8,64}$")

PASSWORD_RULE_TEXT = "密码需为 8-64 位，同时包含英文字母与数字，可使用符号（不可含空格或中文）"
