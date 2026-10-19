"""
Client-side form rules for the desktop app.

These mirror ``backend/app/schemas/user.py`` so the desktop never accepts a
value the API will reject (or rejects one the API would accept). The backend
remains the source of truth.
"""
import re

USERNAME_RE = re.compile(r"^[A-Za-z0-9]{3,32}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,64}$")

PASSWORD_RULE_TEXT = "密码必须为 8-64 位英数组合，且同时包含字母与数字"
