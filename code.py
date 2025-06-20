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
                'nitrogen': None,
                'cec': None  # Cation Exchange Capacity
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
            
            # Extract nitrogen (0-5cm)
            if 'nitrogen' in properties:
                n_data = properties['nitrogen']['depths'][0]['values']['mean']
                soil_info['nitrogen'] = n_data / 100  # Convert to g/kg
            
            # Extract CEC (0-5cm)
            if 'cec' in properties:
                cec_data = properties['cec']['depths'][0]['values']['mean']
                soil_info['cec'] = cec_data / 10  # Convert to cmol/kg
            
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

def create_real_soil_quality_map(gdf):
    """Create map with real soil quality data from SoilGrids"""
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
    
    # Add farm boundary
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
    
    # Get farm geometry
    farm_geom = unary_union(gdf.geometry)
    
    # Generate sample points for soil analysis
    st.info("🔍 Generating soil analysis points within your farm boundary...")
    sample_points = generate_sample_points(farm_geom, num_points=12)
    
    if not sample_points:
        st.error("Could not generate sample points within farm boundary")
        return m, []
    
    # Get soil data for each point
    soil_data_results = []
    progress_bar = st.progress(0)
    
    for i, (lat, lon) in enumerate(sample_points):
        st.write(f"Analyzing soil at point {i+1}/{len(sample_points)}...")
        
        soil_data, error = get_soil_data_soilgrids(lat, lon)
        
        if soil_data and not error:
            quality, color, percentage, details = classify_soil_quality(soil_data)
            
            # Create popup content
            popup_content = f"""
            <b>Soil Analysis Point {i+1}</b><br>
            <b>Quality:</b> {quality} ({percentage:.1f}%)<br>
            <b>pH:</b> {soil_data['ph']:.1f if soil_data['ph'] else 'N/A'}<br>
            <b>Organic Carbon:</b> {soil_data['organic_carbon']:.1f if soil_data['organic_carbon'] else 'N/A'} g/kg<br>
            <b>Clay Content:</b> {soil_data['clay_content']:.1f if soil_data['clay_content'] else 'N/A'}%<br>
            <b>Sand Content:</b> {soil_data['sand_content']:.1f if soil_data['sand_content'] else 'N/A'}%<br>
            <b>Nitrogen:</b> {soil_data['nitrogen']:.2f if soil_data['nitrogen'] else 'N/A'} g/kg<br>
            <b>CEC:</b> {soil_data['cec']:.1f if soil_data['cec'] else 'N/A'} cmol/kg
            """
            
            # Add marker to map
            folium.CircleMarker(
                location=[lat, lon],
                radius=15,
                popup=folium.Popup(popup_content, parse_html=True),
                color='black',
                weight=2,
                fillColor=color,
                fillOpacity=0.8,
                tooltip=f"Soil Quality: {quality}"
            ).add_to(m)
            
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
                'nitrogen': soil_data['nitrogen'],
                'cec': soil_data['cec'],
                'details': details
            }
            soil_data_results.append(result)
        else:
            st.warning(f"Could not get soil data for point {i+1}: {error}")
        
        progress_bar.progress((i + 1) / len(sample_points))
        time.sleep(0.5)  # Rate limiting
    
    # Create legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 220px; height: 160px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><b>Soil Quality Legend</b></p>
    <p><i class="fa fa-circle" style="color:#2E8B57"></i> Excellent (80-100%)</p>
    <p><i class="fa fa-circle" style="color:#9ACD32"></i> Good (65-79%)</p>
    <p><i class="fa fa-circle" style="color:#DAA520"></i> Fair (50-64%)</p>
    <p><i class="fa fa-circle" style="color:#CD853F"></i> Poor (35-49%)</p>
    <p><i class="fa fa-circle" style="color:#A0522D"></i> Very Poor (<35%)</p>
    <p><small>Data source: SoilGrids</small></p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Fit map to farm boundary
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    
    return m, soil_data_results

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
    st.markdown("Upload your farm shapefile to get real soil quality analysis using global soil data.")
    
    # File upload
    st.header("📁 Upload Farm Shapefile")
    uploaded_file = st.file_uploader(
        "Choose a ZIP file containing your shapefile",
        type=['zip'],
        help="Upload a ZIP file containing .shp, .shx, .dbf, and .prj files"
    )
    
    if uploaded_file is not None:
        # Extract and load shapefile
        with st.spinner("Processing shapefile..."):
            shp_path, error = extract_shapefile(uploaded_file)
            
            if error:
                st.error(f"❌ {error}")
                return
            
            try:
                # Load shapefile
                gdf = gpd.read_file(shp_path)
                # Convert datetime columns to strings for JSON compatibility
                gdf = gdf.copy()
                for col in gdf.select_dtypes(include=['datetime64[ns]']).columns:
                    gdf[col] = gdf[col].astype(str)
                
                # Display basic info
                st.success(f"✅ Shapefile loaded successfully!")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Number of Features", len(gdf))
                    st.metric("Total Area (hectares)", f"{gdf.geometry.area.sum() / 10000:.2f}")
                
                with col2:
                    if not gdf.empty:
                        bounds = gdf.total_bounds
                        st.write(f"**Coordinate System:** {gdf.crs}")
                        st.write(f"**Bounds:** {bounds[0]:.4f}, {bounds[1]:.4f} to {bounds[2]:.4f}, {bounds[3]:.4f}")
                
                # Create and display map with real soil analysis
                st.header("🗺️ Real-Time Soil Quality Analysis")
                st.markdown("*This analysis uses real soil data from SoilGrids. Click on the colored circles to see detailed soil information.*")
                
                # Warning about API usage
                st.warning("⚠️ This analysis makes API calls to SoilGrids for real soil data. Please be patient as it may take some time to complete.")
                
                if st.button("🚀 Start Soil Analysis", type="primary"):
                    # Create the map with real soil data
                    soil_map, soil_results = create_real_soil_quality_map(gdf)
                    
                    if soil_results:
                        # Display map
                        map_data = st_folium(
                            soil_map,
                            width=700,
                            height=500,
                            returned_objects=["last_object_clicked"]
                        )
                        
                        # Analyze results
                        analysis = analyze_soil_results(soil_results)
                        
                        if analysis:
                            # Display analysis summary
                            st.header("📈 Real Soil Analysis Summary")
                            
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                if analysis['avg_ph']:
                                    ph_status = "Good" if 6.0 <= analysis['avg_ph'] <= 7.0 else "Needs Attention"
                                    st.metric(
                                        "Average pH",
                                        f"{analysis['avg_ph']:.1f}",
                                        delta=ph_status,
                                        help="Optimal range: 6.0-7.0"
                                    )
                            
                            with col2:
                                if analysis['avg_organic_carbon']:
                                    oc_status = "Good" if analysis['avg_organic_carbon'] >= 15 else "Low"
                                    st.metric(
                                        "Organic Carbon",
                                        f"{analysis['avg_organic_carbon']:.1f} g/kg",
                                        delta=oc_status,
                                        help="Higher values indicate better soil health"
                                    )
                            
                            with col3:
                                overall_quality = "Excellent" if analysis['overall_percentage'] >= 80 else \
                                                "Good" if analysis['overall_percentage'] >= 65 else \
                                                "Fair" if analysis['overall_percentage'] >= 50 else \
                                                "Poor" if analysis['overall_percentage'] >= 35 else "Very Poor"
                                st.metric(
                                    "Overall Farm Quality",
                                    overall_quality,
                                    delta=f"{analysis['overall_percentage']:.1f}%",
                                    help="Based on multiple soil parameters"
                                )
                            
                            # Quality distribution
                            st.subheader("🎯 Soil Quality Distribution")
                            quality_df = pd.DataFrame({
                                'Quality': analysis['quality_distribution'].index,
                                'Count': analysis['quality_distribution'].values,
                                'Percentage': (analysis['quality_distribution'].values / analysis['sample_count'] * 100).round(1)
                            })
                            st.dataframe(quality_df, use_container_width=True)
                            
                            # Detailed soil parameters
                            st.subheader("🧪 Detailed Soil Parameters")
                            param_col1, param_col2 = st.columns(2)
                            
                            with param_col1:
                                if analysis['avg_clay']:
                                    st.metric("Average Clay Content", f"{analysis['avg_clay']:.1f}%")
                                if analysis['avg_nitrogen']:
                                    st.metric("Average Nitrogen", f"{analysis['avg_nitrogen']:.2f} g/kg")
                            
                            with param_col2:
                                if analysis['avg_sand']:
                                    st.metric("Average Sand Content", f"{analysis['avg_sand']:.1f}%")
                                if analysis['avg_cec']:
                                    st.metric("Average CEC", f"{analysis['avg_cec']:.1f} cmol/kg")
                            
                            # Generate recommendations based on real data
                            st.header("💡 Recommendations Based on Real Soil Data")
                            
                            recommendations = []
                            
                            if analysis['avg_ph'] and analysis['avg_ph'] < 6.0:
                                recommendations.append("🔹 **pH Management**: Your soil is acidic (pH < 6.0). Consider lime application to raise pH.")
                            elif analysis['avg_ph'] and analysis['avg_ph'] > 7.5:
                                recommendations.append("🔹 **pH Management**: Your soil is alkaline (pH > 7.5). Consider sulfur application or organic matter to lower pH.")
                            
                            if analysis['avg_organic_carbon'] and analysis['avg_organic_carbon'] < 10:
                                recommendations.append("🔹 **Organic Matter**: Low organic carbon levels. Increase organic matter through compost, cover crops, or manure.")
                            
                            if analysis['avg_clay'] and analysis['avg_clay'] > 50:
                                recommendations.append("🔹 **Soil Structure**: High clay content may cause drainage issues. Consider organic matter addition and avoid working wet soil.")
                            elif analysis['avg_sand'] and analysis['avg_sand'] > 70:
                                recommendations.append("🔹 **Water Retention**: High sand content may cause poor water retention. Add organic matter to improve water-holding capacity.")
                            
                            if analysis['avg_nitrogen'] and analysis['avg_nitrogen'] < 1.0:
                                recommendations.append("🔹 **Nitrogen Management**: Low nitrogen levels detected. Consider nitrogen fertilization or legume cover crops.")
                            
                            # Quality-based recommendations
                            poor_quality_percentage = (analysis['quality_distribution'].get('Poor', 0) + 
                                                     analysis['quality_distribution'].get('Very Poor', 0)) / analysis['sample_count'] * 100
                            
                            if poor_quality_percentage > 30:
                                recommendations.append("🔹 **Priority Areas**: Focus improvement efforts on areas with poor soil quality (marked in brown/orange on map).")
                            
                            if recommendations:
                                for rec in recommendations:
                                    st.markdown(rec)
                            else:
                                st.success("🎉 Your soil quality appears to be in good condition overall!")
                            
                            # Data source attribution
                            st.info("📊 **Data Source**: This analysis uses real soil data from SoilGrids250m v2.0, a global soil information system.")
                    
                    else:
                        st.error("❌ Could not retrieve soil data. Please try again or check your internet connection.")
                
            except Exception as e:
                st.error(f"❌ Error loading shapefile: {str(e)}")
                st.info("Make sure your ZIP file contains all required shapefile components (.shp, .shx, .dbf, .prj)")
    
    else:
        st.info("👆 Please upload a farm boundary shapefile to begin real soil analysis.")
        
        # Instructions
        st.header("📋 How It Works")
        st.markdown("""
        1. **Upload**: Upload your farm boundary shapefile (ZIP format)
        2. **Analysis**: The system generates sample points within your farm boundary
        3. **Real Data**: Each point is analyzed using real soil data from SoilGrids
        4. **Results**: View interactive map with actual soil quality measurements
        5. **Recommendations**: Get specific advice based on your soil conditions
        
        **Data Sources:**
        - **SoilGrids250m**: Global soil information system with 250m resolution
        - **Parameters**: pH, organic carbon, clay/sand content, nitrogen, CEC
        - **Accuracy**: Based on machine learning from global soil profile database
        
        **Note**: This tool provides real soil analysis but professional soil testing 
        is still recommended for detailed nutrient management and precise farming decisions.
        """)

if __name__ == "__main__":
    main()