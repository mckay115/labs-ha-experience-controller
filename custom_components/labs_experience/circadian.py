"""Daypart and circadian lighting curve computation.

Dayparts are clock-based labels (morning/day/evening/night) used for
state gating and defaults; the circadian curve itself follows the sun's
elevation so color temperature and brightness drift continuously through
the day, falling back to daypart estimates if the sun entity is missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from homeassistant.core import HomeAssistant

from .const import Daypart

SUN_ENTITY = "sun.sun"

# Sun elevation mapped linearly onto the curve: below civil twilight is
# fully "night", above 30 degrees is fully "day".
_ELEVATION_FLOOR = -6.0
_ELEVATION_CEILING = 30.0

_DAYPART_FALLBACK_FACTOR = {
    Daypart.NIGHT: 0.0,
    Daypart.EVENING: 0.25,
    Daypart.MORNING: 0.6,
    Daypart.DAY: 1.0,
}


@dataclass(slots=True)
class DaypartBoundaries:
    """Local start times of each daypart; night wraps midnight."""

    morning: time
    day: time
    evening: time
    night: time

    @classmethod
    def from_strings(
        cls, morning: str, day: str, evening: str, night: str
    ) -> DaypartBoundaries:
        return cls(
            morning=time.fromisoformat(morning),
            day=time.fromisoformat(day),
            evening=time.fromisoformat(evening),
            night=time.fromisoformat(night),
        )


def compute_daypart(now: time, boundaries: DaypartBoundaries) -> Daypart:
    if boundaries.morning <= now < boundaries.day:
        return Daypart.MORNING
    if boundaries.day <= now < boundaries.evening:
        return Daypart.DAY
    if boundaries.evening <= now < boundaries.night:
        return Daypart.EVENING
    return Daypart.NIGHT


def sun_factor(hass: HomeAssistant) -> float | None:
    """0.0 (deep night) .. 1.0 (full day) from sun elevation, if known."""
    sun = hass.states.get(SUN_ENTITY)
    if sun is None:
        return None
    elevation = sun.attributes.get("elevation")
    if elevation is None:
        return None
    span = _ELEVATION_CEILING - _ELEVATION_FLOOR
    return min(1.0, max(0.0, (float(elevation) - _ELEVATION_FLOOR) / span))


def circadian_targets(
    hass: HomeAssistant,
    daypart: Daypart,
    *,
    min_kelvin: int,
    max_kelvin: int,
    min_brightness: int,
    max_brightness: int,
) -> tuple[int, int]:
    """Return (kelvin, brightness_pct) for right now."""
    factor = sun_factor(hass)
    if factor is None:
        factor = _DAYPART_FALLBACK_FACTOR[daypart]
    kelvin = round(min_kelvin + factor * (max_kelvin - min_kelvin))
    brightness = round(min_brightness + factor * (max_brightness - min_brightness))
    return kelvin, brightness
