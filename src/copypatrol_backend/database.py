"""Database interaction."""
from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Any, Union
from uuid import UUID

import sqlalchemy.dialects.mysql
from pywikibot.time import Timestamp
from sqlalchemy import (
    BINARY,
    URL,
    VARBINARY,
    Dialect,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    TypeDecorator,
    and_,
    create_engine,
    delete,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

from copypatrol_backend.config import database_config


if TYPE_CHECKING:
    from collections.abc import Sequence

    from pywikibot.page import Page
    from pywikibot.site import APISite
    from sqlalchemy.orm import Session as _Session

    class MappedAsDataclass:
        """sqlalchemy#9467 / mypy#13856 workaround."""

        def __init__(self, *args: Any, **kwargs: Any):
            pass

else:
    from sqlalchemy.orm import MappedAsDataclass


_CREATE_TABLE_ARGS = {
    "mysql_engine": "InnoDB",
    "mariadb_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mariadb_charset": "utf8mb4",
}
_ENGINE = create_engine(URL.create(**database_config()))


Session = sessionmaker(bind=_ENGINE)
TinyInt = Integer().with_variant(
    sqlalchemy.dialects.mysql.TINYINT(),
    "mysql",
    "mariadb",
)
UnsignedFloat = Float().with_variant(
    sqlalchemy.dialects.mysql.FLOAT(unsigned=True),
    "mysql",
    "mariadb",
)
UnsignedInteger = Integer().with_variant(
    sqlalchemy.dialects.mysql.INTEGER(unsigned=True),
    "mysql",
    "mariadb",
)


class Status(IntEnum):
    """Status Enum."""

    UNSUBMITTED = -4
    CREATED = -3
    UPLOADED = -2
    PENDING = -1
    READY = 0


class _BinaryBase(TypeDecorator[str]):
    cache_ok = True

    def process_bind_param(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> bytes | None:
        if value is None:
            return None
        return value.encode()

    def process_result_value(
        self,
        value: bytes | None,
        dialect: Dialect,
    ) -> str | None:
        if value is None:
            return None
        return value.decode()


class _LargeBinary(_BinaryBase):
    impl = LargeBinary


class _Timestamp(TypeDecorator[Timestamp]):
    cache_ok = True
    impl = BINARY

    def process_bind_param(
        self,
        value: Timestamp | None,
        dialect: Dialect,
    ) -> bytes | None:
        if value is None:
            return None
        return value.totimestampformat().encode()

    def process_result_value(
        self,
        value: bytes | None,
        dialect: Dialect,
    ) -> Timestamp | None:
        if value is None:
            return None
        return Timestamp.set_timestamp(value.decode())


_UuidType = Union[str, UUID]


class _Uuid(TypeDecorator[_UuidType]):
    """Compatibility layer for old data."""

    cache_ok = True
    impl = VARBINARY

    def process_bind_param(
        self,
        value: _UuidType | None,
        dialect: Dialect,
    ) -> bytes | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            value = str(value)
        return value.encode()

    def process_result_value(
        self,
        value: bytes | None,
        dialect: Dialect,
    ) -> _UuidType | None:
        if value is None:
            return None
        value_s = value.decode()
        try:
            return UUID(value_s)
        except (TypeError, ValueError):
            return value_s


class _VarBinary(_BinaryBase):
    cache_ok = True
    impl = VARBINARY


class _TableBase(MappedAsDataclass, DeclarativeBase):
    pass


class Diff(_TableBase):
    """Diffs table interface."""

    __tablename__ = "diffs"
    __table_args__ = (
        Index("ix_diffs_rev", "project", "lang", "rev_id", unique=True),
        Index(
            "ix_diffs_page",
            "project",
            "lang",
            "page_namespace",
            "page_title",
        ),
        Index("ix_diffs_rev_time", "project", "lang", "rev_timestamp"),
        _CREATE_TABLE_ARGS,
    )

    diff_id: Mapped[int] = mapped_column(
        UnsignedInteger,
        init=False,
        primary_key=True,
    )
    project: Mapped[str] = mapped_column(_VarBinary(20))
    lang: Mapped[str] = mapped_column(_VarBinary(20))
    page_namespace: Mapped[int]
    page_title: Mapped[str] = mapped_column(_VarBinary(255))
    rev_id: Mapped[int] = mapped_column(UnsignedInteger)
    rev_parent_id: Mapped[int] = mapped_column(UnsignedInteger)
    rev_timestamp: Mapped[Timestamp] = mapped_column(_Timestamp(14))
    rev_user_text: Mapped[str] = mapped_column(_VarBinary(255))
    submission_id: Mapped[_UuidType | None] = mapped_column(
        _Uuid(36),
        init=False,
        index=True,
        unique=True,
    )
    status: Mapped[int] = mapped_column(TinyInt, index=True)
    status_timestamp: Mapped[Timestamp | None] = mapped_column(
        _Timestamp(14),
        init=False,
    )
    status_user_text: Mapped[str | None] = mapped_column(
        _VarBinary(255),
        init=False,
    )

    sources: Mapped[list[Source]] = relationship(
        lazy="joined",
        passive_deletes=True,
        init=False,
    )


class Source(_TableBase):
    """Report sources table interface."""

    __tablename__ = "report_sources"
    __table_args__ = _CREATE_TABLE_ARGS

    source_id: Mapped[int] = mapped_column(
        UnsignedInteger,
        init=False,
        primary_key=True,
    )
    submission_id: Mapped[_Uuid] = mapped_column(
        ForeignKey(
            "diffs.submission_id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    description: Mapped[str] = mapped_column(_LargeBinary)
    url: Mapped[str | None] = mapped_column(_LargeBinary)
    percent: Mapped[float] = mapped_column(UnsignedFloat)


def add_revision(
    *,
    session: _Session,
    page: Page,
    rev_id: int,
    rev_parent_id: int,
    rev_timestamp: Timestamp,
    rev_user_text: str,
) -> None:
    """Add new revision to the database."""
    diff = Diff(
        project=page.site.family.name,
        lang=page.site.code,
        page_namespace=page.namespace().id,
        page_title=page.title(underscore=True, with_ns=False),
        rev_id=rev_id,
        rev_parent_id=rev_parent_id,
        rev_timestamp=rev_timestamp,
        rev_user_text=rev_user_text,
        status=Status.UNSUBMITTED.value,
    )
    session.add(diff)


def create_tables() -> None:
    """Create database tables."""
    _TableBase.metadata.create_all(_ENGINE, checkfirst=True)


def diffs_by_status(
    session: _Session,
    status: list[Status],
    /,
) -> Sequence[Diff]:
    """Get records with a specified status."""
    stmt = select(Diff).where(Diff.status.in_([s.value for s in status]))
    return session.scalars(stmt).unique().all()


def remove_revision(session: _Session, site: APISite, rev_id: int, /) -> None:
    """Remove revision from the database."""
    stmt = delete(Diff).where(
        and_(
            Diff.project == site.family.name,
            Diff.lang == site.code,
            Diff.rev_id == rev_id,
        )
    )
    session.execute(stmt)


def remove_submission(session: _Session, submission_id: UUID, /) -> None:
    """Remove submission from the database."""
    stmt = delete(Diff).where(Diff.submission_id == str(submission_id))
    session.execute(stmt)
