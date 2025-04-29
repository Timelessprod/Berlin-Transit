import enum
import uuid
from datetime import date, datetime
from typing import List

from sqlalchemy import DECIMAL, Date, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class LineProductEnum(enum.Enum):
    BUS = "bus"
    SUBWAY = "subway"
    TRAMWAY = "tram"
    SUBURBAN = "suburban"  # S-Bahn
    FERRY = "ferry"
    EXPRESS = "express"  # IC/ICE trains
    REGIONAL = "regional"  # Regio trains


class Vehicle(Base):
    """
    Table representing a vehicle, partitioned by day.
    A vehicle is represented by its trip id as the API doesn't provide the actual id of vehicles themselves, thus
    we can have multiple trip_ids which represent the same real-world vehicle.
    """
    __tablename__ = "vehicles"
    __table_args__ = (
        {'postgresql_partition_by': 'RANGE (partition_dt)'}
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )
    trip_id: Mapped[str] = mapped_column(String, nullable=False)
    line_product: Mapped[LineProductEnum] = mapped_column(Enum(LineProductEnum, name="line_product_enum"), nullable=False)
    line_name: Mapped[str] = mapped_column(String, nullable=False)
    partition_dt: Mapped[date] = mapped_column(Date, primary_key=True)

    positions: Mapped[List["VehiclePosition"]] = relationship(
        back_populates="vehicle",
        cascade="all, delete-orphan"
    )


class VehiclePosition(Base):
    """
    Table representing the position of a vehicle at a given time, partitioned by day.
    """
    __tablename__ = "vehicle_positions"
    __table_args__ = (
        {'postgresql_partition_by': 'RANGE (partition_dt)'},
    )

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('vehicles.id', ondelete='CASCADE'),
        primary_key=True
    )
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=False), primary_key=True)
    latitude: Mapped[float] = mapped_column(DECIMAL(38, 18), nullable=False)
    longitude: Mapped[float] = mapped_column(DECIMAL(38, 18), nullable=False)
    partition_dt: Mapped[date] = mapped_column(Date, primary_key=True)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="positions")
