from datetime import datetime
from typing import Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import Column
from sqlmodel import Field, SQLModel


class Sign(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sign_type: str = Field(index=True)
    latitude: float
    longitude: float
    location: Any = Field(sa_column=Column(Geometry(geometry_type="POINT", srid=4326)))
    created_at: datetime = Field(default_factory=datetime.utcnow)
