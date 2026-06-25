"""Geographic primitives."""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

_EARTH_RADIUS_KM = 6371.0088


class GeoPoint(BaseModel):
    """A latitude/longitude coordinate on Earth."""

    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)

    def distance_km(self, other: GeoPoint) -> float:
        """Great-circle distance to another point in kilometers (haversine)."""
        lat1, lng1, lat2, lng2 = map(
            math.radians, (self.lat, self.lng, other.lat, other.lng)
        )
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))
