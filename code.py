import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import pandas as pd
import tempfile
import zipfile
import os
import json
from pathlib import Path
import requests
import numpy as np

# Set page config
st.set_page_config(
    page_title="Agricultural Interactive Map",
    page_icon="🌾",
    layout="wide"
)

# Title and description
st.title("🌾 Agricultural Interactive Map")
st.markdown("Upload shapefiles and toggle agricultural layers to explore spatial data")

# Initialize session state
if 'uploaded_layers' not in st.session_state:
    st.session_state.uploaded_layers = {}
if 'map_center' not in st.session_state:
    st.session_state.map_center = [40.4637, -3.7492]  # Center of Spain (Madrid)
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 6

# Function to get location information
def get_location_info(lat, lon):
    """Get formatted location information"""
    try:
        return f"Lat: {lat:.4f}, Lon: {lon:.4f}"
    except (TypeError, ValueError):
        return "Location unavailable"

# Sidebar for controls
with st.sidebar:
    st.header("🗺️ Map Controls")
    
    # Map center and zoom controls
    st.subheader("🎯 Set Your Farm Location")
    
    # Auto-center on uploaded data
    if st.session_state.uploaded_layers:
        if st.button("🎯 Center on My Data"):
            # Get bounds of all uploaded layers
            all_bounds = []
            for gdf in st.session_state.uploaded_layers.values():
                bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
                all_bounds.extend([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])  # Convert to lat/lon pairs
            
            if all_bounds:
                # Calculate center and appropriate zoom
                lats = [bound[0] for bound in all_bounds]
                lons = [bound[1] for bound in all_bounds]
                center_lat = (min(lats) + max(lats)) / 2
                center_lon = (min(lons) + max(lons)) / 2
                st.session_state.map_center = [center_lat, center_lon]
                
                # Calculate zoom based on extent
                lat_range = max(lats) - min(lats)
                lon_range = max(lons) - min(lons)
                max_range = max(lat_range, lon_range)
                if max_range > 1:
                    st.session_state.map_zoom = 8
                elif max_range > 0.1:
                    st.session_state.map_zoom = 12
                else:
                    st.session_state.map_zoom = 15
    
    st.write("**Custom Location:**")
    col1, col2 = st.columns(2)
    with col1:
        center_lat = st.number_input("Latitude", value=st.session_state.map_center[0], format="%.6f")
    with col2:
        center_lon = st.number_input("Longitude", value=st.session_state.map_center[1], format="%.6f")
    
    zoom_level = st.slider("Zoom Level", min_value=1, max_value=18, value=st.session_state.map_zoom)
    
    # Update session state
    st.session_state.map_center = [center_lat, center_lon]
    st.session_state.map_zoom = zoom_level
    
    st.divider()
    
    # File upload section
    st.subheader("📁 Upload Shapefile")
    st.info("Upload a ZIP file containing your shapefile (.shp, .shx, .dbf, .prj)")
    
    uploaded_file = st.file_uploader(
        "Choose a ZIP file",
        type=['zip'],
        help="Your ZIP file should contain .shp, .shx, .dbf files (and optionally .prj)"
    )
    
    if uploaded_file is not None:
        if st.button("Process Shapefile"):
            try:
                # Create temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Extract ZIP file
                    with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    
                    # Find shapefile
                    shp_files = list(Path(temp_dir).glob("*.shp"))
                    
                    if shp_files:
                        shp_file = shp_files[0]
                        
                        # Read shapefile
                        gdf = gpd.read_file(shp_file)
                        
                        # Convert to WGS84 if needed
                        if gdf.crs != 'EPSG:4326':
                            gdf = gdf.to_crs('EPSG:4326')
                        
                        # Store in session state
                        layer_name = f"Uploaded: {uploaded_file.name}"
                        st.session_state.uploaded_layers[layer_name] = gdf
                        
                        # Auto-center map on uploaded data
                        bounds = gdf.total_bounds
                        center_lat = (bounds[1] + bounds[3]) / 2
                        center_lon = (bounds[0] + bounds[2]) / 2
                        st.session_state.map_center = [center_lat, center_lon]
                        
                        # Set appropriate zoom level
                        lat_range = bounds[3] - bounds[1]
                        lon_range = bounds[2] - bounds[0]
                        max_range = max(lat_range, lon_range)
                        if max_range > 0.5:
                            st.session_state.map_zoom = 10
                        elif max_range > 0.1:
                            st.session_state.map_zoom = 12
                        elif max_range > 0.01:
                            st.session_state.map_zoom = 14
                        else:
                            st.session_state.map_zoom = 16
                        
                        st.success(f"✅ Shapefile loaded successfully!")
                        st.info(f"Features: {len(gdf)}")
                        
                        # Show attribute info
                        if not gdf.empty:
                            st.write("**Attributes:**")
                            st.write(list(gdf.columns))
                    else:
                        st.error("No .shp file found in the ZIP archive")
                        
            except Exception as e:
                st.error(f"Error processing shapefile: {str(e)}")
    
    st.divider()
    
    # Layer controls
    st.subheader("🗂️ Layer Controls")
    
    # Built-in reference layers
    st.write("**📊 Reference Agricultural Layers:**")
    reference_layers = {
        "Soil Quality Zones": st.checkbox("🌱 Soil Quality Zones", value=False, help="Sample soil productivity zones"),
        "Climate Zones": st.checkbox("🌡️ Climate Zones", value=False, help="Agricultural climate classifications"),
        "Elevation Contours": st.checkbox("⛰️ Elevation Contours", value=False, help="Topographic elevation lines"),
        "Water Sources": st.checkbox("💧 Water Sources", value=False, help="Rivers, wells, and water points"),
        "Field Management Zones": st.checkbox("📋 Management Zones", value=False, help="Precision agriculture zones"),
        "Slope Analysis": st.checkbox("📐 Slope Analysis", value=False, help="Terrain slope categories"),
    }
    
    st.divider()
    
    # Uploaded layers section
    if st.session_state.uploaded_layers:
        st.write("**🗂️ Your Uploaded Layers:**")
        uploaded_layer_controls = {}
        for layer_name in st.session_state.uploaded_layers.keys():
            uploaded_layer_controls[layer_name] = st.checkbox(layer_name, value=True)
        
        # Clear uploaded layers
        if st.button("🗑️ Clear All Uploaded Layers"):
            st.session_state.uploaded_layers = {}
            st.rerun()
    else:
        st.info("📁 Upload a shapefile first to see analysis layers")
        st.markdown("💡 **Analysis layers will adapt to your shapefile location:**")
        st.markdown("- 🌱 **Soil Quality Zones** - Productivity analysis for your area")
        st.markdown("- 💧 **Water Sources** - Potential water points near your fields")
        st.markdown("- 🌡️ **Climate Zones** - Local climate classification")
        st.markdown("- 📋 **Management Zones** - Precision agriculture zones")
        st.markdown("- ⛰️ **Elevation Contours** - Topographic analysis")
        st.markdown("- 📐 **Slope Analysis** - Terrain suitability assessment")

