import streamlit as st
import geopandas as gpd
import folium
from folium import plugins
import tempfile
import zipfile
import os
import requests
import numpy as np
import pandas as pd
from streamlit_folium import st_folium
from shapely.geometry import Point
from shapely.ops import unary_union
import time
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configure page
st.set_page_config(
    page_title="Farm Soil Analysis",
    page_icon="🌾",
    layout="wide"
)

def extract_shapefile(uploaded_file):
    """Extract shapefile from uploaded ZIP"""
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Save uploaded file
        zip_path = os.path.join(temp_dir, "shapefile.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_file.read())
        
        # Extract ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find .shp file
        shp_files = [f for f in os.listdir(temp_dir) if f.endswith('.shp')]
        if not shp_files:
            return None, "No .shp file found in ZIP"
        
        shp_path = os.path.join(temp_dir, shp_files[0])
        return shp_path, None
        
    except Exception as e:
        return None, f"Error extracting file: {str(e)}"

def get_soil_data_soilgrids(lat, lon):
    """Get soil data from SoilGrids API"""
    try:
        # SoilGrids REST API endpoint
        base_url = "https://rest.soilgrids.org/soilgrids/v2.0/properties/query"
        
        # Parameters for soil properties
        params = {
            'lon': lon,
            'lat': lat,
            'property': ['bdod', 'cec', 'clay', 'nitrogen', 'ocd', 'ocs', 'phh2o', 'sand', 'silt', 'soc'],
            'depth': ['0-5cm', '5-15cm'],
            'value': ['mean']
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract soil properties (0-5cm depth)
            properties = data.get('properties', {})
            
            soil_info = {
                'ph': None,
                'organic_carbon': None,
                'clay_content': None,
                'sand_content': None,
                'silt_content': None,
                'nitrogen': None,
                'cec': None,  # Cation Exchange Capacity
                'bulk_density': None
            }
            
            # Extract pH (0-5cm)
            if 'phh2o' in properties:
                ph_data = properties['phh2o']['depths'][0]['values']['mean']
                soil_info['ph'] = ph_data / 10  # SoilGrids returns pH * 10
            
            # Extract organic carbon (0-5cm)
            if 'soc' in properties:
                soc_data = properties['soc']['depths'][0]['values']['mean']
                soil_info['organic_carbon'] = soc_data / 10  # Convert to g/kg
            
            # Extract clay content (0-5cm)
            if 'clay' in properties:
                clay_data = properties['clay']['depths'][0]['values']['mean']
                soil_info['clay_content'] = clay_data / 10  # Convert to %
            
            # Extract sand content (0-5cm)
            if 'sand' in properties:
                sand_data = properties['sand']['depths'][0]['values']['mean']
                soil_info['sand_content'] = sand_data / 10  # Convert to %
            
            # Extract silt content (0-5cm)
            if 'silt' in properties:
                silt_data = properties['silt']['depths'][0]['values']['mean']
                soil_info['silt_content'] = silt_data / 10  # Convert to %
            
            # Extract nitrogen (0-5cm)
            if 'nitrogen' in properties:
                n_data = properties['nitrogen']['depths'][0]['values']['mean']
                soil_info['nitrogen'] = n_data / 100  # Convert to g/kg
            
            # Extract CEC (0-5cm)
            if 'cec' in properties:
                cec_data = properties['cec']['depths'][0]['values']['mean']
                soil_info['cec'] = cec_data / 10  # Convert to cmol/kg
            
            # Extract bulk density (0-5cm)
            if 'bdod' in properties:
                bd_data = properties['bdod']['depths'][0]['values']['mean']
                soil_info['bulk_density'] = bd_data / 100  # Convert to g/cm³
            
            return soil_info, None
            
        else:
            return None, f"API Error: {response.status_code}"
            
    except Exception as e:
        return None, f"Error fetching soil data: {str(e)}"

def classify_soil_quality(soil_data):
    """Classify soil quality based on multiple parameters"""
    score = 0
    max_score = 0
    details = {}
    
    # pH scoring (optimal range 6.0-7.0)
    if soil_data['ph'] is not None:
        ph = soil_data['ph']
        if 6.0 <= ph <= 7.0:
            ph_score = 5
        elif 5.5 <= ph < 6.0 or 7.0 < ph <= 7.5:
            ph_score = 4
        elif 5.0 <= ph < 5.5 or 7.5 < ph <= 8.0:
            ph_score = 3
        elif 4.5 <= ph < 5.0 or 8.0 < ph <= 8.5:
            ph_score = 2
        else:
            ph_score = 1
        score += ph_score
        max_score += 5
        details['pH Score'] = f"{ph_score}/5 (pH: {ph:.1f})"
    
    # Organic carbon scoring (higher is better, typical range 0-50 g/kg)
    if soil_data['organic_carbon'] is not None:
        oc = soil_data['organic_carbon']
        if oc >= 20:
            oc_score = 5
        elif oc >= 15:
            oc_score = 4
        elif oc >= 10:
            oc_score = 3
        elif oc >= 5:
            oc_score = 2
        else:
            oc_score = 1
        score += oc_score
        max_score += 5
        details['Organic Carbon Score'] = f"{oc_score}/5 ({oc:.1f} g/kg)"
    
    # Clay content scoring (moderate clay is good, 20-40% optimal)
    if soil_data['clay_content'] is not None:
        clay = soil_data['clay_content']
        if 20 <= clay <= 40:
            clay_score = 5
        elif 15 <= clay < 20 or 40 < clay <= 50:
            clay_score = 4
        elif 10 <= clay < 15 or 50 < clay <= 60:
            clay_score = 3
        elif 5 <= clay < 10 or 60 < clay <= 70:
            clay_score = 2
        else:
            clay_score = 1
        score += clay_score
        max_score += 5
        details['Clay Content Score'] = f"{clay_score}/5 ({clay:.1f}%)"
    
    # Calculate overall quality
    if max_score > 0:
        quality_percentage = (score / max_score) * 100
        
        if quality_percentage >= 80:
            quality = "Excellent"
            color = "#2E8B57"  # Sea Green
        elif quality_percentage >= 65:
            quality = "Good"
            color = "#9ACD32"  # Yellow Green
        elif quality_percentage >= 50:
            quality = "Fair"
            color = "#DAA520"  # Goldenrod
        elif quality_percentage >= 35:
            quality = "Poor"
            color = "#CD853F"  # Peru
        else:
            quality = "Very Poor"
            color = "#A0522D"  # Sienna
            
        return quality, color, quality_percentage, details
    else:
        return "Unknown", "#808080", 0, {}

def generate_sample_points(farm_geom, num_points=12):
    """Generate sample points within farm boundary for soil analysis"""
    minx, miny, maxx, maxy = farm_geom.bounds
    points = []
    
    attempts = 0
    while len(points) < num_points and attempts < num_points * 10:
        x = np.random.uniform(minx, maxx)
        y = np.random.uniform(miny, maxy)
        point = Point(x, y)
        
        if farm_geom.contains(point):
            points.append((y, x))  # (lat, lon) for API calls
        attempts += 1
    
    return points

def create_layered_map(gdf, soil_results, active_layers):
    """Create map with toggleable analysis layers"""
    # Get the center of the shapefile
    bounds = gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    
    # Create base map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles='OpenStreetMap'
    )
    
    # Add satellite layer option
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Add farm boundary (always visible)
    folium.GeoJson(
        gdf.to_json(),
        style_function=lambda feature: {
            'fillColor': 'transparent',
            'color': 'red',
            'weight': 3,
            'opacity': 1
        },
        popup=folium.Popup("Farm Boundary", parse_html=True),
        tooltip="Farm Area"
    ).add_to(m)
    
    # Layer 1: Overall Soil Quality
    if active_layers.get('overall_quality', False) and soil_results:
        quality_group = folium.FeatureGroup(name="Overall Soil Quality")
        
        for result in soil_results:
            popup_content = f"""
            <b>Soil Quality Point {result['point']}</b><br>
            <b>Quality:</b> {result['quality']} ({result['percentage']:.1f}%)<br>
            <b>pH:</b> {result['ph']:.1f if result['ph'] else 'N/A'}<br>
            <b>Organic Carbon:</b> {result['organic_carbon']:.1f if result['organic_carbon'] else 'N/A'} g/kg<br>
            <b>Clay Content:</b> {result['clay_content']:.1f if result['clay_content'] else 'N/A'}%
            """
            
            folium.CircleMarker(
                location=[result['lat'], result['lon']],
                radius=15,
                popup=folium.Popup(popup_content, parse_html=True),
                color='black',
                weight=2,
                fillColor=get_quality_color(result['quality']),
                fillOpacity=0.8,
                tooltip=f"Overall Quality: {result['quality']}"
            ).add_to(quality_group)
        
        quality_group.add_to(m)
    
    # Layer 2: pH Analysis
    if active_layers.get('ph_analysis', False) and soil_results:
        ph_group = folium.FeatureGroup(name="pH Analysis")
        
        for result in soil_results:
            if result['ph'] is not None:
                ph_color = get_ph_color(result['ph'])
                ph_status = get_ph_status(result['ph'])
                
                popup_content = f"""
                <b>pH Analysis Point {result['point']}</b><br>
                <b>pH Value:</b> {result['ph']:.1f}<br>
                <b>Status:</b> {ph_status}<br>
                <b>Optimal Range:</b> 6.0 - 7.0
                """
                
                folium.CircleMarker(
                    location=[result['lat'], result['lon']],
                    radius=12,
                    popup=folium.Popup(popup_content, parse_html=True),
                    color='white',
                    weight=2,
                    fillColor=ph_color,
                    fillOpacity=0.7,
                    tooltip=f"pH: {result['ph']:.1f} ({ph_status})"
                ).add_to(ph_group)
        
        ph_group.add_to(m)
    
    # Layer 3: Nutrient Analysis
    if active_layers.get('nutrient_analysis', False) and soil_results:
        nutrient_group = folium.FeatureGroup(name="Nutrient Analysis")
        
        for result in soil_results:
            if result['organic_carbon'] is not None or result['nitrogen'] is not None:
                nutrient_score = calculate_nutrient_score(result)
                nutrient_color = get_nutrient_color(nutrient_score)
                
                popup_content = f"""
                <b>Nutrient Analysis Point {result['point']}</b><br>
                <b>Organic Carbon:</b> {result['organic_carbon']:.1f if result['organic_carbon'] else 'N/A'} g/kg<br>
                <b>Nitrogen:</b> {result['nitrogen']:.2f if result['nitrogen'] else 'N/A'} g/kg<br>
                <b>CEC:</b> {result['cec']:.1f if result['cec'] else 'N/A'} cmol/kg<br>
                <b>Nutrient Score:</b> {nutrient_score:.1f}/100
                """
                
                folium.CircleMarker(
                    location=[result['lat'], result['lon']],
                    radius=12,
                    popup=folium.Popup(popup_content, parse_html=True),
                    color='white',
                    weight=2,
                    fillColor=nutrient_color,
                    fillOpacity=0.7,
                    tooltip=f"Nutrient Score: {nutrient_score:.1f}"
                ).add_to(nutrient_group)
        
        nutrient_group.add_to(m)
    
    # Layer 4: Soil Texture Analysis
    if active_layers.get('texture_analysis', False) and soil_results:
        texture_group = folium.FeatureGroup(name="Soil Texture")
        
        for result in soil_results:
            if all(x is not None for x in [result['clay_content'], result['sand_content'], result.get('silt_content')]):
                texture_type = classify_soil_texture(
                    result['clay_content'], 
                    result['sand_content'], 
                    result.get('silt_content', 0)
                )
                texture_color = get_texture_color(texture_type)
                
                popup_content = f"""
                <b>Soil Texture Point {result['point']}</b><br>
                <b>Texture Type:</b> {texture_type}<br>
                <b>Clay:</b> {result['clay_content']:.1f}%<br>
                <b>Sand:</b> {result['sand_content']:.1f}%<br>
                <b>Silt:</b> {result.get('silt_content', 0):.1f}%
                """
                
                folium.CircleMarker(
                    location=[result['lat'], result['lon']],
                    radius=12,
                    popup=folium.Popup(popup_content, parse_html=True),
                    color='white',
                    weight=2,
                    fillColor=texture_color,
                    fillOpacity=0.7,
                    tooltip=f"Texture: {texture_type}"
                ).add_to(texture_group)
        
        texture_group.add_to(m)
    
    # Layer 5: Management Zones
    if active_layers.get('management_zones', False) and soil_results:
        zones_group = folium.FeatureGroup(name="Management Zones")
        
        for result in soil_results:
            zone = classify_management_zone(result)
            zone_color = get_zone_color(zone)
            
            popup_content = f"""
            <b>Management Zone Point {result['point']}</b><br>
            <b>Zone:</b> {zone}<br>
            <b>Recommendation:</b> {get_zone_recommendation(zone)}
            """
            
            folium.CircleMarker(
                location=[result['lat'], result['lon']],
                radius=15,
                popup=folium.Popup(popup_content, parse_html=True),
                color='black',
                weight=3,
                fillColor=zone_color,
                fillOpacity=0.6,
                tooltip=f"Zone: {zone}"
            ).add_to(zones_group)
        
        zones_group.add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Fit map to farm boundary
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    
    return m

# Helper functions for layer analysis
def get_quality_color(quality):
    color_map = {
        "Excellent": "#2E8B57",
        "Good": "#9ACD32",
        "Fair": "#DAA520",
        "Poor": "#CD853F",
        "Very Poor": "#A0522D"
    }
    return color_map.get(quality, "#808080")

def get_ph_color(ph):
    if ph < 5.5:
        return "#FF4500"  # Red - Very acidic
    elif ph < 6.0:
        return "#FF8C00"  # Orange - Acidic
    elif ph <= 7.0:
        return "#32CD32"  # Green - Optimal
    elif ph <= 7.5:
        return "#FFD700"  # Yellow - Slightly alkaline
    else:
        return "#8A2BE2"  # Purple - Very alkaline

def get_ph_status(ph):
    if ph < 5.5:
        return "Very Acidic"
    elif ph < 6.0:
        return "Acidic"
    elif ph <= 7.0:
        return "Optimal"
    elif ph <= 7.5:
        return "Slightly Alkaline"
    else:
        return "Very Alkaline"

def calculate_nutrient_score(result):
    score = 0
    count = 0
    
    if result['organic_carbon'] is not None:
        oc = result['organic_carbon']
        if oc >= 20:
            score += 100
        elif oc >= 15:
            score += 80
        elif oc >= 10:
            score += 60
        elif oc >= 5:
            score += 40
        else:
            score += 20
        count += 1
    
    if result['nitrogen'] is not None:
        n = result['nitrogen']
        if n >= 2.0:
            score += 100
        elif n >= 1.5:
            score += 80
        elif n >= 1.0:
            score += 60
        elif n >= 0.5:
            score += 40
        else:
            score += 20
        count += 1
    
    return score / count if count > 0 else 0

def get_nutrient_color(score):
    if score >= 80:
        return "#006400"  # Dark Green
    elif score >= 60:
        return "#32CD32"  # Green
    elif score >= 40:
        return "#FFD700"  # Gold
    elif score >= 20:
        return "#FF8C00"  # Orange
    else:
        return "#FF4500"  # Red

def classify_soil_texture(clay, sand, silt):
    if clay >= 40:
        return "Clay"
    elif sand >= 85:
        return "Sand"
    elif silt >= 80:
        return "Silt"
    elif clay >= 25 and sand >= 45:
        return "Sandy Clay"
    elif clay >= 25 and silt >= 40:
        return "Silty Clay"
    elif clay >= 20:
        return "Clay Loam"
    elif sand >= 70:
        return "Sandy Loam"
    elif silt >= 50:
        return "Silt Loam"
    else:
        return "Loam"

def get_texture_color(texture):
    color_map = {
        "Clay": "#8B4513",
        "Sand": "#F4A460",
        "Silt": "#DDA0DD",
        "Sandy Clay": "#CD853F",
        "Silty Clay": "#9370DB",
        "Clay Loam": "#A0522D",
        "Sandy Loam": "#DAA520",
        "Silt Loam": "#D8BFD8",
        "Loam": "#228B22"
    }
    return color_map.get(texture, "#808080")

def classify_management_zone(result):
    ph = result.get('ph', 0)
    oc = result.get('organic_carbon', 0)
    quality_pct = result.get('percentage', 0)
    
    if quality_pct >= 75 and ph >= 6.0 and ph <= 7.0:
        return "Premium Zone"
    elif quality_pct >= 60:
        return "Good Production Zone"
    elif quality_pct >= 40:
        return "Moderate Zone"
    else:
        return "Improvement Zone"

def get_zone_color(zone):
    color_map = {
        "Premium Zone": "#006400",
        "Good Production Zone": "#32CD32",
        "Moderate Zone": "#FFD700",
        "Improvement Zone": "#FF4500"
    }
    return color_map.get(zone, "#808080")

def get_zone_recommendation(zone):
    recommendations = {
        "Premium Zone": "Maintain current practices",
        "Good Production Zone": "Minor adjustments needed",
        "Moderate Zone": "Focus on organic matter",
        "Improvement Zone": "Priority for soil amendments"
    }
    return recommendations.get(zone, "No specific recommendation")

def create_real_soil_quality_map(gdf):
    """Create map with real soil quality data from SoilGrids"""
    # Get the center of the shapefile
    bounds = gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    
    # Get farm geometry
    farm_geom = unary_union(gdf.geometry)
    
    # Generate sample points for soil analysis
    st.info("🔍 Generating soil analysis points within your farm boundary...")
    sample_points = generate_sample_points(farm_geom, num_points=12)
    
    if not sample_points:
        st.error("Could not generate sample points within farm boundary")
        return None, []
    
    # Get soil data for each point
    soil_data_results = []
    progress_bar = st.progress(0)
    
    for i, (lat, lon) in enumerate(sample_points):
        st.write(f"Analyzing soil at point {i+1}/{len(sample_points)}...")
        
        soil_data, error = get_soil_data_soilgrids(lat, lon)
        
        if soil_data and not error:
            quality, color, percentage, details = classify_soil_quality(soil_data)
            
            # Store results for analysis
            result = {
                'point': i+1,
                'lat': lat,
                'lon': lon,
                'quality': quality,
                'percentage': percentage,
                'ph': soil_data['ph'],
                'organic_carbon': soil_data['organic_carbon'],
                'clay_content': soil_data['clay_content'],
                'sand_content': soil_data['sand_content'],
                'silt_content': soil_data.get('silt_content'),
                'nitrogen': soil_data['nitrogen'],
                'cec': soil_data['cec'],
                'bulk_density': soil_data.get('bulk_density'),
                'details': details
            }
            soil_data_results.append(result)
        else:
            st.warning(f"Could not get soil data for point {i+1}: {error}")
        
        progress_bar.progress((i + 1) / len(sample_points))
        time.sleep(0.5)  # Rate limiting
    
    return soil_data_results

def create_analysis_charts(soil_results, active_layers):
    """Create analysis charts based on active layers"""
    if not soil_results:
        return
    
    df = pd.DataFrame(soil_results)
    
    # Chart container
    chart_cols = st.columns(2)
    
    # pH Distribution Chart
    if active_layers.get('ph_analysis', False) and 'ph' in df.columns:
        with chart_cols[0]:
            st.subheader("📊 pH Distribution")
            
            ph_data = df['ph'].dropna()
            if not ph_data.empty:
                fig = px.histogram(
                    x=ph_data,
                    nbins=10,
                    title="Soil pH Distribution",
                    labels={'x': 'pH Value', 'y': 'Frequency'},
                    color_discrete_sequence=['#32CD32']
                )
                fig.add_vline(x=6.0, line_dash="dash", line_color="red", annotation_text="Optimal Min")
                fig.add_vline(x=7.0, line_dash="dash", line_color="red", annotation_text="Optimal Max")
                st.plotly_chart(fig, use_container_width=True)
    
    # Nutrient Analysis Chart
    if active_layers.get('nutrient_analysis', False):
        with chart_cols[1]:
            st.subheader("🧪 Nutrient Levels")
            
            nutrients = []
            if 'organic_carbon' in df.columns:
                nutrients.append('organic_carbon')
            if 'nitrogen' in df.columns:
                nutrients.append('nitrogen')
            
            if nutrients:
                fig = go.Figure()
                
                for nutrient in nutrients:
                    nutrient_data = df[nutrient].dropna()
                    if not nutrient_data.empty:
                        fig.add_trace(go.Box(
                            y=nutrient_data,
                            name=nutrient.replace('_', ' ').title(),
                            boxpoints='all'
                        ))
                
                fig.update_layout(
                    title="Nutrient Distribution",
                    yaxis_title="Concentration (g/kg)"
                )
                st.plotly_chart(fig, use_container_width=True)
    
    # Soil Texture Triangle (if texture analysis is active)
    if active_layers.get('texture_analysis', False):
        st.subheader("🔺 Soil Texture Analysis")
        
        texture_data = df[['clay_content', 'sand_content', 'silt_content']].dropna()
        if not texture_data.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # Texture composition chart
                avg_composition = {
                    'Clay': texture_data['clay_content'].mean(),
                    'Sand': texture_data['sand_content'].mean(),
                    'Silt': texture_data['silt_content'].mean() if 'silt_content' in texture_data.columns else 0
                }
                
                fig = px.pie(
                    values=list(avg_composition.values()),
                    names=list(avg_composition.keys()),
                    title="Average Soil Composition"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Texture classification summary
                textures = []
                for _, row in texture_data.iterrows():
                    texture = classify_soil_texture(
                        row['clay_content'], 
                        row['sand_content'], 
                        row.get('silt_content', 0)
                    )
                    textures.append(texture)
                
                texture_counts = pd.Series(textures).value_counts()
                st.write("**Texture Classification Summary:**")
                for texture, count in texture_counts.items():
                    st.write(f"• {texture}: {count} points")

def analyze_soil_results(soil_data_results):
    """Analyze and summarize soil data results"""
    if not soil_data_results:
        return None
    
    df = pd.DataFrame(soil_data_results)
    
    # Calculate averages
    avg_ph = df['ph'].dropna().mean() if not df['ph'].dropna().empty else None
    avg_oc = df['organic_carbon'].dropna().mean() if not df['organic_carbon'].dropna().empty else None
    avg_clay = df['clay_content'].dropna().mean() if not df['clay_content'].dropna().empty else None
    avg_sand = df['sand_content'].dropna().mean() if not df['sand_content'].dropna().empty else None
    avg_nitrogen = df['nitrogen'].dropna().mean() if not df['nitrogen'].dropna().empty else None
    avg_cec = df['cec'].dropna().mean() if not df['cec'].dropna().empty else None
    
    # Quality distribution
    quality_counts = df['quality'].value_counts()
    
    # Overall farm quality assessment
    avg_percentage = df['percentage'].mean()
    
    return {
        'avg_ph': avg_ph,
        'avg_organic_carbon': avg_oc,
        'avg_clay': avg_clay,
        'avg_sand': avg_sand,
        'avg_nitrogen': avg_nitrogen,
        'avg_cec': avg_cec,
        'quality_distribution': quality_counts,
        'overall_percentage': avg_percentage,
        'sample_count': len(soil_data_results)
    }

# Main app
def main():
    st.title("🌾 Real Farm Soil Analysis")
