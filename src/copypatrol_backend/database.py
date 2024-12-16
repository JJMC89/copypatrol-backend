from __future__ import annotations

import datetime
import operator
import os
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Self, TypeVar, Union
from uuid import UUID

import pywikibot
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
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    relationship,
    sessionmaker,
)

from copypatrol_backend import wiki


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from pywikibot.site import APISite
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import InstrumentedAttribute, Session
    from sqlalchemy.sql.expression import ColumnElement


SidType = Union[str, UUID]


CREATE_TABLE_ARGS = {
    "mysql_engine": "InnoDB",
    "mariadb_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mariadb_charset": "utf8mb4",
}


TinyInt = Integer().with_variant(
    sqlalchemy.dialects.mysql.TINYINT(),  # type: ignore[no-untyped-call]
    "mysql",
    "mariadb",
)
UnsignedFloat = Float().with_variant(
    sqlalchemy.dialects.mysql.FLOAT(unsigned=True),  # type: ignore[no-untyped-call]  # noqa: E501
    "mysql",
    "mariadb",
)
UnsignedInteger = Integer().with_variant(
    sqlalchemy.dialects.mysql.INTEGER(unsigned=True),  # type: ignore[no-untyped-call]  # noqa: E501
    "mysql",
    "mariadb",
)


class Status(IntEnum):
    UNKNOWN = -99
    UNSUBMITTED = -4
    CREATED = -3
    UPLOADED = -2
    PENDING = -1
    READY = 0
    FIXED = 1
    NO_ACTION = 2


class BinaryDecoratorBase(TypeDecorator[str]):
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


class LargeBinaryDecorator(BinaryDecoratorBase):
    impl = LargeBinary


class StatusDecorator(TypeDecorator[Status]):
    cache_ok = True
    impl = TinyInt

    def process_bind_param(
        self,
        value: Status | None,
        dialect: Dialect,
    ) -> int:
        assert value is not None
        return value.value

    def process_result_value(
        self,
        value: int | None,
        dialect: Dialect,
    ) -> Status:
        assert value is not None
        return Status(value)


class SidDecorator(TypeDecorator[SidType]):
    cache_ok = True
    impl = VARBINARY

    def process_bind_param(
        self,
        value: SidType | None,
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
    ) -> SidType | None:
        if value is None:
            return None
        value_s = value.decode()
        try:
            return UUID(value_s)
        except (TypeError, ValueError):
            return value_s


class TimestampDecorator(TypeDecorator[Timestamp]):
    cache_ok = True
    impl = BINARY

    def process_bind_param(
        self,
        value: Timestamp | None,
        dialect: Dialect,
    ) -> bytes:
        assert value is not None
        ret = value.totimestampformat().encode()
        assert isinstance(ret, bytes)
        return ret

    def process_result_value(
        self,
        value: bytes | None,
        dialect: Dialect,
    ) -> Timestamp:
        assert value is not None
        return Timestamp.set_timestamp(value.decode())


class VarBinaryDecorator(BinaryDecoratorBase):
    cache_ok = True
    impl = VARBINARY


class TableBase(MappedAsDataclass, DeclarativeBase):
    pass


class DiffMixin(MappedAsDataclass):
    project: Mapped[str] = mapped_column(VarBinaryDecorator(20))
    lang: Mapped[str] = mapped_column(VarBinaryDecorator(20))
    page_namespace: Mapped[int] = mapped_column()
    page_title: Mapped[str] = mapped_column(VarBinaryDecorator(255))
    rev_id: Mapped[int] = mapped_column(UnsignedInteger)
    rev_parent_id: Mapped[int] = mapped_column(UnsignedInteger)
    rev_timestamp: Mapped[Timestamp] = mapped_column(TimestampDecorator(14))
    rev_user_text: Mapped[str] = mapped_column(VarBinaryDecorator(255))
    status: Mapped[Status] = mapped_column(
        StatusDecorator,
        index=True,
        default=Status.UNSUBMITTED,
    )
    status_timestamp: Mapped[Timestamp] = mapped_column(
        TimestampDecorator(14),
        default_factory=Timestamp.utcnow,
        onupdate=Timestamp.utcnow,
    )

    @property
    def page(self) -> pywikibot.Page:
        namespace = self.site.namespaces[self.page_namespace]
        return pywikibot.Page(
            self.site,
            f"{namespace.canonical_name}:{self.page_title}",
        )

    @property
    def site(self) -> APISite:
        return pywikibot.Site(self.lang, self.project)

    def update_page(self) -> int | None:
        revs = wiki.load_revisions(self.site, [self.rev_id])
        if revs is None:
            return None
        rev = revs[self.rev_id]
        self.page_namespace = rev.ns
        page = pywikibot.Page(self.site, rev.title)
        self.page_title = page.title(underscore=True, with_ns=False)
        assert isinstance(rev.pageid, int)
        return rev.pageid


class QueuedDiff(TableBase, DiffMixin, kw_only=True):
    __tablename__ = "diffs_queue"
    __table_args__ = (
        Index("ix_diffs_queue_rev", "project", "lang", "rev_id", unique=True),
        CREATE_TABLE_ARGS,
    )

    diff_id: Mapped[int] = mapped_column(
        "diff_queue_id",
        UnsignedInteger,
        init=False,
        primary_key=True,
    )
    submission_id: Mapped[UUID | None] = mapped_column(
        SidDecorator(36),
        init=False,
        index=True,
        unique=True,
    )


