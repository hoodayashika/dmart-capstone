# Weather tool tests

Tool-level tests of `tools/weather.py` (`WEATHER_MODE=stub`). Outputs are pasted from a real run of `get_weather(city, date)`.

## T1 check value: Mumbai 2026-05-15 (expect 26, 43, 10, 0.0)

Call: `get_weather('Mumbai', '2026-05-15')`

```
{"ok": true, "city": "Mumbai", "date": "2026-05-15", "mode": "stub", "temperature_c": 26, "humidity_pct": 43, "wind_kmh": 10, "rain_mm": 0.0}
```

## T2 check value: Pune 2026-05-16 (expect 25, 88, 11, 6.5)

Call: `get_weather('Pune', '2026-05-16')`

```
{"ok": true, "city": "Pune", "date": "2026-05-16", "mode": "stub", "temperature_c": 25, "humidity_pct": 88, "wind_kmh": 11, "rain_mm": 6.5}
```

## T3 check value: Hyderabad 2026-04-01 (expect 30, 58, 6, 0.0)

Call: `get_weather('Hyderabad', '2026-04-01')`

```
{"ok": true, "city": "Hyderabad", "date": "2026-04-01", "mode": "stub", "temperature_c": 30, "humidity_pct": 58, "wind_kmh": 6, "rain_mm": 0.0}
```

## T4 unsupported city: Kolkata

Call: `get_weather('Kolkata', '2026-05-15')`

```
{"ok": false, "error": "unsupported city: Kolkata"}
```

## T5 bad date: not a real calendar date

Call: `get_weather('Pune', '2026-02-30')`

```
{"ok": false, "error": "invalid date: 2026-02-30 (expected a real YYYY-MM-DD date)"}
```

## T6 bad date: wrong shape (no hyphens)

Call: `get_weather('Pune', '20260515')`

```
{"ok": false, "error": "invalid date: 20260515 (expected a real YYYY-MM-DD date)"}
```

## T7 own case: lowercase city name, last data day (Bengaluru, n=9, doy=180)

Call: `get_weather('bengaluru', '2026-06-29')`

```
{"ok": true, "city": "Bengaluru", "date": "2026-06-29", "mode": "stub", "temperature_c": 29, "humidity_pct": 47, "wind_kmh": 5, "rain_mm": 6.5}
```

## T8 live mode when the network is unavailable (must not crash)

Call: `WEATHER_MODE=live`, `get_weather('Pune', '2026-05-16')` in a sandbox with no network access. The remote output is optional and ungraded; this only shows that a failure is returned as a structured error.

```
{"ok": false, "error": "network error: ConnectionError"}
```
