from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    Boolean,
    ForeignKey,
    create_engine,
    UniqueConstraint,
    inspect,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from datetime import datetime
from config import DATABASE_URL

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    notifications_enabled = Column(Boolean, default=True)
    language = Column(String(5), default="en", nullable=False)
    
    categories = relationship("Category", back_populates="owner")
    items = relationship("Item", back_populates="owner")
    shared_categories = relationship("SharedCategory", back_populates="user")
    tags = relationship("Tag", back_populates="user")
    locations = relationship("Location", back_populates="user")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"))
    sharing_type = Column(String(20), default="private")  # private, view_only, collaborative
    share_link = Column(String(100), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    date = Column(DateTime, nullable=True)
    
    owner = relationship("User", back_populates="categories")
    items = relationship("Item", back_populates="category")
    shared_users = relationship("SharedCategory", back_populates="category")

class Item(Base):
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    owner_id = Column(Integer, ForeignKey("users.id"))
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    tags = Column(Text)
    price = Column(Float, nullable=True)
    location_type = Column(String(50), nullable=True)
    location_value = Column(String(200), nullable=True)
    date = Column(DateTime, nullable=True)
    date_from = Column(DateTime, nullable=True)
    date_to = Column(DateTime, nullable=True)
    url = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    photo_file_id = Column(String(200), nullable=True)
    product_type = Column(String(50), default="вещь")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notifications_enabled = Column(Boolean, default=True)
    
    category = relationship("Category", back_populates="items")
    owner = relationship("User", back_populates="items")
    location = relationship("Location")

class SharedCategory(Base):
    __tablename__ = "shared_categories"
    
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    can_edit = Column(Boolean, default=False)
    shared_at = Column(DateTime, default=datetime.utcnow)
    
    category = relationship("Category", back_populates="shared_users")
    user = relationship("User", back_populates="shared_categories")

    __table_args__ = (
        UniqueConstraint('category_id', 'user_id', name='uix_shared_category_user'),
    )

class Tag(Base):
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    usage_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="tags")

    __table_args__ = (
        UniqueConstraint('name', 'user_id', name='uix_tag_name_user'),
    )

class Location(Base):
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True)
    location_type = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    usage_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="locations")

    __table_args__ = (
        UniqueConstraint('location_type', 'name', 'user_id', name='uix_location_type_name_user'),
    )

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ensure_language_column)

async def get_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def ensure_language_column(connection):
    inspector = inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'language' not in columns:
        connection.execute(
            text("ALTER TABLE users ADD COLUMN language VARCHAR(5) NOT NULL DEFAULT 'en'")
        )
