
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import colormaps

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
