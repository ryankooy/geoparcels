#!/usr/bin/python3

import folium
import json
import requests
from folium.features import DivIcon
from operator import itemgetter
from urllib.parse import quote

COUNTY_CENTER = [36.046488, -79.389513]
URL = "https://apps.alamance-nc.com/arcgis/rest/services/Tax/AlamanceParcels/FeatureServer/0/query"

offset = 0


def get(m, key):
    """Get value from map by key."""
    value = m[key]
    if value:
        if isinstance(value, str):
            return value.strip()
        return value
    elif value is None:
        return ""
    return value


def set_color_by_year(year):
    """Return CSS color based on given year value."""
    year = int(year)
    if not year:
        return "white"

    if year < 1850:
        return "red"
    elif 1850 <= year < 1875:
        return "orange"
    elif 1875 <= year < 1900:
        return "yellow"
    elif 1900 <= year < 1925:
        return "limegreen"
    elif 1925 <= year < 1950:
        return "green"
    elif 1950 <= year < 1975:
        return "springgreen"
    elif 1975 <= year < 2000:
        return "blue"
    elif 2000 <= year < 2025:
        return "violet"
    elif year >= 2025:
        return "magenta"


def get_default_params():
    global offset
    return {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": True,
        "outSR": 4326,
        "f": "json",
        "resultOffset": offset,
        "resultRecordCount": 1000,
    }


def build_where_query(args):
    """Build clause for API's `where` query parameter."""
    queries = []

    if args.city:
        queries.append(f"OWCITY = '{args.city}'")
    if args.city_code:
        queries.append(f"AKCYCD = '{args.city_code}'")
    if args.nh_code:
        queries.append(f"AKNECD = '{args.nh_code}'")
    if args.street_num:
        queries.append(f"AKPST_ = {args.street_num}")
    if args.street_name:
        street_name = args.street_name.upper()
        queries.append(f"AKPSTN = '{street_name}'")
    if args.min_acres:
        queries.append(f"ACRES >= {args.min_acres}")

    if args.land_parcels_only:
        queries.append("(AHACYR = 0 OR XXDDC1 = 'NON ACRES')")
    elif args.start_year and args.end_year:
        queries.append(f"AHACYR >={args.start_year} AND AHACYR < {args.end_year}")
    elif args.start_year:
        queries.append(f"AHACYR >={args.start_year}")
    elif args.end_year:
        queries.append(f"AHACYR < {args.end_year}")

    if queries:
        return f" AND ".join(queries)

    return "1=1"


def print_row(label, value):
    spaces = " " * (37 - len(label))
    print(f"{label}:{spaces}{value}")


def make_map(filename, coordinates):
    """Generate map (HTML file) using given coordinates."""
    # Create map
    geomap = folium.Map(location=COUNTY_CENTER, zoom_start=12)

    # Add satellite image layer
    esri_satellite = folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Esri Satellite",
        overlay=True,
        control=True,
    )
    esri_satellite.add_to(geomap)

    # Add map layer controls for user
    folium.LayerControl().add_to(geomap)

    # Add circles at given coordinates
    for item in coordinates:
        points = item["rings"]

        if args.show_prop_lines:
            # Draw property lines and points
            folium.PolyLine(
                locations=points, color="black", weight=2, opacity=1
            ).add_to(geomap)

            for point in points:
                folium.Circle(
                    location=point,
                    radius=0.3,
                    color="black",
                    fill=True,
                    fill_color="black",
                    fill_opacity=1,
                ).add_to(geomap)

        # Set popup info
        popup = folium.Popup(item["html"], max_width=250, min_width=150)

        color = set_color_by_year(item["year"])
        center_lat = sum(p[0] for p in points) / len(points)
        center_lng = sum(p[1] for p in points) / len(points)

        # Draw circle at approximate center of parcel
        folium.Circle(
            location=[center_lat, center_lng],
            radius=5,
            color=color,
            popup=popup,
            fill=True,
            fill_color=color,
            fill_opacity=1,
        ).add_to(geomap)

    # Generate map HTML file
    geomap.save(args.output_map)


