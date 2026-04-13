import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import json

from pyodide.http import open_url
from datetime import datetime, timedelta
from urllib.parse import quote
import pytz


COASTLINE_DATA = None


# Global state to hold the dataframe so we don't re-fetch when toggling views
global_df = None
global_matches = None
global_timestamp = None
proxy_url = "https://cors-header-proxy.christian-johnson-3ef.workers.dev/?apiurl="

# UCAR THREDDS OPeNDAP endpoint for GFS 1-degree data.
# NOMADS DODS was retired in 2025 (NOAA SCN 25-81).
THREDDS_BASE = "https://thredds.ucar.edu/thredds/dodsC/grib/NCEP/GFS/Global_onedeg"


def _parse_dods_section(text):
    """Extract data lines, lats, and lons from a UCAR THREDDS OPeNDAP ASCII response.

    The response starts with a DDS header (Dataset {...}) followed by a
    separator line, then the data section.  Within the data section the last
    two coordinate blocks are always lat and lon (in that order), so after
    stripping trailing blank lines: lines[-1] = lon values, lines[-4] = lat
    values.  Data rows start at line 1 (line 0 is the variable declaration).
    """
    sep = "---------------------------------------------"
    data_section = text.split(sep + "\n", 1)[1] if sep in text else text
    data_lines = data_section.split("\n")
    stripped = data_section.rstrip().split("\n")
    lons = np.array(stripped[-1].split(", "), dtype=float)
    lats = np.array(stripped[-4].split(", "), dtype=float)
    return data_lines, lats, lons


def get_latest_gfs(max_lookback_hours=24):
    # GFS runs every 6 hours; UCAR THREDDS has 3-hourly forecast steps
    # starting at +3h (no analysis hour in the individual files).
    utc = pytz.timezone("UTC")
    current_utc_time = datetime.now(utc)

    offset = current_utc_time.hour % 6
    latest_possible_run = current_utc_time.replace(
        minute=0, second=0, microsecond=0
    ) - timedelta(hours=offset)

    for i in range(0, max_lookback_hours, 6):
        gfs_time = latest_possible_run - timedelta(hours=i)

        year = gfs_time.year
        month = f"{gfs_time.month:02}"
        day = f"{gfs_time.day:02}"
        hour = f"{gfs_time.hour:02}"
        hour_hhmm = f"{gfs_time.hour:02}00"  # e.g. "0600", "1800"

        # Round elapsed time to the nearest 3-hour forecast step (min = +3h).
        forecast_hours = (current_utc_time - gfs_time).total_seconds() / 3600
        fh = max(3, round(forecast_hours / 3) * 3)
        time_idx = int(fh / 3) - 1  # 0-based index into the file's time dimension

        file_name = f"GFS_Global_onedeg_{year}{month}{day}_{hour_hhmm}.grib2"
        base = f"{THREDDS_BASE}/{file_name}.ascii"

        temp_url = (
            f"{base}?Temperature_height_above_ground"
            f"[{time_idx}:1:{time_idx}][0:1:0][0:1:180][0:1:359]"
        )
        pres_url = (
            f"{base}?Pressure_surface"
            f"[{time_idx}:1:{time_idx}][0:1:180][0:1:359]"
        )

        try:
            print(f"Fetching GFS run {year}-{month}-{day} {hour}z, forecast hour +{fh:.0f}")
            s = open_url(proxy_url + quote(temp_url, safe="")).read()
            p = open_url(proxy_url + quote(pres_url, safe="")).read()

            s_lines, lats, lons = _parse_dods_section(s)
            p_lines, _, _ = _parse_dods_section(p)

            df = pd.concat(
                [
                    pd.DataFrame(
                        {
                            "lat": lats[j],
                            "lon": lons,
                            "tmp2m": np.array(
                                s_lines[j + 1].split(", ")[1:], dtype=float
                            ),
                            "press": np.array(
                                p_lines[j + 1].split(", ")[1:], dtype=float
                            ),
                        }
                    )
                    for j in range(len(lats))
                ],
                axis=0,
            )
            df["tmp2m"] -= 273.15
            df["press"] *= 9.868 * 10 ** (-6)

            valid_time = gfs_time + timedelta(hours=fh)
            timestamp = f"Run: {year}-{month}-{day} {hour}z | Valid: {valid_time.strftime('%Y-%m-%d %H:%M')}z"

            return df, timestamp
        except Exception as e:
            print(f"Failed fetching GFS run {hour}z forecast +{fh:.0f}: {e}")

    raise RuntimeError("No available GFS datasets found in the given lookback window.")


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

    # # Encode
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
        }
    )
