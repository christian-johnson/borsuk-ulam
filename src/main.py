import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import json

from pyodide.http import open_url
from datetime import datetime, timedelta
import pytz


COASTLINE_DATA = None


# Global state to hold the dataframe so we don't re-fetch when toggling views
global_df = None
global_matches = None
global_timestamp = None
proxy_url = "https://corsproxy.io/?"


def get_latest_gfs(max_lookback_hours=12):
    # Figure out which GFS run we want to query
    # GFS runs every 6 hours, with hourly forecasts
    eastern = pytz.timezone("US/Eastern")
    current_eastern_time = datetime.now(eastern)
    # Round down to the nearest 6-hour mark
    offset = current_eastern_time.hour % 6
    gfs_time = current_eastern_time.replace(
        minute=0, second=0, microsecond=0
    ) - timedelta(hours=offset)
    idx = 1 * (offset > 3)

    for _ in range(0, max_lookback_hours, 6):
        year = gfs_time.year
        month = f"{gfs_time.month:02}"
        day = f"{gfs_time.day:02}"
        hour = f"{gfs_time.hour:02}"

        # EXACT URL construction from working example (using 179 and 359 limits)
        temp_url = f"https://nomads.ncep.noaa.gov/dods/gfs_1p00/gfs{year}{month}{day}/gfs_1p00_{hour}z.ascii?tmp2m[{idx}:1:{idx}][0:1:179][0:1:359]"
        pres_url = f"https://nomads.ncep.noaa.gov/dods/gfs_1p00/gfs{year}{month}{day}/gfs_1p00_{hour}z.ascii?pressfc[{idx}:1:{idx}][0:1:179][0:1:359]"

        try:
            print(f"Fetching: {temp_url}")
            s = open_url(proxy_url + temp_url).read()
            p = open_url(proxy_url + pres_url).read()

            lons = np.array(s.split("\n")[-2].split(", "), dtype=float)
            lats = np.array(s.split("\n")[-4].split(", "), dtype=float)

            df = pd.concat(
                [
                    pd.DataFrame(
                        {
                            "lat": lats[i],
                            "lon": lons,
                            "tmp2m": np.array(
                                s.split("\n")[i + 1].split(", ")[1:], dtype=float
                            ),
                            "press": np.array(
                                p.split("\n")[i + 1].split(", ")[1:], dtype=float
                            ),
                        }
                    )
                    for i in range(len(lats))
                ],
                axis=0,
            )
            df["tmp2m"] -= 273.15
            df["press"] *= 9.868 * 10 ** (-6)

            # Create a timestamp string for display
            timestamp = f"{year}-{month}-{day} {hour}z"

            return df, timestamp
        except Exception as e:
            print(f"no GFS data for: {hour}. Error: {e}")
            gfs_time -= timedelta(hours=6)

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

    # Simple Pcolormesh (Equirectangular projection)
    ax.imshow(
        grid.values,
        origin="lower",
        extent=[-180, 180, -90, 90],
        cmap=cmap_name,
        aspect="auto",
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
