from mesa import Agent
from mesa import Model
from mesa.time import RandomActivation
import math
import matplotlib.pyplot as plt
import pandas as pd

import snman
import os
import random

import networkx as nx
from dataclasses import dataclass

from snman import MODE_PRIVATE_CARS, KEY_LANES_DESCRIPTION, MODE_CYCLING, KEY_LANES_DESCRIPTION_AFTER, lane_graph

## mesa version 2.1.5

#todo:
# add edge states for traffic flow representation
# making an assumption that there is no comparison. cld make a distr for cars and compare

PROJECT = '_main'
data_directory = os.path.join('C:',os.sep,'Users','shiry', 'snman_sgProject')
export_path = os.path.join(data_directory, 'outputs', PROJECT)
inputs_path = os.path.join(data_directory, 'inputs', PROJECT)

@dataclass
class Journey:
    agent_id: int = None
    origin: int = None
    destination: int = None
    mode: str = None

    path: list = None
    current_edge_index: int = 0
    current_edge_time_remaining: float = None
    current_edge: tuple = None

    total_travel_time: float = None
    remaining_time: float = None
    cost_vod: float = None
    distance_m: float = None

    started: bool = False
    finished: bool = False
    started_time: float = None
    end_time: float = None



class Traveler(Agent):

    def __init__(self, unique_id, origin, destination, model):
        super().__init__(unique_id, model)
        self.current_journey = None
        self.origin = origin
        self.destination = destination
        self.has_traveled = False

    def choose_mode(self, origin, destination):
        graphs = {
            "bike": self.model.bike_graph,
            "car": self.model.car_graph,
        }

        results = {}

        for mode, graph in graphs.items():
            if origin not in graph or destination not in graph:
                continue
            if not nx.has_path(graph, origin, destination):
                continue

            path = nx.shortest_path(graph, origin, destination, weight='weight')
            cost = nx.path_weight(graph, path, weight='weight')
            results[mode] = {"path": path, "cost": cost}

        # if no routes
        if not results:
            return None

        # check if bike route is possible, if not choose car and vice versa
        if "bike" not in results and "car" in results:
            return {
                "mode": "car",
                "path": results["car"]["path"],
                "cost": results["car"]["cost"],
            }

        if "car" not in results and "bike" in results:
            return {
                "mode": "bike",
                "path": results["bike"]["path"],
                "cost": results["bike"]["cost"],
            }

        # exponential mode choice model.
        bike_time = self.get_travel_time("bike", results["bike"]["path"]) * 60

        if bike_time > 10:
            chosen_mode = "car"
        else:
            lamda = 0.069
            p_bike = math.exp(-lamda * bike_time)

            if random.random() < p_bike:
                chosen_mode = "bike"
            else:
                chosen_mode = "car"

        return {
            "mode": chosen_mode,
            "path": results[chosen_mode]["path"],
            "cost": results[chosen_mode]["cost"],
        }

    def get_path_dist(self, mode, path):
        if mode == "bike":
            graph = self.model.bike_graph
        elif mode == "car":
            graph = self.model.car_graph

        total_dist_m = 0
        for u, v, in zip(path[:-1], path[1:]):
            total_dist_m += graph[u][v]['length']

        return total_dist_m

    def get_travel_time(self, mode, path):
        if mode == "car":
            distance_m = self.get_path_dist(mode, path)
            distance_km = distance_m/1000
            speed_kmh = 30
            return distance_km/speed_kmh

        elif mode == "bike":
            graph = self.model.bike_graph
            total_time_h = 0

            for u, v, in zip(path[:-1], path[1:]):
                edge = graph[u][v]
                length_km = edge['length']/1000
                primary_mode = edge.get('primary_mode')

                if primary_mode == "cycling":
                    speed_kmh = 14
                else:
                    speed_kmh = 10
                total_time_h += length_km/speed_kmh

            return total_time_h


    def start_journey(self):
        """
        based on mode chosen, create journey state?
        1. pick origin and dest (for now ill just pick random nodes)
        2. choose mode
        3. remaining travel time, mark agent as on journey
        """

        # choose the origin and destination, origin and destination should be different nodes
        origin = self.origin
        destination = self.destination

        decision = self.choose_mode(origin, destination)
        if decision is None:
            return

        travel_time = self.get_travel_time(decision['mode'], decision['path'])
        distance = self.get_path_dist(decision["mode"], decision["path"])

        self.current_journey = Journey(
            agent_id=self.unique_id,
            origin=origin,
            destination=destination,
            mode=decision['mode'],

            path=decision['path'],
            current_edge_index=0,
            distance_m=distance,

            total_travel_time=travel_time,
            remaining_time=travel_time,
            cost_vod=decision['cost'],

            started=True,
            started_time=self.model.schedule.time
        )

    def progress_journey(self):
        journey = self.current_journey
        journey.remaining_time -= self.model.step_time

        if journey.remaining_time <= 0:
            journey.finished = True
            journey.end_time = self.model.schedule.time

    def end_journey(self):
        self.model.completed_journeys.append(self.current_journey)
        self.current_journey = None

    def calculate_emissions(self):
        """
        based on mode chosen and time? calculate emissions
        Returns
        -------
        emissions
        """

    def step(self):
        if self.has_traveled:
            return

        if self.current_journey is None:
            self.start_journey()
            return

        if not self.current_journey.finished:
            self.progress_journey()

        if self.current_journey.finished:
            self.end_journey()
            self.has_traveled = True



