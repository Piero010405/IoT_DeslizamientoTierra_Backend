# app/db/models.py

from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

Base = declarative_base()

# ------------------------------
#   SENSOR PACKET  (CABECERA)
# ------------------------------
class SensorPacket(Base):
    __tablename__ = 'monitoring_sensorpacket'

    id = Column(Integer, primary_key=True)
    seq = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    alerta = Column(Boolean, nullable=False, default=False)

    # IMPORTANTE: deben tener server_default y nullable=False para coincidir con Django
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    samples = relationship("SensorSample", back_populates="packet", cascade="all, delete-orphan")


# ------------------------------
#   SENSOR SAMPLE  (DETALLE)
# ------------------------------
class SensorSample(Base):
    __tablename__ = 'monitoring_sensorsample'

    id = Column(Integer, primary_key=True)
    sample_id = Column(Integer, nullable=False)

    soil_raw = Column(Integer)
    soil_pct = Column(Float)
    tilt = Column(Boolean)
    vib_pulse = Column(Integer)
    vib_hit = Column(Boolean)

    packet_id = Column(Integer, ForeignKey('monitoring_sensorpacket.id', ondelete='CASCADE'), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    packet = relationship("SensorPacket", back_populates="samples")
