
import gpxpy
import geopandas as gpd
import pandas as pd
import numpy as np

def create_gdf(gpx_file_path):
    gpx = gpxpy.parse(open(gpx_file_path))

    x = []
    y = []
    timestamp = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                x.append(point.latitude)
                y.append(point.longitude)
                timestamp.append(point.time)
    
    delta_time = []
    for i in range(0, len(timestamp)):
        delta_time.append(round((timestamp[i].timestamp() - timestamp[0].timestamp())/60))
    delta_time[-1] = (round(delta_time[-1]/15)+1)*15

    data = {'lat': x, 'long': y, 'timestamp_minutes': timestamp, 'delta_time': delta_time}
    df = pd.DataFrame(data)
    gdf_init = gpd.GeoDataFrame(df, geometry = gpd.points_from_xy(df.lat, df.long), crs="EPSG:4326")

    gdf_init['distance_one_to_one'] = gdf_init.geometry.distance(gdf_init.geometry.shift(-1))*111
    distance_to_first = []
    dist = 0
    for i in range(0,len(gdf_init)):
        dist += gdf_init['distance_one_to_one'].iloc[i]
        distance_to_first.append(dist)
    
    distance_to_first[-1] = (round(distance_to_first[-2]/10)+1)*10
    
    gdf_init['distance_to_first'] = [round(elem) for elem in distance_to_first]

    return gdf_init

def trim_gdf(gdf, final_size):
    remainingIndex = np.round(np.linspace(0, len(gdf)-1, final_size), 0)
    gdf_trimmed = gdf.iloc[remainingIndex]
    return gdf_trimmed

def trim_gdf_by_time(gdf):
    indices = gdf.index[gdf['delta_time']%15 != 0] 
    gdf_trimmed = gdf.drop(indices)
    gdf_trimmed = gdf_trimmed.drop_duplicates(subset=['delta_time'], keep='first')
    return gdf_trimmed.reset_index()

def trim_gdf_by_distance(gdf):
    indices = gdf.index[gdf['distance_to_first']%10 != 0] 
    gdf_trimmed = gdf.drop(indices)
    gdf_trimmed = gdf_trimmed.drop_duplicates(subset=['distance_to_first'], keep='first')
    return gdf_trimmed.reset_index()
