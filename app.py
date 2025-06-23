import streamlit as st
import geopandas as gpd
import folium
from folium import plugins
import tempfile
import zipfile
import os
from streamlit_folium import st_folium

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

def create_soil_quality_map(gdf):
    """Create map with synthetic soil quality data"""
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
    
    # Create synthetic soil quality zones within the farm area
    # This simulates different soil quality areas
    import numpy as np
    from shapely.geometry import Point
    from shapely.ops import unary_union
    
    # Get farm geometry
    farm_geom = unary_union(gdf.geometry)
    
    # Create soil quality zones (simplified simulation)
    soil_zones = []
    colors = ['#8B4513', '#A0522D', '#CD853F', '#D2B48C', '#F4A460']  # Brown to tan
    quality_names = ['Very Poor', 'Poor', 'Fair', 'Good', 'Excellent']
    
    # Generate sample points within farm boundary
    minx, miny, maxx, maxy = farm_geom.bounds
    points_added = 0
    
    for i, (color, quality) in enumerate(zip(colors, quality_names)):
        # Create some random points within the farm
        sample_points = []
        attempts = 0
        while len(sample_points) < 3 and attempts < 50:  # Try to get 3 points per quality zone
            x = np.random.uniform(minx, maxx)
            y = np.random.uniform(miny, maxy)
            point = Point(x, y)
            
            if farm_geom.contains(point):
                sample_points.append([y, x])  # folium uses [lat, lon]
                points_added += 1
            attempts += 1
        
        # Add markers for soil quality zones
        for idx, point_coords in enumerate(sample_points):
            folium.CircleMarker(
                location=point_coords,
                radius=20,
                popup=folium.Popup(
                    f"""
                    <b>Soil Quality Zone</b><br>
                    Quality: {quality}<br>
                    pH: {6.0 + i * 0.3:.1f}<br>
                    Organic Matter: {2 + i * 0.5:.1f}%<br>
                    Fertility: {i + 1}/5
                    """,
                    parse_html=True
                ),
                color='black',
                weight=2,
                fillColor=color,
                fillOpacity=0.7,
                tooltip=f"Soil Quality: {quality}"
            ).add_to(m)
    
    # Add a legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 140px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><b>Soil Quality Legend</b></p>
    <p><i class="fa fa-circle" style="color:#8B4513"></i> Very Poor (pH 6.0)</p>
    <p><i class="fa fa-circle" style="color:#A0522D"></i> Poor (pH 6.3)</p>
    <p><i class="fa fa-circle" style="color:#CD853F"></i> Fair (pH 6.6)</p>
    <p><i class="fa fa-circle" style="color:#D2B48C"></i> Good (pH 6.9)</p>
    <p><i class="fa fa-circle" style="color:#F4A460"></i> Excellent (pH 7.2)</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Fit map to farm boundary
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    
    return m

# Main app
def main():
    st.title("🌾 Farm Soil Quality Analysis")
    st.markdown("Upload your farm shapefile to analyze soil quality zones across your property.")
    
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
                # 🔄 Fix: Convert datetime columns to strings for JSON compatibility
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
                
                # Create and display map
                st.header("🗺️ Interactive Soil Quality Map")
                st.markdown("*Click on the colored circles to see detailed soil information for each zone.*")
                
                # Create the map
                soil_map = create_soil_quality_map(gdf)
                
                # Display map
                map_data = st_folium(
                    soil_map,
                    width=700,
                    height=500,
                    returned_objects=["last_object_clicked"]
                )
                
                # Display clicked information
                if map_data['last_object_clicked']:
                    st.subheader("📊 Selected Zone Details")
                    clicked_data = map_data['last_object_clicked']
                    st.json(clicked_data)
                
                # Soil analysis summary
                st.header("📈 Soil Analysis Summary")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        "Average pH",
                        "6.6",
                        delta="0.2",
                        help="Optimal range: 6.0-7.0"
                    )
                
                with col2:
                    st.metric(
                        "Organic Matter",
                        "3.2%",
                        delta="0.5%",
                        help="Good range: 3-5%"
                    )
                
                with col3:
                    st.metric(
                        "Overall Fertility",
                        "Good",
                        help="Based on soil quality zones"
                    )
                
                # Recommendations
                st.header("💡 Recommendations")
                st.markdown("""
                **Based on your soil analysis:**
                
                - 🌱 **Areas with poor soil quality** (brown zones) would benefit from organic matter addition
                - 🧪 **pH levels** are generally good, but monitor acidic areas
                - 💧 **Water retention** can be improved in sandy areas with compost
                - 🌾 **Crop rotation** recommended for maintaining soil health
                - 🔬 **Professional soil testing** recommended for precise nutrient management
                """)
                
            except Exception as e:
                st.error(f"❌ Error loading shapefile: {str(e)}")
                st.info("Make sure your ZIP file contains all required shapefile components (.shp, .shx, .dbf, .prj)")
    
    else:
        st.info("👆 Please upload a shapefile to begin the soil analysis.")
        
        # Instructions
        st.header("📋 Instructions")
        st.markdown("""
        1. **Prepare your shapefile**: Make sure you have all required files (.shp, .shx, .dbf, .prj)
        2. **Create a ZIP file**: Compress all shapefile components into a single ZIP file
        3. **Upload**: Use the file uploader above to upload your ZIP file
        4. **Analyze**: View the interactive map with soil quality zones
        5. **Review**: Check the recommendations for your farm
        
        **Note**: This demo uses simulated soil data for demonstration purposes. 
        For real soil analysis, consider professional soil testing services.
        """)

if __name__ == "__main__":
    main()