# Function to create agricultural reference layers
@st.cache_data
def create_agricultural_reference_layers(bounds):
    """Create reference agricultural layers within the specified bounds"""
    
    # Extract bounds: [minx, miny, maxx, maxy] -> [min_lon, min_lat, max_lon, max_lat]
    min_lon, min_lat, max_lon, max_lat = bounds
    
    # Calculate center and offsets based on actual data extent
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2
    lat_range = max_lat - min_lat
    lon_range = max_lon - min_lon
    
    # Create zones that cover and extend slightly beyond the shapefile area
    lat_buffer = lat_range * 0.2  # 20% buffer
    lon_buffer = lon_range * 0.2
    
    # Expand bounds with buffer
    buffered_min_lat = min_lat - lat_buffer
    buffered_max_lat = max_lat + lat_buffer
    buffered_min_lon = min_lon - lon_buffer
    buffered_max_lon = max_lon + lon_buffer
    
    # Soil Quality Zones (polygons covering your area)
    soil_zones = [
        {
            "name": "High Productivity Zone",
            "geometry": [
                [buffered_min_lat, buffered_min_lon],
                [buffered_min_lat + lat_range * 0.7, buffered_min_lon],
                [buffered_min_lat + lat_range * 0.7, buffered_min_lon + lon_range * 0.6],
                [buffered_min_lat, buffered_min_lon + lon_range * 0.6]
            ],
            "quality": "High",
            "ph": "6.5-7.0",
            "organic_matter": "3.2%"
        },
        {
            "name": "Medium Productivity Zone", 
            "geometry": [
                [center_lat - lat_range * 0.3, center_lon - lon_range * 0.2],
                [center_lat + lat_range * 0.4, center_lon - lon_range * 0.2],
                [center_lat + lat_range * 0.4, center_lon + lon_range * 0.5],
                [center_lat - lat_range * 0.3, center_lon + lon_range * 0.5]
            ],
            "quality": "Medium",
            "ph": "6.0-6.5",
            "organic_matter": "2.1%"
        },
        {
            "name": "Lower Productivity Zone",
            "geometry": [
                [buffered_max_lat - lat_range * 0.5, buffered_max_lon - lon_range * 0.7],
                [buffered_max_lat, buffered_max_lon - lon_range * 0.7],
                [buffered_max_lat, buffered_max_lon],
                [buffered_max_lat - lat_range * 0.5, buffered_max_lon]
            ],
            "quality": "Lower",
            "ph": "5.5-6.0", 
            "organic_matter": "1.8%"
        }
    ]
    
    # Water sources (points within your area)
    water_points = [
        {"name": "Well #1", "lat": center_lat + lat_range * 0.2, "lon": center_lon - lon_range * 0.3, "type": "Borehole", "depth": "45m"},
        {"name": "River Access", "lat": center_lat - lat_range * 0.1, "lon": center_lon + lon_range * 0.2, "type": "Surface Water", "flow": "Seasonal"},
        {"name": "Reservoir", "lat": center_lat + lat_range * 0.1, "lon": center_lon + lon_range * 0.4, "type": "Storage", "capacity": "50,000L"},
        {"name": "Irrigation Point", "lat": min_lat + lat_range * 0.3, "lon": min_lon + lon_range * 0.7, "type": "Irrigation", "pressure": "3.5 bar"}
    ]
    
    # Climate zones (larger area coverage)
    climate_zones = [
        {
            "name": "Local Climate Zone",
            "geometry": [
                [buffered_min_lat, buffered_min_lon],
                [buffered_max_lat, buffered_min_lon],
                [buffered_max_lat, buffered_max_lon],
                [buffered_min_lat, buffered_max_lon]
            ],
            "climate": "Mediterranean/Continental",
            "rainfall": "400-700mm",
            "temp_range": "0-40°C"
        }
    ]
    
    # Management zones (precision agriculture within your area)
    zone_width = lon_range / 3
    zone_height = lat_range / 2
    
    mgmt_zones = [
        {
            "name": "Zone A - High Input",
            "geometry": [
                [min_lat + lat_range * 0.1, min_lon + lon_range * 0.1],
                [min_lat + lat_range * 0.1 + zone_height, min_lon + lon_range * 0.1],
                [min_lat + lat_range * 0.1 + zone_height, min_lon + lon_range * 0.1 + zone_width],
                [min_lat + lat_range * 0.1, min_lon + lon_range * 0.1 + zone_width]
            ],
            "zone": "A",
            "management": "High Input",
            "fertilizer": "200kg/ha",
            "yield_target": "8 t/ha"
        },
        {
            "name": "Zone B - Standard",
            "geometry": [
                [min_lat + lat_range * 0.4, min_lon + lon_range * 0.3],
                [min_lat + lat_range * 0.4 + zone_height, min_lon + lon_range * 0.3],
                [min_lat + lat_range * 0.4 + zone_height, min_lon + lon_range * 0.3 + zone_width],
                [min_lat + lat_range * 0.4, min_lon + lon_range * 0.3 + zone_width]
            ],
            "zone": "B", 
            "management": "Standard",
            "fertilizer": "150kg/ha",
            "yield_target": "6 t/ha"
        },
        {
            "name": "Zone C - Low Input",
            "geometry": [
                [center_lat, center_lon + lon_range * 0.1],
                [center_lat + zone_height * 0.8, center_lon + lon_range * 0.1],
                [center_lat + zone_height * 0.8, center_lon + lon_range * 0.1 + zone_width],
                [center_lat, center_lon + lon_range * 0.1 + zone_width]
            ],
            "zone": "C",
            "management": "Low Input",
            "fertilizer": "100kg/ha",
            "yield_target": "4 t/ha"
        }
    ]
    
    # Elevation contours (lines across your area)
    contour_lines = [
        {
            "name": "Lower elevation contour",
            "coords": [
                [min_lat + lat_range * 0.2, buffered_min_lon],
                [min_lat + lat_range * 0.3, center_lon],
                [min_lat + lat_range * 0.4, buffered_max_lon]
            ],
            "elevation": "Base level"
        },
        {
            "name": "Higher elevation contour", 
            "coords": [
                [min_lat + lat_range * 0.6, buffered_min_lon],
                [min_lat + lat_range * 0.7, center_lon],
                [min_lat + lat_range * 0.8, buffered_max_lon]
            ],
            "elevation": "+20m"
        }
    ]
    
    # Slope analysis zones
    slope_zones = [
        {
            "name": "Flat Area (0-2%)",
            "geometry": [
                [center_lat - lat_range * 0.2, center_lon - lon_range * 0.4],
                [center_lat + lat_range * 0.1, center_lon - lon_range * 0.4],
                [center_lat + lat_range * 0.1, center_lon + lon_range * 0.1],
                [center_lat - lat_range * 0.2, center_lon + lon_range * 0.1]
            ],
            "slope": "0-2%",
            "suitability": "Excellent for machinery",
            "erosion_risk": "Low"
        },
        {
            "name": "Gentle Slope (2-8%)",
            "geometry": [
                [min_lat + lat_range * 0.6, min_lon + lon_range * 0.5],
                [min_lat + lat_range * 0.9, min_lon + lon_range * 0.5],
                [min_lat + lat_range * 0.9, max_lon - lon_range * 0.1],
                [min_lat + lat_range * 0.6, max_lon - lon_range * 0.1]
            ],
            "slope": "2-8%",
            "suitability": "Good for most crops",
            "erosion_risk": "Moderate"
        },
        {
            "name": "Steeper Area (8-15%)",
            "geometry": [
                [max_lat - lat_range * 0.3, min_lon + lon_range * 0.1],
                [max_lat, min_lon + lon_range * 0.1],
                [max_lat, min_lon + lon_range * 0.4],
                [max_lat - lat_range * 0.3, min_lon + lon_range * 0.4]
            ],
            "slope": "8-15%",
            "suitability": "Limited machinery access",
            "erosion_risk": "High"
        }
    ]
    
    return soil_zones, water_points, climate_zones, mgmt_zones, contour_lines, slope_zones