class Diff(TableBase, DiffMixin, kw_only=True):
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
        CREATE_TABLE_ARGS,
    )

    diff_id: Mapped[int] = mapped_column(
        UnsignedInteger,
        init=False,
        primary_key=True,
    )
    submission_id: Mapped[SidType] = mapped_column(
        SidDecorator(36),
        index=True,
        unique=True,
    )
    status_user_text: Mapped[str | None] = mapped_column(
        VarBinaryDecorator(255),
        init=False,
    )

    sources: Mapped[list[Source]] = relationship(
        lazy="joined",
        passive_deletes=True,
    )

    @classmethod
    def from_queueddiff(cls, diff: QueuedDiff, sources: list[Source]) -> Self:
        assert diff.submission_id is not None
        return cls(
            submission_id=diff.submission_id,
            project=diff.project,
            lang=diff.lang,
            page_namespace=diff.page_namespace,
            page_title=diff.page_title,
            rev_id=diff.rev_id,
            rev_parent_id=diff.rev_parent_id,
            rev_timestamp=diff.rev_timestamp,
            rev_user_text=diff.rev_user_text,
            status=Status.READY,
            sources=sources,
        )


class Source(TableBase, kw_only=True):
    __tablename__ = "report_sources"
    __table_args__ = CREATE_TABLE_ARGS

    source_id: Mapped[int] = mapped_column(
        UnsignedInteger,
        init=False,
        primary_key=True,
    )
    submission_id: Mapped[SidType] = mapped_column(
        ForeignKey(
            "diffs.submission_id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        )
    )
    description: Mapped[str] = mapped_column(LargeBinaryDecorator)
    url: Mapped[str | None] = mapped_column(LargeBinaryDecorator)
    percent: Mapped[float] = mapped_column(UnsignedFloat)


DiffT = TypeVar("DiffT", bound=DiffMixin)


def add_revision(
    *,
    session: Session,
    page: pywikibot.Page,
    rev_id: int,
    rev_parent_id: int,
    rev_timestamp: str,
    rev_user_text: str,
) -> None:
    diff_stmt = select(Diff).where(
        Diff.project == page.site.family.name,
        Diff.lang == page.site.code,
        Diff.rev_id == rev_id,
    )
    if session.scalars(diff_stmt).unique().one_or_none():
        return  # pragma: no cover
    diff = QueuedDiff(
        project=page.site.family.name,
        lang=page.site.code,
        page_namespace=page.namespace().id,
        page_title=page.title(underscore=True, with_ns=False),
        rev_id=rev_id,
        rev_parent_id=rev_parent_id,
        rev_timestamp=Timestamp.set_timestamp(rev_timestamp),
        rev_user_text=rev_user_text,
    )
    session.add(diff)


def _create_engine(echo: bool = False) -> Engine:
    charset = os.environ.get("CPB_DB_DEFAULT_CHARACTER_SET")
    url = URL.create(
        drivername=os.environ["CPB_DB_DRIVERNAME"],
        username=os.environ.get("CPB_DB_USERNAME"),
        password=os.environ.get("CPB_DB_PASSWORD"),
        host=os.environ.get("CPB_DB_HOST"),
        port=int(p) if (p := os.environ.get("CPB_DB_PORT")) else None,
        database=os.environ.get("CPB_DB_DATABASE"),
        query={"charset": charset} if charset else {},
    )
    return create_engine(url, echo=echo)


def create_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=_create_engine(), expire_on_commit=False)


def create_tables() -> None:
    TableBase.metadata.create_all(_create_engine(echo=True), checkfirst=True)


def diffs_by_status(
    session: Session,
    table_class: type[DiffT],
    status: Status | list[Status],
    /,
    *,
    delta: datetime.timedelta | None = None,
    op: Callable[
        [InstrumentedAttribute[Any], InstrumentedAttribute[Any]],
        ColumnElement[bool],
    ] = operator.le,
    limit: int | None = None,
) -> Sequence[DiffT]:
    if isinstance(status, Status):
        status = [status]
    if delta is None:
        delta = datetime.timedelta()
    stmt = (
        select(table_class)
        .where(
            table_class.status.in_(status),
            op(table_class.status_timestamp, Timestamp.utcnow() + delta),
        )
        .order_by(table_class.rev_timestamp.desc())
        .limit(limit)
    )
    return session.scalars(stmt).unique().all()


def queued_diff_from_submission_id(
    session: Session,
    submission_id: UUID,
    /,
) -> QueuedDiff | None:
    stmt = select(QueuedDiff).where(QueuedDiff.submission_id == submission_id)
    return session.scalars(stmt).one_or_none()


def diff_count(
    session: Session,
    table_class: type[DiffT],
    /,
    *,
    site: APISite | None = None,
    status: Status | list[Status] | None = None,
) -> int:
    stmt = select(func.count()).select_from(table_class)
    if site is not None:
        stmt = stmt.where(
            table_class.project == site.family.name,
            table_class.lang == site.code,
        )
    if status is not None:
        if isinstance(status, Status):
            status = [status]
        stmt = stmt.where(table_class.status.in_(status))
    res = session.scalar(stmt)
    assert res is not None
    return res


def max_diff_timestamp(
    session: Session,
    table_class: type[DiffT],
    /,
    *,
    status: Status | list[Status] | None = None,
) -> Timestamp:
    stmt = select(func.max(table_class.status_timestamp))
    if status is not None:
        if isinstance(status, Status):
            status = [status]
        stmt = stmt.where(table_class.status.in_(status))
    return session.scalar(stmt)


def min_diff_timestamp(
    session: Session,
    table_class: type[DiffT],
    /,
    *,
    status: Status | list[Status] | None = None,
) -> Timestamp:
    stmt = select(func.min(table_class.status_timestamp))
    if status is not None:
        if isinstance(status, Status):
            status = [status]
        stmt = stmt.where(table_class.status.in_(status))
    return session.scalar(stmt)
