import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
import os

'''
There is no geospatial data officially provided for Singapore bus routes.
Instead, GTFS data is only available from transitland (https://www.transit.land/feeds/f-w21z-lta).
Here, we want to convert the GTFS to a geofile. The GTFS contains these txt files which we will use:

shapes.txt: (geometry points)
            shape_id (what shape the point belongs to)
            shape_pt_lat, shape_pt_lon (point coordinate)
            shape_pt_sequence (order along the route)
routes.txt: data about bus routes such as description and agency
trips.txt: we will use the to link the shapes to the routes
            route_id
            shape_id

'''

# load data
data_directory = os.path.join('C:', os.sep, 'Users', 'shiry', 'snman_sgProject')
GTFS_dir = os.path.join(data_directory, 'custom_inputs', 'gtfs-feed-lta')
export_path = os.path.join(data_directory, 'inputs', 'singapore', 'sg_bus_routes.gpkg')
CRS_input = 'EPSG:4326'
CRS_output = 'EPSG:3414'

def read_gtfs(GTFS_table_name):
    path = os.path.join(GTFS_dir, GTFS_table_name)
    return pd.read_csv(path, sep=',')

def build_lines(shapes_table):
    shapes_table = shapes_table.copy()
    shapes_table['shape_pt_sequence'] = pd.to_numeric(shapes_table['shape_pt_sequence'])
    shapes_table['shape_pt_lat'] = pd.to_numeric(shapes_table['shape_pt_lat'])
    shapes_table['shape_pt_lon'] = pd.to_numeric(shapes_table['shape_pt_lon'])

    shapes_table = shapes_table.dropna(subset=['shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence'])
    shapes_table = shapes_table.sort_values(['shape_id', 'shape_pt_sequence'])

    # use shapely to convert coordinates to LineString geometry object
    def to_linestring(df):
        lons = df['shape_pt_lon'].tolist()
        lats = df['shape_pt_lat'].tolist()
        coords = list(zip(lons, lats))

        if len(coords) < 2:
            return None

        return LineString(coords)

    # so first, grp by the shape id. Then we use the to_linestring function which gives a Series of LineString geometries.
    # then i want to convert into data frame
    lines = (
        shapes_table.groupby('shape_id', sort=False)
        .apply(to_linestring)
        .reset_index(name='geometry') # call the LineString column geometry
        .dropna(subset=['geometry'])
    )

    # turn the pandas data frame to a geodataframe
    gdf = gpd.GeoDataFrame(lines, geometry='geometry', crs=CRS_input)

    return gdf


def main():
    shapes_table = read_gtfs("shapes.txt")
    trips_table = read_gtfs("trips.txt")
    routes_table = read_gtfs("routes.txt")

    shape_lines = build_lines(shapes_table)

    # merge the tables to get the info we need
    shape_route = trips_table[['shape_id', 'route_id', 'direction_id']].dropna().drop_duplicates()
    gdf = shape_lines.merge(shape_route, on='shape_id', how='inner')

    route_cols = ['route_id', 'route_short_name', 'route_long_name', 'route_type']
    gdf = gdf.merge(routes_table[route_cols].drop_duplicates(), on='route_id', how='left')

    gdf = gdf.to_crs(CRS_output)

    # changing names to match ZVV style columns for snman
    gdf['route'] = gdf['route_short_name']
    gdf['direction'] = gdf['direction_id']

    # make into one feature per route direction for ZVV style data
    gdf = gdf.dissolve(by=['route_id', 'direction'], aggfunc={'route': 'first', 'route_type': 'first'}, as_index=False)

    gdf = gdf[['route', 'route_id', 'direction', 'geometry', 'route_type']]

    # export
    gdf.to_file(export_path, driver='GPKG')
    print("saved pt data!")


if __name__ == '__main__':
    main()