# Main map
st.header("🗺️ Interactive Agricultural Map")

# Create the map
m = folium.Map(
    location=st.session_state.map_center,
    zoom_start=st.session_state.map_zoom,
    tiles='OpenStreetMap'
)

# Add tile layer options
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attr='Esri',
    name='Satellite',
    overlay=False,
    control=True
).add_to(m)

folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}',
    attr='Esri',
    name='Terrain',
    overlay=False,
    control=True
).add_to(m)

folium.TileLayer(
    tiles='CartoDB positron',
    name='Light Map',
    overlay=False,
    control=True
).add_to(m)

# Add reference layers if selected and shapefile is uploaded
if any(reference_layers.values()) and st.session_state.uploaded_layers:
    # Get combined bounds of all uploaded layers
    all_bounds = []
    for gdf in st.session_state.uploaded_layers.values():
        all_bounds.append(gdf.total_bounds)  # [minx, miny, maxx, maxy]
    
    # Calculate overall bounds
    min_x = min([bounds[0] for bounds in all_bounds])
    min_y = min([bounds[1] for bounds in all_bounds])
    max_x = max([bounds[2] for bounds in all_bounds])
    max_y = max([bounds[3] for bounds in all_bounds])
    overall_bounds = [min_x, min_y, max_x, max_y]
    
    soil_zones, water_points, climate_zones, mgmt_zones, contour_lines, slope_zones = create_agricultural_reference_layers(overall_bounds)
    
    # Add soil quality zones
    if reference_layers["Soil Quality Zones"]:
        soil_group = folium.FeatureGroup(name="🌱 Soil Quality Zones")
        for zone in soil_zones:
            coords = [[coord[0], coord[1]] for coord in zone["geometry"]]
            coords.append(coords[0])  # Close the polygon
            
            popup_content = f"""
            <b>{zone['name']}</b><br>
            Quality: {zone['quality']}<br>
            pH: {zone['ph']}<br>
            Organic Matter: {zone['organic_matter']}
            """
            
            folium.Polygon(
                locations=coords,
                popup=folium.Popup(popup_content, max_width=200),
                tooltip=zone['name'],
                color='green',
                fillColor='lightgreen',
                fillOpacity=0.4
            ).add_to(soil_group)
        soil_group.add_to(m)
    
    # Add water sources
    if reference_layers["Water Sources"]:
        water_group = folium.FeatureGroup(name="💧 Water Sources")
        for point in water_points:
            popup_content = f"""
            <b>{point['name']}</b><br>
            Type: {point['type']}<br>
            {'Depth: ' + point.get('depth', '') if 'depth' in point else ''}
            {'Flow: ' + point.get('flow', '') if 'flow' in point else ''}
            {'Capacity: ' + point.get('capacity', '') if 'capacity' in point else ''}
            """
            
            folium.Marker(
                location=[point['lat'], point['lon']],
                popup=folium.Popup(popup_content, max_width=200),
                tooltip=point['name'],
                icon=folium.Icon(color='blue', icon='tint', prefix='fa')
            ).add_to(water_group)
        water_group.add_to(m)
    
    # Add climate zones
    if reference_layers["Climate Zones"]:
        climate_group = folium.FeatureGroup(name="🌡️ Climate Zones")
        for zone in climate_zones:
            coords = [[coord[0], coord[1]] for coord in zone["geometry"]]
            coords.append(coords[0])
            
            popup_content = f"""
            <b>{zone['name']}</b><br>
            Climate: {zone['climate']}<br>
            Rainfall: {zone['rainfall']}<br>
            Temperature: {zone['temp_range']}
            """
            
            folium.Polygon(
                locations=coords,
                popup=folium.Popup(popup_content, max_width=200),
                tooltip=zone['name'],
                color='orange',
                fillColor='yellow',
                fillOpacity=0.3
            ).add_to(climate_group)
        climate_group.add_to(m)
    
    # Add management zones
    if reference_layers["Field Management Zones"]:
        mgmt_group = folium.FeatureGroup(name="📋 Management Zones")
        for zone in mgmt_zones:
            coords = [[coord[0], coord[1]] for coord in zone["geometry"]]
            coords.append(coords[0])
            
            popup_content = f"""
            <b>{zone['name']}</b><br>
            Zone: {zone['zone']}<br>
            Management: {zone['management']}<br>
            Fertilizer: {zone['fertilizer']}<br>
            Yield Target: {zone['yield_target']}
            """
            
            folium.Polygon(
                locations=coords,
                popup=folium.Popup(popup_content, max_width=200),
                tooltip=zone['name'],
                color='purple',
                fillColor='lavender',
                fillOpacity=0.4
            ).add_to(mgmt_group)
        mgmt_group.add_to(m)
    
    # Add elevation contours
    if reference_layers["Elevation Contours"]:
        contour_group = folium.FeatureGroup(name="⛰️ Elevation Contours")
        for contour in contour_lines:
            coords = [[coord[0], coord[1]] for coord in contour["coords"]]
            
            folium.PolyLine(
                locations=coords,
                popup=f"<b>{contour['name']}</b><br>Elevation: {contour['elevation']}",
                tooltip=contour['name'],
                color='brown',
                weight=2
            ).add_to(contour_group)
        contour_group.add_to(m)
    
    # Add slope analysis
    if reference_layers["Slope Analysis"]:
        slope_group = folium.FeatureGroup(name="📐 Slope Analysis")
        for zone in slope_zones:
            coords = [[coord[0], coord[1]] for coord in zone["geometry"]]
            coords.append(coords[0])
            
            popup_content = f"""
            <b>{zone['name']}</b><br>
            Slope: {zone['slope']}<br>
            Suitability: {zone['suitability']}<br>
            Erosion Risk: {zone['erosion_risk']}
            """
            
            color = 'darkgreen' if '0-2%' in zone['name'] else 'darkorange'
            fill_color = 'lightgreen' if '0-2%' in zone['name'] else 'lightyellow'
            
            folium.Polygon(
                locations=coords,
                popup=folium.Popup(popup_content, max_width=200),
                tooltip=zone['name'],
                color=color,
                fillColor=fill_color,
                fillOpacity=0.4
            ).add_to(slope_group)
        slope_group.add_to(m)

