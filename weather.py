import time
start_time_overall = time.time()

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import colormaps
import gpxpy
from concurrent.futures import ThreadPoolExecutor
import openmeteo_requests
import requests_cache
from retry_requests import retry
import requests

API_KEY = '5b3ce3597851110001cf6248cca3afa1547a460ab12d2624d73dbe4e'

gpx_file_path = "Opua.gpx"

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

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
def get_weather_API(lat, long):
    # Setup the Open-Meteo API client with cache and retry on error
    cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    openmeteo = openmeteo_requests.Client(session = retry_session)

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": long,
        "models": "best_match",
        "hourly": "temperature_2m",
        "minutely_15": ["temperature_2m", "wind_direction_10m", "wind_speed_10m", "precipitation"],
        "forecast_days": 1,
        "forecast_minutely_15": 96,
    }
    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    minutely_15 = response.Minutely15()
    temp_15minutes = minutely_15.Variables(0).ValuesAsNumpy()
    wind_dir_15 = minutely_15.Variables(1).ValuesAsNumpy()
    wind_intensity_15 = minutely_15.Variables(2).ValuesAsNumpy()
    rain_15minutes = minutely_15.Variables(3).ValuesAsNumpy()
    return temp_15minutes, rain_15minutes, wind_dir_15, wind_intensity_15

# Process first location. Add a for-loop for multiple locations or weather models
def get_all_weather(gdf):
    coord_pairs = []
    tot_temperature = []
    tot_rain = []
    tot_wind_dir = []
    tot_wind_intensity = []

    for index, row in gdf.iterrows():
        current_point = row.geometry
        coord_pairs.append((current_point.x, current_point.y))

    def get_weather(params):
        return get_weather_API(*params)

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(get_weather, point) for point in coord_pairs]
        for future in futures:
            temperature, rain, wind_dir, wind_intensity = future.result()
            tot_temperature.append(temperature)
            tot_rain.append(rain)
            tot_wind_dir.append(wind_dir)
            tot_wind_intensity.append(wind_intensity)

    gdf = gdf.assign(tot_temperature=tot_temperature,
                     tot_rain=tot_rain,
                     tot_wind_dir=tot_wind_dir,
                     tot_wind_intensity=tot_wind_intensity)
        
    return gdf

def get_travel_time(gdf, API_KEY):
    coords = []
    for index, row in gdf.iterrows():
        current_point = row.geometry
        coords.append([current_point.y, current_point.x])
    # OpenRouteService API endpoint for directions
    ors_route_url = "https://api.openrouteservice.org/v2/directions/driving-car"
    
    # Headers to include your API key
    headers = {
        'Authorization': API_KEY,
        'Content-Type': 'application/json'
    }
    
    # Body for the POST request, including the start and end coordinates
    body = {
        "coordinates": coords
    }
        
    # Sending a POST request to OpenRouteService API
    response = requests.post(ors_route_url, json=body, headers=headers)
    
    data = response.json()

    travel_time = [0]
    for i in range(0, len(gdf)-1):
        time_waypoint = data['routes'][0]['segments'][i]['duration']
        travel_time.append(time_waypoint)

    gdf['travel_times'] = travel_time

    return gdf

def get_timestamped_weather(gdf):
    current_temp = []
    current_rain = []
    current_wind_dir = []
    current_wind_intensity = []
    for index, row in gdf.iterrows():
        temp = row.tot_temperature
        rain = row.tot_rain
        wind_dir = row.tot_wind_dir
        wind_intensity = row.tot_wind_intensity
        timestamp = round((row.delta_time)/15)
        current_temp.append(temp[timestamp])
        current_rain.append(rain[timestamp])
        current_wind_dir.append(wind_dir[timestamp])
        current_wind_intensity.append(wind_intensity[timestamp])
    
    gdf = gdf.assign(timestamped_temperature=current_temp,
                     timestamped_rain=current_rain,
                     timestamped_wind_dir=current_wind_dir,
                     timestamped_wind_intensity=current_wind_intensity)
    
    return gdf

gdf = create_gdf(gpx_file_path)

def plot_function(gdf):
    time = gdf.delta_time
    temperature = gdf.timestamped_temperature
    rain = gdf.timestamped_rain
    wind_dir = gdf.timestamped_wind_dir
    wind_intensity = gdf.timestamped_wind_intensity

    if max(rain) > 2.5:
        maxrain = 10
    else:
        maxrain = 2.5

    U = np.cos(wind_dir) * wind_intensity
    V = np.sin(wind_dir) * wind_intensity
    Y = [min(temperature) - abs(min(temperature)-max(temperature))] * len(U)
    C = np.sqrt(U**2 + V**2)

    fig, ax1 = plt.subplots(figsize=(8, 8))
    ax2 = ax1.twinx()    
    ax2.set_ylim(0,maxrain)
    Q = ax1.quiver(time, Y, U, V, C, 
                   pivot='middle', 
                   cmap="rainbow", 
                   scale = 10, 
                   scale_units='xy'
                   )
    Q.set_clim(vmin=0, vmax=50)

    fig.colorbar(Q, ax=ax1, label='Vitesse du vent [km/h]')
    ax2.bar(time, rain, alpha=0.4, width=7.5)
    ax2.set_ylabel("Précipitation [mm]")
    ax1.plot(time, temperature)
    ax1.set_ylabel("Température [°C]")
    ax1.set_xlabel("Temps après le départ")

    plt.show()

    return None

# final_size = 40
# while True:
    # gdf_trimmed = trim_gdf(gdf, final_size)
    # gdf_trimmed = get_travel_time(gdf_trimmed, API_KEY)
    # if gdf_trimmed['travel_times'].max() > 900:
    #     final_size +=5
    # else:
    #     break

gdf_trimmed_dist = trim_gdf_by_distance(gdf)
gdf_trimmed_time = trim_gdf_by_time(gdf)

gdf_trimmed_time_weather = get_all_weather(gdf_trimmed_time)
gdf_trimmed_dist_weather = get_all_weather(gdf_trimmed_dist)

final_distancestamped = get_timestamped_weather(gdf_trimmed_dist_weather)
final_timestamped = get_timestamped_weather(gdf_trimmed_time_weather)

plot_function(final_timestamped)
plot_function(final_distancestamped)

end_time_overall = time.time()
elapsed_time_overall =  end_time_overall - start_time_overall
print(f"Temps overall {round(elapsed_time_overall, 2)}s")