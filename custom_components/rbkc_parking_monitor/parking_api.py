"""API client for RBKC Parking Suspension Monitor."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, date, timedelta
from email.utils import parsedate_to_datetime
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import ClientError

from .const import (
    CACHE_FILE,
    GEO_CACHE_FILE,
    GEOCODE_REGION,
    GEOCODE_USER_AGENT,
    GEOCODE_TIMEOUT,
    GEOCODE_RATE_LIMIT,
    EARTH_RADIUS_METERS,
)

_LOGGER = logging.getLogger(__name__)


class ParkingApiClient:
    """API client for parking suspension monitoring."""

    def __init__(
        self,
        hass,
        car_location: str,
        proximity_threshold: int,
        upcoming_window_days: int,
        debug_mode: bool = False,
    ) -> None:
        """Initialize the API client."""
        self._hass = hass
        self._car_location = car_location
        self._proximity_threshold = proximity_threshold
        self._upcoming_window_days = upcoming_window_days
        self._debug_mode = debug_mode
        self._config_dir = Path(hass.config.config_dir)
        self._geo_cache: dict[str, tuple[float, float]] = {}
        self._session: aiohttp.ClientSession | None = None

    async def async_load_caches(self) -> None:
        """Load cached data from disk."""
        # Load geocoding cache
        geo_cache_path = self._config_dir / GEO_CACHE_FILE
        if geo_cache_path.exists():
            try:
                content = await self._hass.async_add_executor_job(
                    geo_cache_path.read_text
                )
                data = json.loads(content)
                # Convert lists back to tuples
                self._geo_cache = {k: tuple(v) for k, v in data.items()}
                _LOGGER.debug("Loaded geocoding cache with %d entries", len(self._geo_cache))
            except Exception as err:
                _LOGGER.warning("Failed to load geocoding cache: %s", err)
                self._geo_cache = {}

    async def async_save_geo_cache(self) -> None:
        """Save geocoding cache to disk."""
        geo_cache_path = self._config_dir / GEO_CACHE_FILE
        try:
            content = json.dumps(self._geo_cache, indent=2)
            await self._hass.async_add_executor_job(
                geo_cache_path.write_text, content
            )
            _LOGGER.debug("Saved geocoding cache with %d entries", len(self._geo_cache))
        except Exception as err:
            _LOGGER.error("Failed to save geocoding cache: %s", err)

    async def async_save_email(self, email_body: str) -> str | None:
        """Save email body to cache and extract timestamp."""
        cache_path = self._config_dir / CACHE_FILE
        try:
            await self._hass.async_add_executor_job(
                cache_path.write_text, email_body
            )
            _LOGGER.debug("Saved email to cache (%d chars)", len(email_body))
        except Exception as err:
            _LOGGER.error("Failed to save email cache: %s", err)
            return None

        # Extract email timestamp
        return self._extract_email_timestamp(email_body)

    async def async_load_cached_email(self) -> tuple[str | None, str | None]:
        """Load cached email body and timestamp."""
        cache_path = self._config_dir / CACHE_FILE
        if not cache_path.exists():
            return None, None

        try:
            email_body = await self._hass.async_add_executor_job(
                cache_path.read_text
            )
            if len(email_body) < 10:
                return None, None

            timestamp = self._extract_email_timestamp(email_body)
            return email_body, timestamp
        except Exception as err:
            _LOGGER.error("Failed to load email cache: %s", err)
            return None, None

    def _extract_email_timestamp(self, email_body: str) -> str:
        """Extract timestamp from email subject or date header."""
        # Try subject line date (21/11/2025 format)
        subject_match = re.search(
            r"Subject:.*?(\d{2}/\d{2}/\d{4})", email_body, re.IGNORECASE
        )
        if subject_match:
            try:
                dt = datetime.strptime(subject_match.group(1), "%d/%m/%Y")
                return dt.strftime("%d %b %Y")
            except Exception:
                pass

        # Try Date header
        date_match = re.search(
            r"Date:\s*(.+?)(?:\n|$)", email_body, re.IGNORECASE | re.MULTILINE
        )
        if date_match:
            try:
                dt = parsedate_to_datetime(date_match.group(1).strip())
                return dt.strftime("%d %b %Y, %H:%M")
            except Exception:
                pass

        return datetime.now().strftime("%d %b %Y")

    async def async_geocode(self, address: str) -> tuple[float, float] | None:
        """Geocode an address using Nominatim."""
        # Check cache first
        if address in self._geo_cache:
            _LOGGER.debug("Geocode cache hit: %s", address)
            return self._geo_cache[address]

        # Geocode via API
        query = f"{address}, {GEOCODE_REGION}"
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": 1}
        headers = {"User-Agent": GEOCODE_USER_AGENT}

        try:
            if self._session is None:
                self._session = aiohttp.ClientSession()

            async with self._session.get(
                url, params=params, headers=headers, timeout=GEOCODE_TIMEOUT
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        coords = (float(data[0]["lat"]), float(data[0]["lon"]))
                        self._geo_cache[address] = coords
                        _LOGGER.debug("Geocoded %s -> %s", address, coords)
                        # Rate limiting
                        await asyncio.sleep(GEOCODE_RATE_LIMIT)
                        return coords
                else:
                    _LOGGER.warning("Geocoding failed: HTTP %d", response.status)
        except ClientError as err:
            _LOGGER.error("Geocoding error for %s: %s", address, err)
        except Exception as err:
            _LOGGER.error("Unexpected geocoding error: %s", err)

        return None

    @staticmethod
    def calc_distance(
        coord1: tuple[float, float], coord2: tuple[float, float]
    ) -> float:
        """Calculate distance between two coordinates in meters."""
        lat1, lon1 = radians(coord1[0]), radians(coord1[1])
        lat2, lon2 = radians(coord2[0]), radians(coord2[1])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return EARTH_RADIUS_METERS * c

    async def async_check_parking(
        self, email_body: str | None = None
    ) -> dict[str, Any]:
        """Check parking suspensions and return status data."""
        _LOGGER.info(
            "Starting parking check. Location: %s, Email: %s",
            self._car_location,
            "provided" if email_body else "from cache",
        )

        # Initialize result
        result = {
            "car_at_risk_now": False,
            "car_at_risk_soon": False,
            "my_active_suspensions": [],
            "my_upcoming_suspensions": [],
            "all_active_suspensions": [],
            "all_upcoming_suspensions": [],
            "map_data": [],
            "status": "OK",
            "email_timestamp": "No email received yet",
            "last_checked": datetime.now().strftime("%d %b %Y, %H:%M"),
            "car_coords": None,
        }

        # Load caches
        await self.async_load_caches()

        # Handle email body
        if email_body and len(email_body) > 10:
            result["email_timestamp"] = await self.async_save_email(email_body)
        else:
            email_body, cached_timestamp = await self.async_load_cached_email()
            if cached_timestamp:
                result["email_timestamp"] = cached_timestamp

        # Validate inputs
        if not email_body:
            result["status"] = "Cache Empty"
            result["all_active_suspensions"] = [
                "_⚠️ System Empty. Forward a suspension email to yourself to initialize._"
            ]
            result["all_upcoming_suspensions"] = result["all_active_suspensions"]
            return result

        if not self._car_location:
            result["status"] = "No Location"
            return result

        # Parse email and check suspensions
        try:
            await self._process_suspensions(email_body, result)
            await self.async_save_geo_cache()
        except Exception as err:
            _LOGGER.error("Error processing suspensions: %s", err)
            result["status"] = f"Script Crash: {err}"

        _LOGGER.info("Parking check complete. Status: %s", result["status"])
        return result

    async def _process_suspensions(
        self, email_body: str, result: dict[str, Any]
    ) -> None:
        """Process email to extract and check suspensions."""
        today = date.today()
        next_week = today + timedelta(days=self._upcoming_window_days)

        # Geocode car location
        car_coords = await self.async_geocode(self._car_location)
        result["car_coords"] = car_coords

        # Parse user location
        user_street, user_num = self._parse_location(self._car_location)

        # Decode and clean email
        decoded = self._decode_email(email_body)

        # Parse suspensions
        blocks = decoded.split("APPROVED SUSPENSION")

        for i, block in enumerate(blocks):
            if i == 0:
                continue

            suspension = self._parse_suspension_block(block)
            if not suspension:
                continue

            street_display, street_lower, loc_desc, from_date, to_date = suspension

            # Create entry
            entry = f"- **{street_display}**: {loc_desc} ({from_date.strftime('%d/%m')} - {to_date.strftime('%d/%m')})"

            # Determine suspension type (active/upcoming)
            sus_type = None
            if from_date <= today <= to_date:
                result["all_active_suspensions"].append(entry)
                sus_type = "active"
            elif today < from_date <= next_week:
                result["all_upcoming_suspensions"].append(entry)
                sus_type = "upcoming"

            # Build geocoding address
            if sus_type:
                geo_addr = self._build_geo_address(street_display, loc_desc)
                result["map_data"].append({
                    "addr": geo_addr,
                    "type": sus_type,
                    "desc": loc_desc,
                    "street": street_display,
                })

            # Check if user is at risk
            nums = self._extract_numbers(loc_desc)
            if user_street and (user_street in street_lower or street_lower in user_street):
                hit = False
                if nums and user_num and user_num in nums:
                    hit = True
                elif user_num is None:
                    hit = True

                if hit:
                    if from_date <= today <= to_date:
                        result["my_active_suspensions"].append(f"{street_display}: {loc_desc}")
                        result["car_at_risk_now"] = True
                    elif today < from_date <= next_week:
                        result["my_upcoming_suspensions"].append(f"{street_display}: {loc_desc}")
                        result["car_at_risk_soon"] = True

        # Geocode and check proximity for active suspensions
        await self._geocode_suspensions(result, car_coords)

        # Set defaults if empty
        if not result["all_active_suspensions"]:
            result["all_active_suspensions"] = ["_No active suspensions found_"]
        if not result["all_upcoming_suspensions"]:
            result["all_upcoming_suspensions"] = ["_No upcoming suspensions found_"]

    async def _geocode_suspensions(
        self, result: dict[str, Any], car_coords: tuple[float, float] | None
    ) -> None:
        """Geocode active suspensions and check proximity."""
        active_suspensions = [
            s for s in result["map_data"] if s["type"] == "active"
        ][: 5]  # Top 5 only

        for idx, sus in enumerate(active_suspensions):
            coords = await self.async_geocode(sus["addr"])
            if coords:
                # Add to map data with coords
                sus["coords"] = coords
                sus["tracker_id"] = f"sus_active_{idx}"

                # Distance-based risk check
                if car_coords and sus["street"].lower() in self._car_location.lower():
                    distance = self.calc_distance(car_coords, coords)
                    if distance <= self._proximity_threshold:
                        sus_desc = f"{sus['street']}: {sus['desc']}"
                        if sus_desc not in result["my_active_suspensions"]:
                            result["my_active_suspensions"].append(sus_desc)
                            result["car_at_risk_now"] = True
                            _LOGGER.debug(
                                "Distance alert: %.0fm from suspension", distance
                            )

    @staticmethod
    def _parse_location(location: str) -> tuple[str, int | None]:
        """Parse location into street name and number."""
        match = re.search(r"(\d+)", location)
        num = int(match.group(1)) if match else None
        street = re.sub(r"\d+", "", location).replace(",", "").strip().lower()
        return street, num

    @staticmethod
    def _decode_email(email_body: str) -> str:
        """Decode and clean email body."""
        decoded = email_body.replace("=\r\n", "").replace("=\n", "")
        decoded = decoded.replace("=3D", "=").replace("=20", " ")
        decoded = re.sub(r"^>+\s*", "", decoded, flags=re.MULTILINE)
        decoded = re.sub(r"<[^>]+>", "", decoded)
        return " ".join(decoded.split())

    @staticmethod
    def _parse_suspension_block(
        block: str,
    ) -> tuple[str, str, str, date, date] | None:
        """Parse a suspension block from email."""
        # Extract street name
        street_match = re.search(
            r"Street Name:\s*(.*?)(?:From Date|To Date|Number of Bays|$)",
            block,
            re.IGNORECASE,
        )
        if not street_match:
            return None

        street_display = street_match.group(1).strip()
        street_lower = street_display.lower()

        # Extract location description
        loc_match = re.search(
            r"Location:\s*(.*?)(?:To view|http|$)", block, re.IGNORECASE
        )
        loc_desc = loc_match.group(1).strip() if loc_match else "Check Signage"

        # Extract dates
        from_date, to_date = ParkingApiClient._extract_dates(block)
        if not from_date or not to_date:
            return None

        return street_display, street_lower, loc_desc, from_date, to_date

    @staticmethod
    def _extract_dates(text: str) -> tuple[date | None, date | None]:
        """Extract from and to dates from text."""
        from_date, to_date = None, None
        date_pattern = r"(\d{2}/\d{2}/\d{4})"

        from_match = re.search(r"From Date:\s*" + date_pattern, text)
        if from_match:
            try:
                from_date = datetime.strptime(from_match.group(1), "%d/%m/%Y").date()
            except Exception:
                pass

        to_match = re.search(r"To Date:\s*" + date_pattern, text)
        if to_match:
            try:
                to_date = datetime.strptime(to_match.group(1), "%d/%m/%Y").date()
            except Exception:
                pass

        return from_date, to_date

    @staticmethod
    def _extract_numbers(text: str) -> set[int]:
        """Extract house numbers from location description."""
        nums = set()

        # Clean up text
        cleaned = re.sub(r"\bNo\.?\s+(\d+)", r"\1", text, flags=re.IGNORECASE)
        for delimiter in [".", " Sign", " Signs"]:
            if delimiter in cleaned:
                cleaned = cleaned.split(delimiter)[0]

        # Extract ranges (e.g., "12-18" or "12 to 18")
        range_pattern = re.compile(r"(\d+)\s*(?:-|to)\s*(\d+)", re.IGNORECASE)
        for match in range_pattern.finditer(cleaned):
            try:
                nums.update(range(int(match.group(1)), int(match.group(2)) + 1))
            except Exception:
                continue

        # Remove ranges from text
        cleaned = range_pattern.sub(" ", cleaned)

        # Extract individual numbers (excluding certain keywords)
        num_pattern = re.compile(
            r"\b(\d+)\b(?!\s*(?:bays|spaces|permit|RES|PBP|sign|lamp|st|nd|rd|th))",
            re.IGNORECASE,
        )
        for match in num_pattern.finditer(cleaned):
            try:
                nums.add(int(match.group(1)))
            except Exception:
                continue

        return nums

    @staticmethod
    def _build_geo_address(street: str, location_desc: str) -> str:
        """Build best geocoding address from street and location."""
        nums = ParkingApiClient._extract_numbers(location_desc)
        if nums:
            # Use street number if available
            return f"{min(nums)} {street}"

        # Try to extract landmark/building name
        landmark_match = re.search(
            r"(?:outside|near|opposite|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            location_desc,
            re.IGNORECASE,
        )
        if landmark_match:
            landmark = landmark_match.group(1)
            return f"{landmark}, {street}"

        return street

    async def async_close(self) -> None:
        """Close the API client session."""
        if self._session:
            await self._session.close()
            self._session = None
