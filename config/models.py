"""
SQLAlchemy ORM Models
"""

from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    pin = Column(String, nullable=False)  # This stores the hash
    first_name = Column(String)
    last_name = Column(String)
    timezone = Column(String, default='America/Denver')
    created_at = Column(DateTime, server_default=func.now())
    last_checked = Column(DateTime)

    # Relationships
    monitoring_jobs = relationship("MonitoringJob", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

class Resort(Base):
    __tablename__ = 'resorts'

    resort_id = Column(Integer, primary_key=True)
    resort_name = Column(String, unique=True, nullable=False)
    resort_url = Column(String, nullable=False)
    status = Column(String, default='active')
    available_color = Column(String)
    unavailable_color = Column(String)
    check_interval = Column(Integer, default=10)

    # Relationships
    monitoring_jobs = relationship("MonitoringJob", back_populates="resort")
    check_logs = relationship("CheckLog", back_populates="resort")

class MonitoringJob(Base):
    __tablename__ = 'monitoring_jobs'

    job_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    resort_id = Column(Integer, ForeignKey('resorts.resort_id'), nullable=False)
    target_date = Column(Date, nullable=False) # Stored as YYYY-MM-DD string in SQLite usually, but SQLAlchemy handles Date type
    status = Column(String, default='active')
    priority = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    last_checked = Column(DateTime)
    success_count = Column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="monitoring_jobs")
    resort = relationship("Resort", back_populates="monitoring_jobs")
    notifications = relationship("Notification", back_populates="job", cascade="all, delete-orphan")

class Notification(Base):
    __tablename__ = 'notifications'

    notification_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    job_id = Column(Integer, ForeignKey('monitoring_jobs.job_id'), nullable=False)
    sent_at = Column(DateTime, server_default=func.now())
    delivery_status = Column(String, default='sent')
    resort_name = Column(String)
    available_date = Column(Date) # Or String if we want to match exact format

    # Relationships
    user = relationship("User", back_populates="notifications")
    job = relationship("MonitoringJob", back_populates="notifications")

class CheckLog(Base):
    __tablename__ = 'check_logs'

    log_id = Column(Integer, primary_key=True)
    resort_id = Column(Integer, ForeignKey('resorts.resort_id'), nullable=False)
    check_timestamp = Column(DateTime, server_default=func.now())
    status = Column(String, nullable=False)
    response_time = Column(Integer)
    error_message = Column(Text)
    availability_found = Column(Boolean, default=False)

    # Relationships
    resort = relationship("Resort", back_populates="check_logs")
