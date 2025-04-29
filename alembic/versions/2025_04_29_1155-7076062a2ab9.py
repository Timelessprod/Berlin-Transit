"""Create vehicles & vehicle_positions tables

Revision ID: 7076062a2ab9
Revises: 
Create Date: 2025-04-29 11:55:10.699738

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7076062a2ab9'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enum type explicitly
    op.execute("""
            CREATE TYPE line_product_enum AS ENUM (
                'BUS', 'SUBWAY', 'TRAMWAY', 'SUBURBAN', 'FERRY', 'EXPRESS', 'REGIONAL'
            );
        """)

    # Create partitioned 'vehicles' table
    op.execute("""
               CREATE TABLE vehicles
               (
                   id           UUID              NOT NULL DEFAULT gen_random_uuid(),
                   trip_id      TEXT              NOT NULL,
                   line_product line_product_enum NOT NULL,
                   line_name    TEXT              NOT NULL,
                   partition_dt DATE              NOT NULL,
                   PRIMARY KEY (id, partition_dt)
               ) PARTITION BY RANGE (partition_dt);
               """)
    # Create partitioned 'vehicle_positions' table
    op.execute("""
               CREATE TABLE vehicle_positions
               (
                   vehicle_id   UUID            NOT NULL,
                   timestamp    TIMESTAMP       NOT NULL,
                   latitude     NUMERIC(38, 18) NOT NULL,
                   longitude    NUMERIC(38, 18) NOT NULL,
                   partition_dt DATE            NOT NULL,
                   PRIMARY KEY (vehicle_id, timestamp, partition_dt),
                   FOREIGN KEY (vehicle_id, partition_dt) REFERENCES vehicles (id, partition_dt) ON DELETE CASCADE
               ) PARTITION BY RANGE (partition_dt);
               """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS vehicle_positions CASCADE;")
    op.execute("DROP TABLE IF EXISTS vehicles CASCADE;")
    op.execute("DROP TYPE IF EXISTS line_product_enum;")
