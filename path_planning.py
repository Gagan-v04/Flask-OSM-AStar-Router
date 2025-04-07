# path_planning_logic.py
import os
from pyrosm import OSM
import networkx as nx
from shapely.geometry import LineString, MultiLineString
from geopy.distance import geodesic
import time
import traceback
import re

DEFAULT_SPEEDS_KPH = {
    'motorway': 100, 'trunk': 85, 'primary': 65, 'secondary': 55, 'tertiary': 45,
    'unclassified': 30, 'residential': 30, 'motorway_link': 50, 'trunk_link': 45,
    'primary_link': 40, 'secondary_link': 35, 'tertiary_link': 30, 'living_street': 20,
    'service': 15, 'road': 30, 'track': 15,
}
FALLBACK_SPEED_KPH = 25
MAX_SPEED_KPH_HEURISTIC = 110
MAX_SPEED_MPS_HEURISTIC = MAX_SPEED_KPH_HEURISTIC * 1000 / 3600

def estimate_speed_mps(highway_type, maxspeed_str):
    speed_kph = None
    if maxspeed_str and isinstance(maxspeed_str, str):
        match = re.match(r'^(\d+(\.\d+)?)', maxspeed_str.lower().strip())
        if match:
            speed_val = float(match.group(1))
            speed_kph = speed_val * 1.60934 if 'mph' in maxspeed_str else speed_val
    if speed_kph is None and highway_type in DEFAULT_SPEEDS_KPH: speed_kph = DEFAULT_SPEEDS_KPH[highway_type]
    if speed_kph is None: speed_kph = FALLBACK_SPEED_KPH
    return max(speed_kph, 1) * 1000 / 3600

def initialize_osm_and_graph(pbf_path):
    print(f"Initializing OSM and Graph for TIME-based routing from: {pbf_path}")
    start_time = time.time()
    try:
        print("Loading OSM data..."); osm = OSM(pbf_path)
        print("Extracting driving network with 'maxspeed' attribute..."); 
        drive_net = osm.get_network(network_type="driving", extra_attributes=["maxspeed"])
        if drive_net is None or drive_net.empty: print(" No drivable road network found."); return None
        print(f"Extracted {len(drive_net)} road segments."); print("Building graph with TIME weights and LENGTH attribute...")
        G = nx.Graph(); gdf = drive_net[drive_net["geometry"].notnull()].copy()
        edge_count = 0; skipped_edges = 0
        for idx, row in gdf.iterrows():
            geom = row["geometry"]; highway_type = row.get("highway"); maxspeed_str = row.get("maxspeed")
            if not isinstance(maxspeed_str, str): maxspeed_str = None
            speed_mps = estimate_speed_mps(highway_type, maxspeed_str)
            if speed_mps <= 0: skipped_edges+=1; continue
            if isinstance(geom, (LineString, MultiLineString)):
                lines = [geom] if isinstance(geom, LineString) else list(geom.geoms)
                for line in lines:
                    if len(line.coords) < 2: continue
                    coords = list(line.coords)
                    for i in range(len(coords) - 1):
                        u_node, v_node = coords[i], coords[i+1]
                        if not (-180 <= u_node[0] <= 180 and -90 <= u_node[1] <= 90 and -180 <= v_node[0] <= 180 and -90 <= v_node[1] <= 90): skipped_edges += 1; continue
                        try: distance_m = geodesic((u_node[1], u_node[0]), (v_node[1], v_node[0])).meters
                        except ValueError: skipped_edges += 1; continue
                        if distance_m <= 0: skipped_edges += 1; continue
                        time_seconds = distance_m / speed_mps
                        G.add_edge(u_node, v_node, weight=time_seconds, length=distance_m)
                        edge_count += 1
        if G.number_of_nodes() == 0: print(" Graph built has 0 nodes."); return None
        print(f" Built graph ({G.number_of_nodes()} nodes, {edge_count} edges). Skipped {skipped_edges} invalid segments.")
        end_time = time.time(); print(f"Graph initialization complete in {end_time - start_time:.2f} seconds.")
        return G
    except ImportError as e: print(f" Import error: {e}"); raise
    except Exception as e: print(f" Error during init: {e}"); traceback.print_exc(); raise

