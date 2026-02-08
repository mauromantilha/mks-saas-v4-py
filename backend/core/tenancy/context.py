from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from customers.models import Company


_current_company: ContextVar[Optional["Company"]] = ContextVar(
    "current_company", default=None
)


def get_current_company() -> Optional["Company"]:
    return _current_company.get()


def set_current_company(company: Optional["Company"]) -> Token:
    return _current_company.set(company)


def reset_current_company(token: Token) -> None:
    _current_company.reset(token)
