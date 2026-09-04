import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    marketer = "marketer"
    foreman = "foreman"
    owner = "owner"


class PostMode(str, enum.Enum):
    trend = "trend"
    idea = "idea"
    voice = "voice"


class PostStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    published = "published"
    rejected = "rejected"


class TrendStatus(str, enum.Enum):
    unused = "unused"
    used = "used"
    planned = "planned"


class Platform(str, enum.Enum):
    vk = "vk"
    telegram = "telegram"
    shorts = "shorts"


class RubricCode(str, enum.Enum):
    video_clip = "video_clip"
    layout = "layout"
    horror = "horror"
    done = "done"
    expertise = "expertise"
    battle = "battle"
    lifehack = "lifehack"
    team = "team"
    status = "status"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    posts: Mapped[list["Post"]] = relationship(
        back_populates="author",
        foreign_keys="Post.author_id",
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    mode: Mapped[PostMode] = mapped_column(Enum(PostMode))
    rubric: Mapped[Optional[RubricCode]] = mapped_column(Enum(RubricCode), nullable=True)
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus), default=PostStatus.draft
    )
    source_transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_idea: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    facts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    content_vk: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_tg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_shorts: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hashtags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    approved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    vk_post_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    client_request_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    author: Mapped["User"] = relationship(
        back_populates="posts",
        foreign_keys=[author_id],
    )
    approver: Mapped[Optional["User"]] = relationship(
        foreign_keys=[approved_by],
    )
    media: Mapped[list["Media"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    metrics: Mapped[list["Metric"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    generation_logs: Mapped[list["GenerationLog"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    telegram_file_id: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(16), default="photo")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=True)

    post: Mapped["Post"] = relationship(back_populates="media")


class Rubric(Base):
    __tablename__ = "rubrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[RubricCode] = mapped_column(Enum(RubricCode), unique=True)
    emoji: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    trigger_audience: Mapped[str] = mapped_column(Text)
    cta_template: Mapped[str] = mapped_column(Text)
    frequency_hint: Mapped[str] = mapped_column(Text)
    generation_prompt: Mapped[str] = mapped_column(Text)
    min_chars: Mapped[int] = mapped_column(Integer)
    max_chars: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Trend(Base):
    __tablename__ = "trends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    source_competitor: Mapped[str] = mapped_column(Text)
    original_topic: Mapped[str] = mapped_column(Text)
    er_original: Mapped[float] = mapped_column(Float)
    rubric: Mapped[RubricCode] = mapped_column(Enum(RubricCode))
    trigger_text: Mapped[str] = mapped_column(Text)
    adaptation_note: Mapped[str] = mapped_column(Text)
    status: Mapped[TrendStatus] = mapped_column(Enum(TrendStatus), default=TrendStatus.unused)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    used_post_id: Mapped[Optional[int]] = mapped_column(ForeignKey("posts.id"), nullable=True)


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    platform: Mapped[Platform] = mapped_column(Enum(Platform))
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    reposts: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    er: Mapped[float] = mapped_column(Float, default=0.0)
    collection_point: Mapped[str] = mapped_column(String(8))
    collected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    post: Mapped["Post"] = relationship(back_populates="metrics")


class GenerationLog(Base):
    __tablename__ = "generation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[Optional[int]] = mapped_column(ForeignKey("posts.id"), nullable=True)
    operation: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(Text)
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_rub: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    post: Mapped[Optional["Post"]] = relationship(back_populates="generation_logs")
