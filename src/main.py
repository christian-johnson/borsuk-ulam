import base64
import io
import json
import re
from datetime import datetime, timedelta
from urllib.parse import quote

import matplotlib

matplotlib.use(
    "agg"
)  # must precede pyplot import; Pyodide's default canvas backend can't savefig to BytesIO
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz
from pyodide.http import open_url


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that converts numpy scalars to native Python types."""

    def default(self, obj):
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        return super().default(obj)


COASTLINE_DATA = None

# Global state to hold the dataframe so we don't re-fetch when toggling views
global_df = None
global_matches = None
global_timestamp = None

proxy_url = (
    "https://cors-header-proxy.christian-johnson-3ef.workers.dev/corsproxy/?apiurl="
)

# UCAR THREDDS OPeNDAP endpoint for GFS 1-degree data.
# NOMADS DODS was retired in 2025 (NOAA SCN 25-81).
THREDDS_BASE = "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/GFS/Global_onedeg"


def _fetch(url):
    """Fetch a URL through the CORS proxy, returning the response text."""
    return open_url(proxy_url + quote(url, safe="")).read()


def _parse_dods_ascii(text, varname):
    """Parse an OPeNDAP ASCII response for a surface variable over the full lat/lon grid.

    The response is expected to include lat[181], lon[360], and *varname* as a
    (possibly 4-D) array whose last two dimensions are lat and lon.

    Args:
        text: Raw ASCII response string from THREDDS.
        varname: Variable name exactly as requested, e.g. 'Temperature_surface'.

    Returns:
        tuple: (lats, lons, rows) where rows[i] is a 1-D float array of length
               360, holding the variable values at latitude lats[i] across all
               longitudes.  Returns (None, None, []) if parsing fails.
    """
    sep = "---------------------------------------------"
    data_section = text.split(sep + "\n", 1)[1] if sep in text else text
    lines = data_section.split("\n")

    lats = lons = None
    rows = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Standalone coordinate arrays appear as bare "lat[N]" / "lon[N]".
        # Grid map sections like "Temperature_surface.lat[N]" contain a dot
        # and must be ignored — they only cover the requested slice, not the
        # full 181/360-point coordinate axis.
        if line.startswith("lat[") and "." not in line:
            i += 1
            if i < len(lines) and lines[i].strip():
                lats = np.fromstring(lines[i], sep=", ")

        elif line.startswith("lon[") and "." not in line:
            i += 1
            if i < len(lines) and lines[i].strip():
                lons = np.fromstring(lines[i], sep=", ")

        elif varname + "." + varname in line:
            # Data rows follow, one per latitude.
            # Format: "[t0][t1][lat_idx], v0, v1, ..., v359"
            i += 1
            while i < len(lines) and lines[i].startswith("["):
                _, _, data_str = lines[i].partition(", ")
                if data_str.strip():
                    rows.append(np.fromstring(data_str, sep=", "))
                i += 1
            continue

        i += 1

    return lats, lons, rows


def get_latest_gfs():
    """Fetch GFS surface data from UCAR THREDDS TwoD for the most current forecast.

    Picks the most recently ingested model run and the forecast step whose
    valid time is closest to the current UTC time.

    GFS runs every 6 hours (0z/6z/12z/18z).  Data takes ~3 hours to reach
    THREDDS, so we subtract that before computing which run to use.

    Returns:
        tuple: (df, timestamp_str) where df has columns lat, lon, tmp2m (°C),
               press (atm).

    Raises:
        RuntimeError: If the fetch or parse fails.
    """
    utc_now = datetime.now(pytz.UTC)

    # Subtract availability lag before choosing the run cycle.
    safe_now = utc_now - timedelta(hours=3)
    last_run_hour = (safe_now.hour // 6) * 6
    run_time = safe_now.replace(
        hour=last_run_hour, minute=0, second=0, microsecond=0
    )

    # Round elapsed time to the nearest 3-hour forecast step.
    hours_elapsed = (utc_now - run_time).total_seconds() / 3600
    desired_offset_h = round(hours_elapsed / 3) * 3
    offset_idx = int(desired_offset_h / 3)

    # Fetch the DDS to find the number of available runs in the TwoD archive.
    # We look specifically for 'reftime' (model run axis) and 'validtime1Offset'
    # (forecast step axis) — not the large aggregate time dimensions that caused
    # the previous "Request Too Large" failure.
    try:
        dds_text = _fetch(f"{THREDDS_BASE}/TwoD.dds")
        m_run = re.search(r"\[reftime\s*=\s*(\d+)\]", dds_text)
        n_runs = int(m_run.group(1)) if m_run else 1
        m_off = re.search(r"\[validtime1Offset\s*=\s*(\d+)\]", dds_text)
        if m_off:
            offset_idx = min(offset_idx, int(m_off.group(1)) - 1)
    except Exception as e:
        print(f"DDS fetch failed ({e}); defaulting to run 0, offset 0")
        n_runs = 1

    run_idx = n_runs - 1
    valid_time = run_time + timedelta(hours=desired_offset_h)
    print(f"run_idx={run_idx}, offset_idx={offset_idx}, valid={valid_time}")

    run_slice = f"[{run_idx}:1:{run_idx}]"
    offset_slice = f"[{offset_idx}:1:{offset_idx}]"
    lat_slice = "[0:1:180]"
    lon_slice = "[0:1:359]"

    base = f"{THREDDS_BASE}/TwoD.ascii"
    coord_prefix = f"lat{lat_slice},lon{lon_slice},"

    temp_url = (
        f"{base}?{coord_prefix}"
        f"Temperature_surface{run_slice}{offset_slice}{lat_slice}{lon_slice}"
    )
    pres_url = (
        f"{base}?{coord_prefix}"
        f"Pressure_surface{run_slice}{offset_slice}{lat_slice}{lon_slice}"
    )

    print(f"Fetching temperature: {temp_url}")
    s = _fetch(temp_url)
    print(f"Fetching pressure: {pres_url}")
    p = _fetch(pres_url)

    lats, lons, temp_rows = _parse_dods_ascii(s, "Temperature_surface")
    _, _, pres_rows = _parse_dods_ascii(p, "Pressure_surface")

    if lats is None or lons is None or not temp_rows or not pres_rows:
        raise RuntimeError("Failed to parse GFS data from THREDDS response.")
    if len(temp_rows) != len(lats) or len(pres_rows) != len(lats):
        raise RuntimeError(
            f"Row count mismatch: lats={len(lats)}, "
            f"temp={len(temp_rows)}, pres={len(pres_rows)}"
        )

    df = pd.concat(
        [
            pd.DataFrame({
                "lat": float(lats[j]),
                "lon": lons,
                "tmp2m": temp_rows[j],
                "press": pres_rows[j],
            })
            for j in range(len(lats))
        ],
        ignore_index=True,
    )

    df["tmp2m"] -= 273.15
    df["press"] *= 9.868e-6

    timestamp = (
        f"GFS {run_time.strftime('%Y-%m-%d %H')}z +{desired_offset_h:.0f}h"
        f" | Valid: {valid_time.strftime('%Y-%m-%d %H:%M')}z"
    )
    return df, timestamp


def find_matching_antipodes(df):
    """Get the antipode locations with equal temperature & pressure."""
    threshold = 0.001

    # Create antipode coordinates
    df = df.copy()
    df["antipode_lat"] = -df["lat"]
    df["antipode_lon"] = (df["lon"] + 180) % 360

    # Merge with itself on antipodal coordinates
    merged = df.merge(
        df,
        left_on=["antipode_lat", "antipode_lon"],
        right_on=["lat", "lon"],
        suffixes=("", "_opp"),
    )

    # Compute differences
    merged["tmp2m_diff"] = (merged["tmp2m"] - merged["tmp2m_opp"]) / merged["tmp2m"]
    merged["press_diff"] = (merged["press"] - merged["press_opp"]) / merged["press"]

    # Apply threshold condition
    equals = merged[
        (np.abs(merged["tmp2m_diff"]) < threshold)
        & (np.abs(merged["press_diff"]) < threshold)
    ]

    return equals[df.columns].to_dict("records")


def get_coastlines():
    global COASTLINE_DATA
    if COASTLINE_DATA is not None:
        return COASTLINE_DATA

    # URL to Natural Earth 110m Coastlines (Low res, very small file ~250KB)
    # This is perfect for web visualization
    url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_coastline.geojson"

    try:
        print("Fetching coastlines...")
        # open_url is synchronous, which is fine for this small file
        data = json.loads(open_url(url).read())

        COASTLINE_DATA = data
        return data
    except Exception as e:
        print(f"Failed to load coastlines: {e}")
        return None


def plot_coastlines_on_ax(ax):
    data = get_coastlines()
    if not data:
        return

    # Iterate through the GeoJSON features
    for feature in data["features"]:
        geometry = feature["geometry"]
        geom_type = geometry["type"]
        coords = geometry["coordinates"]

        # Helper to plot a single line string
        def plot_line(points):
            # Points is list of [lon, lat]
            arr = np.array(points)
            lons, lats = arr[:, 0], arr[:, 1]

            # Matplotlib hack: Stop lines from drawing horizontally across the
            # entire map when crossing the 180th meridian (the date line)
            # We split the line if the jump is too big.
            diffs = np.abs(np.diff(lons))
            if np.any(diffs > 180):
                # Simple skip for this specific segment or complex splitting
                # For this demo, we just plot it; if it looks messy,
                # we can add the splitting logic.
                # Most 110m natural earth data is already cut at 180.
                pass

            ax.plot(lons, lats, color="black", linewidth=0.8, transform=ax.transData)

        if geom_type == "LineString":
            plot_line(coords)
        elif geom_type == "MultiLineString":
            for line_coords in coords:
                plot_line(line_coords)


def generate_texture_base64(df, column, cmap_name):
    # Pivot to grid for plotting; rotate to match coastline
    df2 = df.copy()
    df2["lon"] = (df2["lon"] + 180) % 360
    grid = df2.pivot(index="lat", columns="lon", values=column)

    # Plotting setup
    fig = plt.figure(figsize=(10, 5), dpi=150, frameon=False)

    # [0,0,1,1] fills the whole image with the axes
    ax = plt.Axes(fig, [0.0, 0.0, 1.0, 1.0])
    ax.set_axis_off()
    fig.add_axes(ax)

    color_scales_dict = {
        "tmp2m": {"vmin": -40, "vmax": 40},
        "press": {"vmin": 0.5, "vmax": 1.05},
    }

    # Simple Pcolormesh (Equirectangular projection)
    ax.imshow(
        grid.values,
        origin="lower",
        extent=[-180, 180, -90, 90],
        cmap=cmap_name,
        aspect="auto",
        vmin=color_scales_dict[column]["vmin"],
        vmax=color_scales_dict[column]["vmax"],
    )

    plot_coastlines_on_ax(ax)

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    buf.seek(0)

    # Encode
    b64_str = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"


def process_data():
    global global_df, global_matches, global_timestamp

    # 1. Fetch
    global_df, global_timestamp = get_latest_gfs()

    # 2. Calculate Matches
    global_matches = find_matching_antipodes(global_df)

    # 3. Generate Textures
    # Temperature: 'RdYlBu_r' (Red is hot, Blue is cold)
    # Pressure: 'viridis'
    temp_img = generate_texture_base64(global_df, "tmp2m", "RdYlBu_r")
    press_img = generate_texture_base64(global_df, "press", "viridis")

    return json.dumps(
        {
            "timestamp": global_timestamp,
            "matches": global_matches,
            "textures": {"temp": temp_img, "press": press_img},
        },
        cls=_NumpyEncoder,
    )