# Add uploaded layers
if st.session_state.uploaded_layers:
    uploaded_layer_controls = {}
    for layer_name in st.session_state.uploaded_layers.keys():
        uploaded_layer_controls[layer_name] = True  # Default to True if not in sidebar yet
    
    for layer_name, gdf in st.session_state.uploaded_layers.items():
        if uploaded_layer_controls.get(layer_name, True):
            uploaded_group = folium.FeatureGroup(name=layer_name)
            
            for idx, row in gdf.iterrows():
                geom = row.geometry
                
                # Create popup content with attributes
                popup_content = f"<b>{layer_name}</b><br>"
                for col in gdf.columns:
                    if col != 'geometry':
                        popup_content += f"{col}: {row[col]}<br>"
                
                if geom.geom_type == 'Point':
                    folium.Marker(
                        location=[geom.y, geom.x],
                        popup=popup_content,
                        tooltip=f"Feature {idx}",
                        icon=folium.Icon(color='red', icon='info-sign')
                    ).add_to(uploaded_group)
                
                elif geom.geom_type in ['Polygon', 'MultiPolygon']:
                    # Convert geometry to GeoJSON
                    geojson = gpd.GeoSeries([geom]).to_json()
                    geojson_dict = json.loads(geojson)
                    
                    folium.GeoJson(
                        geojson_dict,
                        popup=folium.Popup(popup_content, max_width=300),
                        tooltip=f"Feature {idx}",
                        style_function=lambda x: {
                            'fillColor': 'purple',
                            'color': 'purple',
                            'weight': 2,
                            'fillOpacity': 0.3
                        }
                    ).add_to(uploaded_group)
                
                elif geom.geom_type in ['LineString', 'MultiLineString']:
                    # Convert to coordinates
                    if geom.geom_type == 'LineString':
                        coords = [[coord[1], coord[0]] for coord in geom.coords]
                    else:  # MultiLineString
                        coords = []
                        for line in geom.geoms:
                            coords.extend([[coord[1], coord[0]] for coord in line.coords])
                    
                    folium.PolyLine(
                        locations=coords,
                        popup=popup_content,
                        tooltip=f"Feature {idx}",
                        color='purple',
                        weight=3
                    ).add_to(uploaded_group)
            
            uploaded_group.add_to(m)

