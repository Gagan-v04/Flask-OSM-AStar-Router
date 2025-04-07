import os
from pyrosm import OSM

# Step 1: Define directories for raw and processed data
raw_data_dir = "data/raw/"  # Path to raw OSM data
processed_data_dir = "data/processed/"  # Path to save processed GeoJSON files

# Ensure the processed data directory exists
if not os.path.exists(processed_data_dir):
    os.makedirs(processed_data_dir)

# Step 2: Iterate through all .osm.pbf files in the raw data directory
for filename in os.listdir(raw_data_dir):
    if filename.endswith(".pbf"):
        # Define file paths
        input_file = os.path.join(raw_data_dir, filename)
        
        # Correct the output file name by ensuring it ends with .geojson
        output_file = os.path.join(processed_data_dir, filename.replace(".pbf", ".geojson"))

        print(f"Processing file: {filename}...")

        # Step 3: Initialize the OSM parser object
        osm = OSM(input_file)

        # Step 4: Convert the entire map data to GeoJSON format
        print(f"Converting {filename} to GeoJSON...")
        osm.to_file(output_file, driver="GeoJSON")
        
        print(f"Saved processed data to: {output_file}")

print("Script completed.")
