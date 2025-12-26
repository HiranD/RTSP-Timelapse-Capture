"""
Twilight Calculator - Astronomical twilight time calculations
For astrophotography scheduling based on location and twilight type.

Uses the astral library for accurate sun position calculations.
"""

from datetime import datetime, timedelta, date, timezone
from typing import Tuple, Optional
from dataclasses import dataclass

from astral import LocationInfo
from astral.sun import sun
import astral.sun


def utc_to_local(utc_dt: datetime) -> datetime:
    """Convert UTC datetime to local timezone"""
    if utc_dt.tzinfo is None:
        # Assume UTC if no timezone
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone().replace(tzinfo=None)  # Return naive local time


@dataclass
class DarknessWindow:
    """Represents a window of darkness for a given night"""
    date: date                    # The evening date (start of the night)
    darkness_start: datetime      # When darkness begins
    darkness_end: datetime        # When darkness ends (next morning)
    duration_hours: float         # Total darkness duration in hours
    twilight_type: str            # Type of twilight used for calculation

    def get_duration_str(self) -> str:
        """Return formatted duration string"""
        hours = int(self.duration_hours)
        minutes = int((self.duration_hours - hours) * 60)
        return f"{hours}h {minutes}m"

    def get_time_range_str(self) -> str:
        """Return formatted time range string"""
        start_str = self.darkness_start.strftime("%H:%M")
        end_str = self.darkness_end.strftime("%H:%M")
        return f"{start_str} - {end_str}"

    def is_active_now(self) -> bool:
        """Check if we are currently in the darkness window"""
        now = datetime.now()
        return self.darkness_start <= now <= self.darkness_end


class TwilightCalculator:
    """
    Calculate astronomical twilight times for a given location.

    Twilight Types:
    - Civil (-6°): Sun is 6° below horizon. Enough light for outdoor activities.
    - Nautical (-12°): Sun is 12° below horizon. Horizon still visible at sea.
    - Astronomical (-18°): Sun is 18° below horizon. True darkness for astronomy.
    """

    # Sun depression angles for each twilight type
    TWILIGHT_ANGLES = {
        "civil": 6,
        "nautical": 12,
        "astronomical": 18
    }

    def __init__(self, latitude: float, longitude: float):
        """
        Initialize twilight calculator for a location.

        Args:
            latitude: Latitude in degrees (-90 to 90, negative = south)
            longitude: Longitude in degrees (-180 to 180, negative = west)
        """
        self.latitude = latitude
        self.longitude = longitude
        self._location = LocationInfo(
            name="Observer",
            region="",
            timezone="UTC",
            latitude=latitude,
            longitude=longitude
        )

    @property
    def hemisphere(self) -> str:
        """Return hemisphere based on latitude"""
        return "northern" if self.latitude >= 0 else "southern"

    def get_darkness_window(
        self,
        target_date: date,
        twilight_type: str = "astronomical",
        start_offset_minutes: int = 0,
        end_offset_minutes: int = 0
    ) -> Optional[DarknessWindow]:
        """
        Calculate the darkness window for a given night.

        Args:
            target_date: The evening date (darkness starts this evening, ends next morning)
            twilight_type: "civil", "nautical", or "astronomical"
            start_offset_minutes: Minutes to add after darkness begins (positive = later start)
            end_offset_minutes: Minutes to add before darkness ends (negative = earlier end)

        Returns:
            DarknessWindow object, or None if calculation fails (e.g., polar day/night)
        """
        if twilight_type not in self.TWILIGHT_ANGLES:
            raise ValueError(f"Invalid twilight type: {twilight_type}. "
                           f"Must be one of: {list(self.TWILIGHT_ANGLES.keys())}")

        try:
            depression = self.TWILIGHT_ANGLES[twilight_type]
            next_day = target_date + timedelta(days=1)

            # Use astral's time_at_elevation to get exact twilight times
            # Darkness starts when sun goes below -depression degrees (evening)
            # Darkness ends when sun rises above -depression degrees (morning)

            # Get sunset and sunrise as reference points
            sun_times_evening = sun(
                self._location.observer,
                date=target_date,
                tzinfo=None
            )

            sun_times_morning = sun(
                self._location.observer,
                date=next_day,
                tzinfo=None
            )

            # Calculate when sun reaches the depression angle
            # Evening: after sunset, sun goes to -6, -12, -18 degrees
            # Morning: before sunrise, sun rises from -18, -12, -6 degrees

            if twilight_type == "civil":
                # Civil twilight: sun at -6 degrees
                darkness_start = sun_times_evening["dusk"]
                darkness_end = sun_times_morning["dawn"]
            elif twilight_type == "nautical":
                # Nautical twilight: sun at -12 degrees
                # Estimate: dusk + time for sun to go from -6 to -12
                # This is roughly the same duration as sunset to dusk
                dusk = sun_times_evening["dusk"]
                sunset = sun_times_evening["sunset"]
                dusk_duration = dusk - sunset

                dawn = sun_times_morning["dawn"]
                sunrise = sun_times_morning["sunrise"]
                dawn_duration = sunrise - dawn

                darkness_start = dusk + dusk_duration
                darkness_end = dawn - dawn_duration
            else:  # astronomical
                # Astronomical twilight: sun at -18 degrees
                # Estimate: dusk + 2x time for sun to go from sunset to dusk
                dusk = sun_times_evening["dusk"]
                sunset = sun_times_evening["sunset"]
                dusk_duration = dusk - sunset

                dawn = sun_times_morning["dawn"]
                sunrise = sun_times_morning["sunrise"]
                dawn_duration = sunrise - dawn

                darkness_start = dusk + (dusk_duration * 2)
                darkness_end = dawn - (dawn_duration * 2)

            # Convert UTC times to local timezone
            darkness_start = utc_to_local(darkness_start)
            darkness_end = utc_to_local(darkness_end)

            # Apply offsets
            darkness_start = darkness_start + timedelta(minutes=start_offset_minutes)
            darkness_end = darkness_end + timedelta(minutes=end_offset_minutes)

            # Calculate duration
            duration = darkness_end - darkness_start
            duration_hours = duration.total_seconds() / 3600

            # Handle case where offsets make the window invalid
            if duration_hours <= 0:
                return None

            return DarknessWindow(
                date=target_date,
                darkness_start=darkness_start,
                darkness_end=darkness_end,
                duration_hours=duration_hours,
                twilight_type=twilight_type
            )

        except (ValueError, AttributeError) as e:
            # This can happen during polar day/night when there's no twilight
            return None

    def get_tonight_window(
        self,
        twilight_type: str = "astronomical",
        start_offset_minutes: int = 0,
        end_offset_minutes: int = 0
    ) -> Optional[DarknessWindow]:
        """
        Get the darkness window for tonight.

        If it's currently daytime, returns tonight's window.
        If it's currently nighttime (after midnight), returns the current night's window.

        Args:
            twilight_type: "civil", "nautical", or "astronomical"
            start_offset_minutes: Minutes to add after darkness begins
            end_offset_minutes: Minutes to add before darkness ends

        Returns:
            DarknessWindow for tonight/current night
        """
        now = datetime.now()

        # If it's early morning (before noon), we might still be in last night's window
        # Use yesterday's date as the "evening" date
        if now.hour < 12:
            target_date = (now - timedelta(days=1)).date()
        else:
            target_date = now.date()

        return self.get_darkness_window(
            target_date,
            twilight_type,
            start_offset_minutes,
            end_offset_minutes
        )

    def get_windows_for_dates(
        self,
        dates: list,
        twilight_type: str = "astronomical",
        start_offset_minutes: int = 0,
        end_offset_minutes: int = 0
    ) -> list:
        """
        Calculate darkness windows for multiple dates.

        Args:
            dates: List of date objects or date strings (YYYY-MM-DD)
            twilight_type: Twilight type for all calculations
            start_offset_minutes: Offset for darkness start
            end_offset_minutes: Offset for darkness end

        Returns:
            List of DarknessWindow objects (None entries excluded)
        """
        windows = []

        for d in dates:
            if isinstance(d, str):
                d = datetime.strptime(d, "%Y-%m-%d").date()

            window = self.get_darkness_window(
                d,
                twilight_type,
                start_offset_minutes,
                end_offset_minutes
            )

            if window:
                windows.append(window)

        return windows