class Network(Model):
    def __init__(self, scenario="before", n=150, step_time = 1/12, start_time = 5, end_time = 11, od_pairs = None, rng= None):
        super().__init__(rng = rng)

        self.scenario = scenario
        self.step_time = step_time
        self.start_time = start_time
        self.end_time = end_time

        self.current_time = start_time
        self.completed_journeys = []
        self.od_pairs = od_pairs

        # load the graphs
        self.graph = snman.io.load_street_graph(
            edges_path=os.path.join(export_path, 'G_edges.gpkg'),
            nodes_path=os.path.join(export_path, 'G_nodes.gpkg'),
            crs=3414
        )

        if scenario == "before":
            self.car_graph = self.build_mode_graph(
                MODE_PRIVATE_CARS,
                KEY_LANES_DESCRIPTION
            )
            self.bike_graph = self.build_mode_graph(
                MODE_CYCLING,
                KEY_LANES_DESCRIPTION
            )

        if scenario == "after":
            self.car_graph = self.build_mode_graph(
                MODE_PRIVATE_CARS,
                KEY_LANES_DESCRIPTION_AFTER
            )
            self.bike_graph = self.build_mode_graph(
                MODE_CYCLING,
                KEY_LANES_DESCRIPTION_AFTER
            )

        # create edge state for traffic flow (to do)
        for u, v, k, data in self.graph.edges(keys = True, data=True):
            edge_type = data.get("highway")
            data["occupants"] = 0
        '''
            if edgetype == motorway:
                data['capacity'] = something
            elif edgetype == bicycle:
                data['capacity'] = somethingelse
            data['no_traffic_time'] = errm
            data['current_travel_time'] = hmmm
        '''

        # we need a dictionary of locations from G?

        # create the agents
        self.schedule = RandomActivation(self)

        for i in range(n):
            origin, destination = self.od_pairs[i]
            agent = Traveler(i, origin, destination, self)
            self.schedule.add(agent)

    def build_mode_graph(self, mode, lanes_key):
        # uses snman functions to create lane graph from street graph to get info on cost and length (weight and travel time)
        G_filtered = snman.street_graph.filter_lanes_by_modes(
            self.graph.copy(),
            {mode},
            lane_description_key=lanes_key
        )

        L = snman.lane_graph.create_lane_graph(
            G_filtered,
            lanes_attribute=lanes_key
        )

        L = snman.graph.keep_only_the_largest_connected_component(L)

        H= nx.DiGraph()
        H.add_nodes_from(L.nodes(data=True))

        weight_key = f"cost_{mode}"

        for u, v, k, data in L.edges(keys=True, data=True):
            w = data.get(weight_key, math.inf)
            length = data.get("length", 0)
            lanetype = data.get("lanetype")
            primary_mode = data.get("primary_mode")

            if w is None or math.isinf(w):
                continue
            if H.has_edge(u, v):
                if w < H[u][v]["weight"]:
                    H[u][v]["weight"] = w
                    H[u][v]["length"] = length
                    H[u][v]["primary_mode"] = primary_mode
                    H[u][v]["lanetype"] = lanetype
            else:
                H.add_edge(
                    u, v,
                    weight=w,
                    length=length,
                    lanetype = lanetype,
                    primary_mode = primary_mode,
                )

        return H

    def get_journeys(self):
        rows = []
        for journey in self.completed_journeys:
            rows.append({
                "agent_id": journey.agent_id,
                "origin": journey.origin,
                "destination": journey.destination,
                "mode": journey.mode,
                "travel_time": journey.total_travel_time,
                "cost_vod": journey.cost_vod,
                "started_time": journey.started_time,
                "end_time": journey.end_time,
                "distance_m": journey.distance_m,
                "travel_time_h": journey.total_travel_time
            })

        return pd.DataFrame(rows)

    def step(self):
        self.schedule.step() # each step shld be 5 mins
        self.current_time += self.step_time
        active = sum(agent.current_journey is not None for agent in self.schedule.agents)
        # print(f"Active journeys: {active}")