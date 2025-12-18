# MUNICIPAL SERVICES API: LONG TERM SUPPORT STRATEGY
# Last Updated: Dec 16, 2025

This document outlines the strategy for maintaining connection to Milwaukee's municipal data services (Snow, Trash, Leaves).

## 1. Snow Plow Operations (ArcGIS)
**Status:** ✅ Stable (Modern REST API)
- **Endpoint:** `https://services1.arcgis.com/.../SnowRoutes_PublicView/FeatureServer/0/query`
- **Protocol:** HTTP/2 over TLS 1.3
- **Reliability Check:** We implemented a `mke_snow_system_health` sensor. This queries a 5km radius to see if *any* plow data exists. If this returns 0 features during winter, the system is down, and we suppress "No Activity" warnings to avoid false negatives.

**Mitigation Plan:**
- If the endpoint changes, search for "SnowRoutes_PublicView" on the [Milwaukee Open Data Portal](https://data.milwaukee.gov/).
- Update the `resource_template` in `packages/municipal/snow_plows.yaml`.

## 2. Garbage & Recycling (Legacy Servlet)
**Status:** ⚠️ Fragile (Old HTML Servlet)
- **Endpoint:** `https://itmdapps.milwaukee.gov/DpwServletsPublic/garbage_day`
- **Protocol:** HTTP/1.1 over TLS 1.2
- **Issue:** This endpoint returns a full HTML page intended for browsers, not JSON. It is prone to breaking if the city redesigns their website layout.
- **Current Fix:** We are using a simple "Service Status" check (`Milwaukee Garbage Service Status`) that just looks for the text "Sanitation Collection Schedule" in the response. This ensures we at least know if the server is responding.

**Long Term Fix (The "Right Way"):**
- The city has an internal API used by their mobile app. It is not publicly documented but is likely a REST endpoint.
- **Action Item:** If the HTML scraper fails permanently, inspect network traffic on the "Garbage Day" mobile app or website to find the underlying JSON API.

## 3. Leaf Collection (ArcGIS)
**Status:** ✅ Stable (Modern REST API)
- **Endpoint:** `https://services1.arcgis.com/.../Leaf_Routes_061022_view/FeatureServer/0/query`
- **Note:** The "061022" in the URL suggests a date-versioned dataset (June 10, 2022).
- **Risk:** The city creates *new* feature layers for each year (e.g., `Leaf_Routes_2025_view`).
- **Maintenance:** Every Fall (October), you must check the Open Data Portal for the new Leaf Collection dataset URL and update `packages/municipal/snow_plows.yaml`.

## Summary of Maintenance
| Service | Update Frequency | What to Watch For |
| :--- | :--- | :--- |
| **Snow** | Low | System outages during storms. |
| **Garbage** | Medium | Website redesigns breaking the HTML parser. |
| **Leaves** | High (Annual) | New API URL published every Fall. |
