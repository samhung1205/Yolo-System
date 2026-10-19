"""
Pydantic schemas for User — request and response models.
"""
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


USERNAME_RE = re.compile(r"^[A-Za-z0-9]{3,32}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# Printable ASCII without spaces: letters + digits required, symbols allowed.
PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[\x21-\x7E]{8,64}$")


def _clean_avatar(v: Optional[str]) -> Optional[str]:
    """Shape check only; who may use which file is checked in avatar_service."""
    if v is None:
        return None
    text = v.strip()
    if not text:
        return None
    if len(text) > 255 or "/" in text or "\\" in text or text.startswith("."):
        raise ValueError("頭像檔名無效，請重新上傳頭像")
    return text


class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None

    _validate_avatar = field_validator("avatar")(classmethod(lambda cls, v: _clean_avatar(v)))

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        text = v.strip()
        if not USERNAME_RE.match(text):
            raise ValueError("使用者名稱只能包含英文字母與數字，長度 3-32 位")
        return text

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        text = v.strip().lower()
        if not text:
            return None
        if not EMAIL_RE.match(text):
            raise ValueError("Email 格式不正確")
        return text

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        text = v.strip()
        if not PASSWORD_RE.match(text):
            raise ValueError("密碼需為 8-64 位，同時包含英文字母與數字，可使用符號（不可含空白或中文）")
        return text


class UserRead(BaseModel):
    id: int
    username: str
    email: Optional[str]
    nickname: Optional[str]
    avatar: Optional[str]
    avatar_url: Optional[str] = None
    register_time: datetime
    is_admin: bool
    is_active: bool

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    """Self-service profile update — nickname, avatar and password only.

    ``current_password`` is required whenever ``password`` is set, so a stolen
    token alone cannot lock the owner out of their account.
    """

    nickname: Optional[str] = None
    avatar: Optional[str] = None
    password: Optional[str] = None
    current_password: Optional[str] = None

    _validate_avatar = field_validator("avatar")(classmethod(lambda cls, v: _clean_avatar(v)))

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        text = v.strip()
        if not PASSWORD_RE.match(text):
            raise ValueError("密碼需為 8-64 位，同時包含英文字母與數字，可使用符號（不可含空白或中文）")
        return text


class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    avatar: Optional[str] = None

    _validate_avatar = field_validator("avatar")(classmethod(lambda cls, v: _clean_avatar(v)))

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        text = v.strip()
        if not USERNAME_RE.match(text):
            raise ValueError("使用者名稱只能包含英文字母與數字，長度 3-32 位")
        return text

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        text = v.strip().lower()
        if not text:
            return None
        if not EMAIL_RE.match(text):
            raise ValueError("Email 格式不正確")
        return text

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        text = v.strip()
        if not PASSWORD_RE.match(text):
            raise ValueError("密碼需為 8-64 位，同時包含英文字母與數字，可使用符號（不可含空白或中文）")
        return text
