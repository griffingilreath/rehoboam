# Municipal Services — Maintenance Guide

Milwaukee's municipal data APIs have varying levels of stability. This guide documents what to watch for and what to do when things break.

## Services

| Package | API | Stability | Update Frequency |
|---------|-----|-----------|-----------------|
| `snow_plows.yaml` | ArcGIS REST (SnowRoutes_PublicView) | ✅ Stable | Seasonal |
| `trash_recycling.yaml` | Milwaukee IT servlet | ⚠️ Fragile | Annual check |
| `leaf_collection.yaml` | ArcGIS REST (Leaf_Routes_XXXXXX_view) | ⚠️ Annual URL change | Every fall |

---

## Snow Plows

**Endpoint:** `https://services1.arcgis.com/5ly0cVV70qsN8Soc/arcgis/rest/services/SnowRoutes_PublicView/FeatureServer/0/query`

**If it breaks:** Search `SnowRoutes_PublicView` on [data.milwaukee.gov](https://data.milwaukee.gov) and update the URL in `snow_plows.yaml`.

**System health sensor:** `sensor.mke_snow_api_health` — if this shows `no_data` during a known snow event, the API is down.

---

## Trash & Recycling

**Endpoint:** Stored in `secrets.yaml` as `milwaukee_garbage_url`.

**Expected format:**
```
https://itmdapps.milwaukee.gov/DpwServletsPublic/garbage_day?address=2930N39thStreet
```
The endpoint should return JSON: `{"success": true, "garbage": {"date": "Monday January 15, 2024", "route": "A3"}, ...}`

**If it breaks:** The legacy servlet sometimes returns HTML or goes down. Options:
1. Inspect network traffic on Milwaukee's official website or garbage app to find any new JSON endpoint
2. Manually set pickup dates using the `input_datetime` helpers in the UI as a fallback
3. Check `sensor.mke_sanitation_raw` — its state will be `error` when the API fails

---

## Leaf Collection ⚠️ REQUIRES ANNUAL UPDATE

Milwaukee publishes a **new ArcGIS feature layer every fall** with a new URL. The layer name includes the publication date (e.g., `Leaf_Routes_061022_view` was published June 10, 2022).

**Every September 15**, you'll get an HA notification reminding you to:
1. Go to [data.milwaukee.gov](https://data.milwaukee.gov)
2. Search for "Leaf Collection"
3. Find the new layer URL
4. Update it in HA: **Settings → Helpers → "Leaf Collection: ArcGIS Layer URL"**

**Season window:** Default is Oct 1 – Nov 20. Adjust via HA helpers:
- `input_text.leaf_season_start` (format: `MM-DD`)
- `input_text.leaf_season_end` (format: `MM-DD`)

**Route status values from ArcGIS:**
- `Collected` — Leaves have been picked up on your route this round
- `Not Collected` / _(blank)_ — Not yet done this round
- `In Progress` — City crews are currently working your area
- `FinalRound: Yes` — Last collection of the season
