"""Solar position, shadow geometry, and chronolocation.

Sun geometry is one of the few cheap clues that is causally independent of the
visual match. It needs a date and a time; without both, it cannot discriminate.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone


def _julian_day(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    y, m = dt.year, dt.month
    d = dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def solar_position(lat_deg: float, lon_deg: float, dt: datetime) -> tuple[float, float, float]:
    """Return (azimuth_deg, elevation_deg, declination_deg) using NOAA's approximation."""
    jd = _julian_day(dt)
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    m_rad = math.radians(m)
    c = (
        math.sin(m_rad) * (1.914602 - t * (0.004817 + 0.000014 * t))
        + math.sin(2 * m_rad) * (0.019993 - 0.000101 * t)
        + math.sin(3 * m_rad) * 0.000289
    )
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    obliquity = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    obliquity += 0.00256 * math.cos(math.radians(omega))
    declination = math.degrees(
        math.asin(math.sin(math.radians(obliquity)) * math.sin(math.radians(app_long)))
    )

    # Equation of time (minutes).
    y = math.tan(math.radians(obliquity / 2)) ** 2
    eq_time = 4 * math.degrees(
        y * math.sin(2 * math.radians(l0))
        - 2 * e * math.sin(m_rad)
        + 4 * e * y * math.sin(m_rad) * math.cos(2 * math.radians(l0))
        - 0.5 * y * y * math.sin(4 * math.radians(l0))
        - 1.25 * e * e * math.sin(2 * m_rad)
    )
    utc_minutes = dt.astimezone(timezone.utc).hour * 60 + dt.astimezone(timezone.utc).minute
    true_solar_time = (utc_minutes + eq_time + 4 * lon_deg) % 1440
    hour_angle = true_solar_time / 4 - 180

    lat = math.radians(lat_deg)
    dec = math.radians(declination)
    ha = math.radians(hour_angle)
    cos_zenith = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(ha)
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith = math.degrees(math.acos(cos_zenith))
    elevation = 90.0 - zenith
    # Azimuth from north, clockwise.
    sin_az = -math.sin(ha) * math.cos(dec)
    cos_az = math.sin(dec) * math.cos(lat) - math.cos(dec) * math.sin(lat) * math.cos(ha)
    azimuth = (math.degrees(math.atan2(sin_az, cos_az)) + 360.0) % 360.0
    return azimuth, elevation, declination


def shadow_ratio(elevation_deg: float) -> float | None:
    """Shadow length / object height for a vertical object."""
    if elevation_deg <= 1.0:
        return None
    return 1.0 / math.tan(math.radians(elevation_deg))


def latitude_band_from_shadow(
    shadow_ratio_value: float,
    declination_deg: float,
    hour_angle_deg: float,
) -> list[float]:
    """Latitudes consistent with a shadow ratio at a given declination/hour angle.

    Returns up to two latitudes (the equation is symmetric about the subsolar
    point). This is a band, not a point: local terrain and object tilt matter.
    """
    elevation = math.atan(1.0 / max(1e-9, shadow_ratio_value))
    a = math.sin(math.radians(declination_deg))
    b = math.cos(math.radians(declination_deg)) * math.cos(math.radians(hour_angle_deg))
    r = math.hypot(a, b)
    if r < 1e-9 or abs(math.sin(elevation)) > r:
        return []
    base = math.atan2(a, b)
    delta = math.acos(max(-1.0, min(1.0, math.sin(elevation) / r)))
    return [math.degrees(base + delta), math.degrees(base - delta)]


def hour_angle(dt: datetime, lon_deg: float) -> float:
    """Approximate solar hour angle in degrees."""
    # shortcut: equation of time is ignored; replace for sub-degree shadow work.
    utc = dt.astimezone(timezone.utc)
    minutes = utc.hour * 60 + utc.minute + utc.second / 60
    # Equation of time is already embedded in solar_position; use a local
    # approximation good to a few minutes for shadow work.
    solar_minutes = (minutes + 4 * lon_deg) % 1440
    return solar_minutes / 4 - 180


def night_at(lat_deg: float, lon_deg: float, dt: datetime) -> bool:
    _, elevation, _ = solar_position(lat_deg, lon_deg, dt)
    return elevation < -6.0