# Add layer control
folium.LayerControl().add_to(m)

# Add a marker at the current center location
try:
    center_marker = folium.Marker(
        location=st.session_state.map_center,
        popup=f"📍 Map Center<br>{get_location_info(st.session_state.map_center[0], st.session_state.map_center[1])}",
        tooltip="Map Center",
        icon=folium.Icon(color='red', icon='crosshairs', prefix='fa')
    ).add_to(m)
except Exception as e:
    st.error(f"Error adding center marker: {str(e)}")

# Display the map
map_data = st_folium(m, width=1200, height=600)

# Display information about clicked features
if map_data['last_object_clicked_popup']:
    st.subheader("📍 Selected Feature Information")
    st.write(map_data['last_object_clicked_popup'])

# Statistics section
col1, col2, col3 = st.columns(3)

with col1:
    active_ref_layers = len([k for k, v in reference_layers.items() if v])
    st.metric("🔍 Reference Layers", active_ref_layers)

with col2:
    if st.session_state.uploaded_layers:
        active_uploaded = len([name for name in st.session_state.uploaded_layers.keys() 
                             if uploaded_layer_controls.get(name, True)])
        st.metric("📁 Your Layers", active_uploaded)
    else:
        st.metric("📁 Your Layers", 0)

with col3:
    total_features = 0
    for gdf in st.session_state.uploaded_layers.values():
        total_features += len(gdf)
    st.metric("🎯 Total Features", total_features)