def find_nearest_node(G, coord_lat_lon):
    if G is None:
        print(" Graph is None in find_nearest_node.")
        return None
    target_lat, target_lon = coord_lat_lon
    min_dist_sq = float('inf')
    nearest_node = None
    if not G.nodes:
        print(" Graph has no nodes.")
        return None
    for node_lon, node_lat in G.nodes:
        dist_sq = (node_lat - target_lat)**2 + (node_lon - target_lon)**2
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq
            nearest_node = (node_lon, node_lat)
    if nearest_node:
        try:
            final_dist = geodesic((target_lat, target_lon), (nearest_node[1], nearest_node[0])).meters
            print(f"Found nearest node {nearest_node} at approx {final_dist:.2f}m")
        except ValueError:
            print(f"Found nearest {nearest_node}, dist calc failed.")
    else:
        print(" No nearest node found.")
    return nearest_node

def time_heuristic(u_node_lonlat, v_node_lonlat):
    try:
        dist_meters = geodesic((u_node_lonlat[1], u_node_lonlat[0]), (v_node_lonlat[1], v_node_lonlat[0])).meters
        return dist_meters / MAX_SPEED_MPS_HEURISTIC
    except ValueError:
        return float('inf')

def calculate_shortest_path(start_coord_lat_lon, end_coord_lat_lon, pbf_path):
    """Calculates fastest path and returns path, time (sec), and distance (m)."""
    print(f"\n--- Calculating FASTEST Path & Stats ---")
    print(f"Start: {start_coord_lat_lon}, End: {end_coord_lat_lon}, PBF: {pbf_path}")
    try:
        G = initialize_osm_and_graph(pbf_path)
        if G is None:
            return None
        start_node = find_nearest_node(G, start_coord_lat_lon)
        end_node = find_nearest_node(G, end_coord_lat_lon)
        if start_node is None or end_node is None:
            return None
        print(f"Graph Start: {start_node}, Graph End: {end_node}")
        if start_node == end_node:
             print(" Start/End nodes same.")
             return {"path": [list(start_coord_lat_lon), list(end_coord_lat_lon)], "time_sec": 0, "dist_m": 0}

        print("Running A* search (minimizing time)...")
        path_lon_lat = None
        try:
            path_lon_lat = nx.astar_path(G, start_node, end_node, heuristic=time_heuristic, weight='weight')
            print(f"A* found path ({len(path_lon_lat)} nodes).")

            # --- CALCULATE TOTAL TIME AND DISTANCE ---
            # Use the path found (list of (lon, lat) nodes) and the graph weights
            # Ensure path has at least 2 nodes to calculate weight
            total_seconds = 0
            total_meters = 0
            if len(path_lon_lat) >= 2:
                try:
                    # Calculate total time using 'weight' attribute
                    total_seconds = nx.path_weight(G, path_lon_lat, weight='weight')
                    # Calculate total distance using 'length' attribute
                    total_meters = nx.path_weight(G, path_lon_lat, weight='length')
                    print(f"Calculated total time: {total_seconds:.2f} sec, total distance: {total_meters:.2f} m")
                except Exception as calc_e:
                     print(f" Could not calculate path weight/length: {calc_e}")
                     # Set to None or 0 if calculation fails? Set to None for clarity.
                     total_seconds = None
                     total_meters = None

            # Convert path nodes to [lat, lon] format for Leaflet
            path_lat_lon = [[coord[1], coord[0]] for coord in path_lon_lat]
            final_path = [list(start_coord_lat_lon)] + path_lat_lon + [list(end_coord_lat_lon)]

            return {
                "path": final_path,
                "time_sec": total_seconds,
                "dist_m": total_meters
            }

        except nx.NetworkXNoPath:
            print(" No path found (A*).")
            return None
        except nx.NodeNotFound as e:
            print(f" Node not found (A*): {e}")
            return None

    except Exception as e:
        print(f" Error in calculate_shortest_path: {e}")
        traceback.print_exc()
        return None