def main(args):
    global offset
    feature_count = 0
    year_map = {}
    json_results = []
    coordinates = []
    legal_fields = ["AKLAD1", "AKLAD2", "AKLAD3"]
    divider = "=================================================================="

    # Set API query parameters
    params = get_default_params()
    params["where"] = build_where_query(args)

    # Open TTY for writing to terminal
    tty = open("/dev/tty", "w")
    tty.write("Pulling 'n' parsing data...\n")

    # Fetch GIS data from ArcGIS API
    while True:
        params["resultOffset"] = offset

        try:
            # Fetch response
            response = requests.get(URL, params=params)

            # Check if request was successful
            response.raise_for_status()

            # Parse JSON from response
            data = response.json()

            features = data.get("features", [])
            if not features:
                # This response is feature-less, so break the loop
                break

            if args.json_dump_file:
                # Add features to the list of JSON results
                json_results.extend(features)

            feature_count += len(features)

            # Iterate the returned features and do stuff with 'em
            for feature in features:
                attr = feature["attributes"]

                if args.print_all_fields:
                    print(divider)

                    # Print a labeled row for each field
                    for field in data["fields"]:
                        value = attr[field["name"]]

                        if field["type"] == "esriFieldTypeString":
                            value = value.strip()
                        elif isinstance(value, float) and not value.is_integer():
                            value = f"{value:.2f}"

                        if value:
                            print_row(field["alias"], value)

                elif args.print_summary:
                    print(divider)

                    owner1 = get(attr, "OWNAM1")
                    owner2 = get(attr, "OWNAM2")
                    if owner2:
                        print_row("Owners", f"{owner1}, {owner2}")
                    else:
                        print_row("Owner", owner1)

                    addr = get(attr, "CAKPSAD")
                    print_row("Street address", addr)

                    city = get(attr, "OWCITY")
                    print_row("City", city)

                    city_code = get(attr, "AKCYCD")
                    print_row("City code", city_code)

                    legal_values = "; ".join(
                        [v for a in legal_fields if (v := get(attr, a))]
                    )

                    print_row("Legal", legal_values)

                    year = get(attr, "AHACYR")
                    print_row("Built", year)

                    acres = get(attr, "ACRES")
                    print_row("Acres", acres)

                    desc = get(attr, "XXDDC1")
                    print_row("Description", desc)

                    qlty_grade = get(attr, "XXQGDS")
                    print_row("Quality", qlty_grade)

                    sq_feet = get(attr, "AHFNAR")
                    print_row("Square feet", sq_feet)

                elif args.print_by_year:
                    # Add this parcel's address info to the list for the given year

                    year = get(attr, "AHACYR")
                    if year and len(str(year)) == 4:
                        if not year_map.get(year):
                            year_map[year] = []

                        st_name = get(attr, "AKPSTN")
                        phys_addr = get(attr, "AKPST_")
                        nhd = get(attr, "XXNEDS")

                        year_map[year].append((phys_addr, st_name, nhd))

                if args.output_map:
                    # Parse this parcel's data and add it to the coordinates list

                    year = get(attr, "AHACYR")
                    if not year and (args.start_year or args.end_year):
                        continue

                    geometry = feature["geometry"]
                    if not geometry.get("rings"):
                        continue

                    parcel = get(attr, "AKPAR_")
                    owner = get(attr, "OWNAM1")
                    nh_code = get(attr, "AKNECD")
                    tax_district = get(attr, "XXDSDS")
                    st_name = get(attr, "AKPSTN")
                    road = get(attr, "AKPSTP")
                    city = get(attr, "XXCYDS")
                    township = get(attr, "XXTWDS")
                    nh = get(attr, "XXNEDS")
                    acres = get(attr, "ACRES")
                    desc = get(attr, "XXDDC1")
                    legal_values = "; ".join(
                        [v for a in legal_fields if (v := get(attr, a))]
                    )

                    # Start a list of HTML for this parcel's popup info
                    html_list = ['<div style="display: block">']

                    phys_addr = get(attr, "AKPST_")
                    if phys_addr:
                        html_list.append(
                            f"<div><strong>{phys_addr} {st_name} {road}</strong></div>"
                        )
                    else:
                        html_list.append(
                            f"<div><strong>{st_name} {road}</strong></div>"
                        )

                    html_list.extend(
                        [
                            f"<div>Parcel #: {parcel}</div>",
                            f"<div>City: {city}</div>",
                            f"<div>Township: {township}</div>",
                            f"<div>Tax district: {tax_district}</div>",
                            f"<div>Neighborhood: {nh}</div>",
                            f"<div>Acreage: {acres:.2f}</div>",
                            f"<div>Legal: {legal_values}</div>",
                            f"<div>Owner: {owner}</div>",
                        ]
                    )

                    grantor = get(attr, "XXGNM1")
                    if grantor and grantor != "UNKNOWN OWNER":
                        html_list.append(f"<div>Grantor: {grantor}</div>")

                    qualified = get(attr, "XXQCDS")
                    if qualified:
                        html_list.append(f"<div>Qualified: {qualified}</div>")

                    desc2 = get(attr, "AHDESC")
                    if desc2:
                        html_list.append(f"<div>Description: {desc2}; {desc}</div>")
                    else:
                        html_list.append(f"<div>Description: {desc}</div>")

                    if year:
                        qlty_grade = get(attr, "XXQGDS")
                        sq_feet = get(attr, "AHFNAR")
                        stories = get(attr, "XGSTPR")
                        bedrooms = get(attr, "AHBED_")
                        bathrooms = get(attr, "AHBTH_")
                        basement = get(attr, "XXBMYN")

                        html_list.extend(
                            [
                                f"<div>Year built: {year}</div>",
                                f"<div>Grade: {qlty_grade}</div>",
                                f"<div>Sq. feet: {sq_feet}</div>",
                                f"<div>Stories: {stories}</div>",
                                f"<div>Bedrooms: {bedrooms}</div>",
                                f"<div>Bathrooms: {bathrooms}</div>",
                                f"<div>Basement: {basement}</div>",
                            ]
                        )

                    html_list.append("</div>")
                    popup_html = "".join(html_list)

                    # Extract (and reverse each pair of) coordinates for this parcel
                    rings = [[l[1], l[0]] for l in geometry["rings"][0]]

                    # Add this parcel's data to the coordinates list
                    coordinates.append(
                        {
                            "html": popup_html,
                            "year": year,
                            "rings": rings,
                        }
                    )

            offset += len(features)

        except requests.exceptions.RequestException as e:
            print(f"Error occurred during request: {e}", file=sys.stderr)

    if not feature_count:
        tty.write("No features returned\n")
        tty.close()
        return

    if args.output_map:
        tty.write("Building map file...\n")

        # Generate map HTML file
        make_map(args.output_map, coordinates)
        tty.write(f"Map saved at {args.output_map}\n")

    if args.print_by_year:
        # Print parcel info grouped by year structures built
        for year, houses in sorted(year_map.items()):
            print(f"\n{year} ({len(houses)})")

            # Sort houses by street and then address number
            for num, st, nhd in sorted(houses, key=itemgetter(1, 0)):
                print(f"  {num} {st} | {nhd}")

    if args.json_dump_file and json_results:
        tty.write("Dumping JSON response to file...\n")

        # Pretty-print JSON to file
        with open(args.json_dump_file, "w", encoding="utf-8") as f:
            json.dump(json_results, f, indent=4, ensure_ascii=False)
            tty.write(f"JSON saved at {args.json_dump_file}\n")

    tty.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GIS Map Customizer")
    parser.add_argument(
        "--print-all-fields",
        action="store_true",
        help="Print all ArcGIS fields for each returned feature",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print minimal ArcGIS fields for each returned feature",
    )
    parser.add_argument(
        "--print-by-year",
        action="store_true",
        help="Print list of street addresses grouped by year structure built",
    )
    parser.add_argument(
        "--json-dump-file",
        "-f",
        type=str,
        help="Path of file to which to dump returned JSON",
    )
    parser.add_argument(
        "--start-year",
        "-s",
        type=int,
        help="Earliest build year of structures to return in results; parcels having structures built earlier are filtered out",
    )
    parser.add_argument(
        "--end-year",
        "-e",
        type=int,
        help="Latest build year of structures to return in results; parcels having structures built later are filtered out",
    )
    parser.add_argument("--city", type=str, help="Filter parcels by city (OWCITY)")
    parser.add_argument(
        "--city-code", type=str, help="Filter parcels by city code (AKCYCD)"
    )
    parser.add_argument(
        "--nh-code",
        type=str,
        help="Filter parcels by neighborhood code (AKNECD)",
    )
    parser.add_argument(
        "--street-num",
        type=int,
        help="Filter parcels by street number (AKPST_)",
    )
    parser.add_argument(
        "--street-name",
        type=str,
        help="Filter parcels by given street name (AKPSTN)",
    )
    parser.add_argument(
        "--min-acres",
        type=int,
        help="Filter parcels by given minimum number of parcel acres",
    )
    parser.add_argument(
        "--output-map",
        "-o",
        type=str,
        help="Path of file to which to output generated map HTML",
    )
    parser.add_argument(
        "--show-prop-lines",
        action="store_true",
        help="Show property lines in generated map",
    )
    parser.add_argument(
        "--land-parcels-only",
        action="store_true",
        help="Include only parcels without structures",
    )

    args = parser.parse_args()
    main(args)
