# app/db/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

Base = declarative_base()

class SensorPacket(Base):
    __tablename__ = 'monitoring_sensorpacket'
    id = Column(Integer, primary_key=True)
    seq = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    alerta = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    panels = relationship("SensorPanel", back_populates="packet", cascade="all, delete-orphan")

class SensorPanel(Base):
    __tablename__ = 'monitoring_sensorpanel'
    id = Column(Integer, primary_key=True)
    sample_id = Column(Integer, nullable=False)
    soil_raw = Column(Integer)
    soil_pct = Column(Integer)
    tilt = Column(Integer)
    vib_pulse = Column(Integer)
    vib_hit = Column(Integer)
    packet_id = Column(Integer, ForeignKey('monitoring_sensorpacket.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    packet = relationship("SensorPacket", back_populates="panels")
