from json import dump
import json
from math import pi, sqrt
import statistics
import requests
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pysolar.solar import get_altitude, get_altitude_fast
import datetime

from windrose import WindroseAxes

def prueba(start,end,latitude,longitude,parameters,solar=None,comunity='ag',time_std='utc'):
    # URL de la API
    url = 'https://power.larc.nasa.gov/api/temporal/hourly/point'

    # Cargar parametros
    params = {
        'start':start,
        'end':end,
        'latitude':latitude,
        'longitude':longitude,
        'community':comunity,
        'parameters':parameters,
        'format':'json',
        'user':'user',
        'header':True,
        'time-standard':time_std
    }

    # Realizar la solicitud GET
    response = requests.get(url, params=params)

    # Verificar si la solicitud fue exitosa (código de estado 200)
    if response.status_code == 200:
        # obtener datos
        data = response.json()

        with open('datos_api.json', 'w') as file:
            dump(data, file, indent=4)

        parameters = data["parameters"]
        data = pd.DataFrame.from_dict(data["properties"]["parameter"])

        # Reemplazar -999 por NaN
        data.replace(-999, np.nan, inplace=True)

        # Valido si se desea datos tomados para el día o la noche
        if solar:
            # Calculo la altura del sol para cada hora y la almaceno en una nueva columna
            for index, row in data.iterrows():
                year = int(str(index)[0:4])
                month = int(str(index)[4:6])
                day = int(str(index)[6:8])
                hour = int(str(index)[8:10])
                datetime_row = datetime.datetime(year,month,day,hour,0,0,0,tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))

                altitude = get_altitude(latitude,longitude,datetime_row)
                data.loc[index, 'ALT'] = altitude

            # filtro los datos
            if solar == 'day':
                data = data[data['ALT'] > 0]
            elif solar == 'night':
                data = data[data['ALT'] <= 0]

            # Borro la columna agregada
            del data['ALT']

        # Creo la tabla de resultados 
        result = {}
        wind_flag = False

        for col in data:
            if col in ['WS2M','WD2M']:
                if 'WS2M' in data.columns and 'WD2M' in data.columns and wind_flag != True:
                    # Calcular estadísticos de velocidad de viento para las 16 direcciones
                    cant_dir = 16
                    df_wind = {}
                    for dir in range(0,cant_dir):
                        if dir*360/cant_dir-11.25 < 0:
                            df_wind_data = data[(data['WD2M'] > 348.75) | (data['WD2M'] <= 11.25)]
                        else:
                            df_wind_data = data[(data['WD2M'] > dir*360/cant_dir-11.25) & (data['WD2M'] <= (dir+1)*360/cant_dir-11.25)]
                        df_wind[str(dir)] = {
                            'FREC':int(df_wind_data['WD2M'].dropna().count()),
                            'MIN':min(df_wind_data['WS2M'].dropna()),
                            'MAX':max(df_wind_data['WS2M'].dropna()),
                            'MEAN':statistics.mean(df_wind_data['WS2M'].dropna()),
                            'SD':statistics.stdev(df_wind_data['WS2M'].dropna())
                        }
                    result['W2M'] = df_wind
                    wind_flag = True

                elif 'WS2M' in data.columns and 'WD2M' not in data.columns:
                    # Calcular estadísticos para la velocidad de viento
                    result[col] = [
                        int(data[col].dropna().count()),
                        min(data[col].dropna()),
                        max(data[col].dropna()),
                        statistics.mean(data[col].dropna()),
                        statistics.stdev(data[col].dropna())
                    ]

                elif 'WS2M' not in data.columns and 'WD2M' in data.columns:
                    # Calcular frecuencia de direccion de viento
                    cant_dir = 16
                    df_wind = {}
                    for dir in range(0,cant_dir):
                        df_wind_data = data[(data['WD2M'] > dir*360/cant_dir) & (data['WD2M'] <= (dir+1)*360/cant_dir)]
                        df_wind[str(dir)] = {'FREC':int(df_wind_data['WD2M'].count())}
                    result['WD2M'] = df_wind

            else:
                result[col] = {
                    'FREC': int(data[col].dropna().count()),
                    'MIN': min(data[col].dropna()),
                    'MAX':max(data[col].dropna()),
                    'MEAN':statistics.mean(data[col].dropna()),
                    'SD':statistics.stdev(data[col].dropna())
                }

        result["parameters"] = parameters

        # print(result)
        # print(dumps(result, indent=4))

        with open('datos.json', 'w') as file:
            dump(result, file, indent=4)

        for col in data:
            if col in ['WS2M','WD2M']:
                #Definición de estilo
                #plt.style.use('ggplot')

                # Rosa de los vientos
                data['velocidad_x'] = data['WS2M'] * np.sin(data['WD2M'] * pi / 180.0)
                data['velocidad_y'] = data['WS2M'] * np.cos(data['WD2M'] * pi / 180.0)
                fig, ax = plt.subplots()
                ax.set_aspect('equal')
                data.plot(kind='scatter', x='velocidad_x', y='velocidad_y', alpha=0.35, ax=ax)
                ax = WindroseAxes.from_ax()
                ax.bar(data['WD2M'], data['WS2M'], normed=True, opening=0.8, edgecolor='white')
                ax.set_legend(title=parameters['WS2M']['units'])
                ax.set_title('WIND')
                plt.savefig('images\\W2M_windrose.png')
                
            else:
                #Definición de estilo
                #plt.style.use('_mpl-gallery')

                # histograma:
                fig, ax = plt.subplots(figsize=(5,5), layout='constrained')
                ax.hist(data[col], bins=9)
                x_label = parameters[col]['longname'] + ' [' \
                        + parameters[col]['units'] + ']'
                ax.set_xlabel(x_label)
                ax.set_ylabel('Frecuency')
                ax.set_title(col)
                plt.savefig('images\\'+col+'_hist.png')

                # Diagrama de caja
                fig, ax = plt.subplots(figsize=(5,5), layout='constrained')
                ax.boxplot(data[col])
                ax.set_title(col)
                y_label = parameters[col]['longname'] + ' [' \
                        + parameters[col]['units'] + ']'
                ax.set_ylabel(y_label)
                plt.savefig('images\\'+col+'_boxplot.png')
                

    else:
        print(f'Error al realizar la solicitud: {response.status_code}')

# prueba(start=20240601,end=20240630,latitude=-32.9,longitude=-60.77,parameters='T2M,RH2M,PS,WS2M,WD2M',solar='night')
prueba(start=20231221,end=20240320,latitude=-32.54,longitude=-60.46,parameters='T2M,RH2M,PS,WS2M,WD2M',solar=True)
# prueba(start=20240729,end=20240802,latitude=-32.9,longitude=-60.77,parameters='WS2M,WD2M')
