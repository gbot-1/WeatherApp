import time
start_time_overall = time.time()


import requests

from gdf_manipulation import* 
from get_weather_func import*
from display import*

API_KEY = '5b3ce3597851110001cf6248cca3afa1547a460ab12d2624d73dbe4e'

gpx_file_path = "Opua.gpx"


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

    # Extract the geometry
    geometry = data['features'][0]['geometry']['coordinates']

    geometry = [(lat, lon) for lon, lat in geometry]

    gdf['travel_times'] = travel_time

    return gdf, geometry

# final_size = 40
# while True:
    # gdf_trimmed = trim_gdf(gdf, final_size)
    # gdf_trimmed = get_travel_time(gdf_trimmed, API_KEY)
    # if gdf_trimmed['travel_times'].max() > 900:
    #     final_size +=5
    # else:
    #     break

gdf = create_gdf(gpx_file_path)

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