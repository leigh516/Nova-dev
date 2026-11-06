"""서비스 전용 DB. 각 서비스는 자기 스키마만 소유한다(공유 DB·교차 조인 금지).

로컬/테스트: SQLite 파일 또는 메모리 · k3s: MariaDB 서비스별 스키마·전용 계정 (DATABASE_URL).
"""
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from . import runtime

from sqlalchemy import JSON, Boolean, DateTime, Integer, MetaData, String, Text, UniqueConstraint, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, registry, sessionmaker
from sqlalchemy.pool import StaticPool

log = logging.getLogger("nova.db")

# 제약 · 인덱스 이름 규칙(ADR-011). DB 가 임의로 지은 이름은 DB 마다 달라 마이그레이션으로 지우거나 바꿀 수 없다.
# 형식은 naming.md §3.1 과 같은 snake_case: <종류>_<표>_<칸…>(여러 칸이면 밑줄로 잇는다).
# CHECK 는 칸으로 이름을 지을 수 없어 name= 을 반드시 준다(없으면 SQLAlchemy 가 오류를 낸다 — 이름 없는 CHECK 를 막는 장치).
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class NovaBase(DeclarativeBase):
    """모든 서비스 Base 의 부모 — `class Base(NovaBase): pass`.

    바로 상속한 클래스(서비스 Base)마다 제약 이름 규칙을 가진 **자기 MetaData · registry** 를 만든다.
    하나를 함께 쓰면 한 프로세스에 여러 서비스(통합 테스트 · 단일 프로세스 실행)가 뜰 때 outbox 표가 부딪힌다."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def __init_subclass__(cls, **kw) -> None:  # noqa: ANN003
        if NovaBase in cls.__bases__:
            if "__tablename__" in cls.__dict__ or "__table__" in cls.__dict__:
                raise TypeError(f"{cls.__name__}: NovaBase 를 바로 상속하는 클래스는 서비스 Base 여야 합니다 — 표 모델은 서비스 Base 를 상속하세요")
            # DeclarativeBase 가 바로 아래 Base 에 해 주는 설정을 서비스 Base 에 다시 한다(MetaData 만 새로)
            cls.metadata = MetaData(naming_convention=NAMING_CONVENTION)
            cls.registry = registry(metadata=cls.metadata)
            cls._sa_registry = cls.registry
            super(DeclarativeBase, cls).__init_subclass__(**kw)
            return
        super().__init_subclass__(**kw)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_now() -> datetime:
    """업무 현지 시각(naive, NOVA_TZ_OFFSET_HOURS 기본 9). 영업시간 · 유효시간 같은 '벽시계' 비교에만 쓴다(저장 · 감사 시각은 utcnow)."""
    return utcnow() + timedelta(hours=runtime.tz_offset_hours())


class Database:
    def __init__(self, service: str, url: str | None = None):
        self.service = service
        # 서비스별 우선: DATABASE_URL_<SERVICE> → 공통 DATABASE_URL → 로컬 SQLite 파일
        specific = "DATABASE_URL_" + service.upper().replace("-", "_")
        url = url or os.getenv(specific) or os.getenv("DATABASE_URL") or f"sqlite:///./data/{service}.db"
        kwargs: dict = {"future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if url in ("sqlite://", "sqlite:///:memory:"):
                kwargs["poolclass"] = StaticPool
            else:
                path = url.replace("sqlite:///", "")
                d = os.path.dirname(path)
                if d:
                    os.makedirs(d, exist_ok=True)
        else:
            # 자원 효율: 서비스당 작은 풀 (uvicorn 단일 워커 기준)
            kwargs.update(pool_size=5, max_overflow=5, pool_pre_ping=True, pool_recycle=1800)
        self.url = url
        self.engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def _pragma(dbapi_conn, _):  # noqa: ANN001
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()

        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    @contextmanager
    def session(self):
        s: Session = self.SessionLocal()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def ping(self) -> bool:
        """DB 에 닿는지 `SELECT 1` 로 본다(준비 확인 /readyz 용). 실패는 예외를 올리지 않고 이유를 로그로 남긴 뒤 False —
        준비 확인은 '닿는가'만 답하면 되고, 예외가 새면 readyz 가 500 이 되어 503(트래픽에서 빼기)과 구분되지 않는다."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:  # noqa: BLE001 — 드라이버마다 예외 종류가 달라 모두 'DB 응답 없음'으로 본다
            first = str(e).splitlines()[0] if str(e) else ""
            log.warning("DB 응답 없음 service=%s — 준비 확인 실패(%s: %s)", self.service, type(e).__name__, first)
            return False

    def create_all(self, base) -> None:
        base.metadata.create_all(self.engine)


def add_infra_tables(Base):  # noqa: N803
    """아웃박스(outbox)와 멱등 소비 기록(processed_event)을 서비스 스키마에 생성한다."""

    class Outbox(Base):
        __tablename__ = "outbox"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="일련번호")
        event_id: Mapped[str] = mapped_column(String(40), unique=True, comment="이벤트 ID(UUIDv7)")
        topic: Mapped[str] = mapped_column(String(120), index=True, comment="토픽")
        key: Mapped[str] = mapped_column(String(80), comment="파티션 키(집계 ID)")
        payload: Mapped[dict] = mapped_column(JSON, comment="봉투 전체(JSON)")
        created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, comment="적재 시각(UTC)")
        sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True, comment="발행 시각 — 비면 미발행")
        attempts: Mapped[int] = mapped_column(Integer, default=0, comment="발행 시도 횟수")
        last_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="마지막 발행 오류")
        is_parked: Mapped[bool] = mapped_column(Boolean, default=False, index=True, comment="독 메시지 격리(재처리 대기)")  # 독 메시지 격리(운영 콘솔에서 재처리)

    class ProcessedEvent(Base):
        __tablename__ = "processed_event"
        # 중복 제거는 (소비자, 중복 제거 키) — 같은 업무 사건이 다른 이벤트 id 로 다시 와도 한 번만(ADR-012 P1).
        # 칸이 빈 옛 행은 UNIQUE 에 걸리지 않고 event_id(기본키)로 판정한다(Contract 전까지)
        __table_args__ = (UniqueConstraint("consumer", "idempotency_key"),)
        event_id: Mapped[str] = mapped_column(String(40), primary_key=True, comment="처리한 이벤트 ID")
        consumer: Mapped[str] = mapped_column(String(80), primary_key=True, comment="소비 서비스")
        topic: Mapped[str] = mapped_column(String(120), comment="토픽")
        # 320 = 기본 키 `{source}:{topic}:{key}:{event_id}` 최대 319(소비자 80 + 토픽 120 + 키 80 + UUID 36 + 구분자 3) — p0004
        idempotency_key: Mapped[str | None] = mapped_column(String(320), nullable=True, comment="중복 제거 키(봉투 idempotency_key)")
        is_ok: Mapped[bool] = mapped_column(Boolean, default=True, comment="처리 성공")
        processed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, comment="처리 시각(UTC)")

    return Outbox, ProcessedEvent
