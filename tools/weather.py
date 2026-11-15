"""Weather tool for the five store cities.

get_weather(city, date) -> dict
  success: {"ok": True, "city", "date", "mode", "temperature_c", "humidity_pct", "wind_kmh", "rain_mm"}
  failure: {"ok": False, "error": "..."}   (it never raises)

WEATHER_MODE=stub (default) is deterministic and offline.
WEATHER_MODE=live calls the Open-Meteo archive API (optional, needs the `requests` package).
Weather data by Open-Meteo.com (CC BY 4.0, non-commercial use) - see README.
"""
import os
import re
from datetime import date as _date

COORDS = {
    "Mumbai": (19.0760, 72.8777),
    "Pune": (18.5204, 73.8567),
    "Hyderabad": (17.3850, 78.4867),
    "Bengaluru": (12.9716, 77.5946),
    "Ahmedabad": (23.0225, 72.5714),
}

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
LIVE_TIMEOUT_SECONDS = 10
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_date(value):
    """Return a date for an exact YYYY-MM-DD string that is a real calendar date, else None."""
    if not isinstance(value, str) or not _ISO_RE.match(value):
        return None
    try:
        return _date(int(value[0:4]), int(value[5:7]), int(value[8:10]))
    except ValueError:
        return None


def _canonical_city(city):
    if not isinstance(city, str):
        return None
    for name in COORDS:
        if name.lower() == city.strip().lower():
            return name
    return None


def _stub(city, d):
    doy = d.timetuple().tm_yday          # 1 January is 1
    n = len(city)                         # characters in the city name
    return {
        "temperature_c": 20 + (n + doy) % 15,
        "humidity_pct": 40 + (3 * n + doy) % 50,
        "wind_kmh": 5 + doy % 10,
        "rain_mm": 6.5 if doy % 4 == 0 else 0.0,
    }


def _live(city, iso):
    try:
        import requests  # only needed for live mode
    except ImportError:
        return {"ok": False, "error": "live mode needs the requests package"}
    lat, lon = COORDS[city]
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": iso,
        "end_date": iso,
        "timezone": "Asia/Kolkata",
        "daily": "temperature_2m_mean,relative_humidity_2m_mean,wind_speed_10m_max,precipitation_sum",
    }
    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=LIVE_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            return {"ok": False, "error": f"weather service returned status {resp.status_code}"}
        daily = resp.json()["daily"]
        values = {
            "temperature_c": daily["temperature_2m_mean"][0],
            "humidity_pct": daily["relative_humidity_2m_mean"][0],
            "wind_kmh": daily["wind_speed_10m_max"][0],
            "rain_mm": daily["precipitation_sum"][0],
        }
        if any(v is None for v in values.values()):
            return {"ok": False, "error": "weather service returned no data for that date"}
        return values
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "weather service timed out"}
    except requests.exceptions.RequestException as exc:
        return {"ok": False, "error": f"network error: {type(exc).__name__}"}
    except (ValueError, KeyError, IndexError, TypeError):
        return {"ok": False, "error": "unexpected response from weather service"}


def get_weather(city, date):
    """Return weather for one store city on one ISO date (stub by default)."""
    canonical = _canonical_city(city)
    if canonical is None:
        return {"ok": False, "error": f"unsupported city: {city}"}
    d = _parse_date(date)
    if d is None:
        return {"ok": False, "error": f"invalid date: {date} (expected a real YYYY-MM-DD date)"}
    mode = os.environ.get("WEATHER_MODE", "stub").strip().lower() or "stub"
    if mode == "live":
        values = _live(canonical, date)
        if values.get("ok") is False:
            return values
    else:
        mode = "stub"
        values = _stub(canonical, d)
    return {"ok": True, "city": canonical, "date": date, "mode": mode, **values}


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(get_weather(sys.argv[1], sys.argv[2]), indent=2))