# Instructions
with st.expander("📋 Instructions"):
    st.markdown("""
    ### How to use this Agricultural Interactive Map:
    
    1. **Upload Shapefiles**: 
       - Prepare a ZIP file containing your shapefile components (.shp, .shx, .dbf, and optionally .prj)
       - Use the file uploader in the sidebar
       - Click "Process Shapefile" to add it to the map
    
    2. **Toggle Layers**: 
       - Use the checkboxes in the sidebar to show/hide different layers
       - Both built-in sample layers and uploaded layers can be toggled
    
    3. **Interact with the Map**:
       - Click on features to see popup information
       - Use the layer control in the top-right of the map
       - Zoom and pan to explore different areas
    
    4. **Adjust Map View**:
       - Change the center coordinates and zoom level in the sidebar
       - Switch between different base map styles using the layer control
    
    ### Reference Agricultural Layers:
    
    The app now includes several built-in reference layers that adapt to your map location:
    
    - **🌱 Soil Quality Zones**: Productivity zones with pH and organic matter data
    - **🌡️ Climate Zones**: Agricultural climate classifications with rainfall/temperature
    - **⛰️ Elevation Contours**: Topographic lines showing terrain elevation
    - **💧 Water Sources**: Wells, rivers, and water storage locations
    - **📋 Management Zones**: Precision agriculture zones with fertilizer/yield targets
    - **📐 Slope Analysis**: Terrain slope categories for machinery suitability
    
    These reference layers are generated around your current map center and provide context for your uploaded farm data.
    """)