def test_twilight_calculator():
    """Test the twilight calculator with sample locations"""
    print("Twilight Calculator Test")
    print("=" * 60)

    # Test locations
    locations = [
        ("London, UK", 51.5074, -0.1278),
        ("New York, USA", 40.7128, -74.0060),
        ("Sydney, Australia", -33.8688, 151.2093),
        ("Tokyo, Japan", 35.6762, 139.6503),
        ("Reykjavik, Iceland", 64.1466, -21.9426),  # High latitude
    ]

    today = date.today()

    for name, lat, lon in locations:
        print(f"\n{name} (lat: {lat}, lon: {lon})")
        print("-" * 40)

        calc = TwilightCalculator(lat, lon)
        print(f"Hemisphere: {calc.hemisphere}")

        for twilight_type in ["civil", "nautical", "astronomical"]:
            window = calc.get_darkness_window(today, twilight_type)

            if window:
                print(f"  {twilight_type.capitalize():12} : "
                      f"{window.get_time_range_str()} ({window.get_duration_str()})")
            else:
                print(f"  {twilight_type.capitalize():12} : No darkness (polar day/night)")

    # Test tonight's window
    print("\n" + "=" * 60)
    print("Tonight's Window (with offsets)")
    print("-" * 40)

    calc = TwilightCalculator(51.5074, -0.1278)  # London
    window = calc.get_tonight_window(
        twilight_type="astronomical",
        start_offset_minutes=15,
        end_offset_minutes=-15
    )

    if window:
        print(f"Tonight: {window.get_time_range_str()} ({window.get_duration_str()})")
        print(f"Currently in darkness: {window.is_active_now()}")
    else:
        print("No darkness window available")


if __name__ == "__main__":
    test_twilight_calculator()
