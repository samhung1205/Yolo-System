"""
Pydantic schemas for User — request and response models.
"""
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


USERNAME_RE = re.compile(r"^[A-Za-z0-9]{3,32}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,64}$")


class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None

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
            raise ValueError("密碼必須為至少 8 位英數組合，且同時包含字母與數字")
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
    """Self-service profile update — only nickname and password allowed."""

    nickname: Optional[str] = None
    password: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        text = v.strip()
        if not PASSWORD_RE.match(text):
            raise ValueError("密碼必須為至少 8 位英數組合，且同時包含字母與數字")
        return text


class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    avatar: Optional[str] = None

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
            raise ValueError("密碼必須為至少 8 位英數組合，且同時包含字母與數字")
        return text
