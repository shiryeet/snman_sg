from mesa import Agent
from mesa import Model
from mesa.time import RandomActivation
import math
import pandas as pd

import snman
import os
import random

import networkx as nx
from dataclasses import dataclass

from snman import MODE_PRIVATE_CARS, KEY_LANES_DESCRIPTION, MODE_CYCLING, KEY_LANES_DESCRIPTION_AFTER, lane_graph

## mesa version 2.1.5

#todo:
# consider carbon emissions
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

    total_travel_time: float = 0
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

            path = nx.shortest_path(graph, origin, destination, weight='length')
            distance = self.get_path_dist(mode, path)
            results[mode] = {"path": path, "distance": distance}

        # if no routes
        if not results:
            return None

        # check if bike route is possible, if not choose car and vice versa
        if "bike" not in results and "car" in results:
            return {
                "mode": "car",
                "path": results["car"]["path"],
                "distance": results["car"]["distance"],
            }

        if "car" not in results and "bike" in results:
            return {
                "mode": "bike",
                "path": results["bike"]["path"],
                "distance": results["bike"]["distance"],
            }

        # exponential mode choice model.
        # also, im using get_travel_time here, which means that in the future if
        # I add bike lane congestion, decision accounts for congestion time
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
            "distance": results[chosen_mode]["distance"],
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
            graph = self.model.car_graph
        else:
            graph = self.model.bike_graph

        total_time_h = 0
        for u, v, in zip(path[:-1], path[1:]):
            total_time_h += graph[u][v]['current_travel_time']

        return total_time_h

    def enter_edge(self):
        journey = self.current_journey
        u = journey.path[journey.current_edge_index]
        v = journey.path[journey.current_edge_index + 1]

        if journey.mode == "car":
            edge = self.model.car_graph[u][v]
            edge["occupants"] += 1
            self.model.update_edge_time(edge)
            journey.current_edge_time_remaining = edge["current_travel_time"]
        else:
            edge = self.model.bike_graph[u][v]
            journey.current_edge_time_remaining = edge["current_travel_time"]


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
            # since we set each agent to go on only one trip
            self.has_traveled = True
            return False

        distance = decision["distance"]

        self.current_journey = Journey(
            agent_id=self.unique_id,
            origin=origin,
            destination=destination,
            mode=decision['mode'],

            path=decision['path'],
            current_edge_index=0,
            distance_m=distance,

            started=True,
            started_time=self.model.current_time
        )

        self.enter_edge()

        return True

    def progress_journey(self):
        journey = self.current_journey
        remaining_step_time = self.model.step_time

        while remaining_step_time > 0 and not self.has_traveled:
            time_used = min(remaining_step_time, journey.current_edge_time_remaining)
            journey.current_edge_time_remaining -= time_used
            journey.total_travel_time += time_used
            remaining_step_time -= time_used

            # so if the agent needs more than one tick on the edge then dont leave the edge yet
            if journey.current_edge_time_remaining > 0:
                return

            u = journey.path[journey.current_edge_index]
            v = journey.path[journey.current_edge_index + 1]

            if journey.mode == "car":
                edge = self.model.car_graph[u][v]
                edge["occupants"] -= 1
                self.model.update_edge_time(edge)

            # move on to the next edge
            journey.current_edge_index += 1

            # if reached destination then end the trip
            if journey.current_edge_index >= len(journey.path) - 1:
                journey.finished = True
                journey.end_time = self.model.current_time + (self.model.step_time - remaining_step_time)

                self.end_journey()
                self.has_traveled = True
                return

            self.enter_edge()

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
        '''
        if agent has already travelled: do nothing
        if agent hasnt started: try to start then progress journey, if not possible to start a journey, then the agent is marked as has travelled (in the start_journey method), and wont try to start a journey anymore
        '''

        if self.has_traveled:
            return

        #  to make sure that if the agent cant find a valid trip then it doesnt continue trying to start a journey
        if self.current_journey is None:
            started = self.start_journey()
            if not started:
                return

        self.progress_journey()


class Network(Model):
    def __init__(self, scenario="before", n=150, step_time = 1/60, start_time = 5, end_time = 11, od_pairs = None, rng= None, car_graph = None, bike_graph = None):
        super().__init__(rng = rng)

        self.scenario = scenario
        self.step_time = step_time
        self.start_time = start_time
        self.end_time = end_time

        self.current_time = start_time
        self.completed_journeys = []
        self.od_pairs = od_pairs
        self.network_stats = []

        # load the graphs
        if car_graph is not None and bike_graph is not None:
            self.car_graph = car_graph
            self.bike_graph = bike_graph
        else:
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

        self.initialize_edge_states()

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

        for u, v, k, data in L.edges(keys=True, data=True):
            length = data.get("length", 0)
            lanetype = data.get("lanetype")
            primary_mode = data.get("primary_mode")

            if H.has_edge(u, v):
                if length < H[u][v]["length"]:
                    H[u][v]["length"] = length
                    H[u][v]["primary_mode"] = primary_mode
                    H[u][v]["lanetype"] = lanetype
            else:
                H.add_edge(
                    u, v,
                    length=length,
                    lanetype = lanetype,
                    primary_mode = primary_mode,
                )

        return H


    def initialize_edge_states(self):
        for u, v, data in self.car_graph.edges(data=True):
            length_km = data["length"]/1000
            free_flow_time = length_km/30

            data["occupants"] = 0
            data["capacity"] = self.get_edge_capacity(data)
            data["free_flow_time"] = free_flow_time
            data["current_travel_time"] = free_flow_time

        for u, v, data in self.bike_graph.edges(data=True):
            length_km = data["length"]/1000
            primary_mode = data["primary_mode"]

            if primary_mode == "cycling":
                speed_kmh = 14
            else:
                speed_kmh = 10

            free_flow_time = length_km/speed_kmh
            data["occupants"] = 0
            data["capacity"] = float("inf")
            data["free_flow_time"] = free_flow_time
            data["current_travel_time"] = free_flow_time

    def get_edge_capacity(self, edge_data):
        lanetype = edge_data.get("lanetype")
        length_m = edge_data.get("length", 0)

        # jam space is how many meters per vehicle when its a jam condition
        if lanetype == "H":
            jam_space_m = 8
        elif lanetype == "M":
            jam_space_m = 10
        else:
            return 3

        capacity = length_m/jam_space_m
        return max(capacity, 3)

    def update_edge_time(self, edge_data):
        free_flow_time = edge_data["free_flow_time"]
        occupants = edge_data["occupants"]
        capacity = max(edge_data["capacity"], 1)

        congestion_fac = 1 + 0.15 * (occupants/capacity) ** 2
        edge_data["current_travel_time"] = free_flow_time * congestion_fac


    def get_journeys(self):
        rows = []
        for journey in self.completed_journeys:
            rows.append({
                "agent_id": journey.agent_id,
                "origin": journey.origin,
                "destination": journey.destination,
                "mode": journey.mode,
                "travel_time": journey.total_travel_time,
                "started_time": journey.started_time,
                "end_time": journey.end_time,
                "distance_m": journey.distance_m,
                "travel_time_h": journey.total_travel_time
            })

        return pd.DataFrame(rows)

    def get_traffic_stats(self):
        '''

        Returns
        average congestion level in the network and the average delay/extra travel time due to congestion

        '''
        ratios = []
        delays = []
        relative_delays = []

        for u, v, data in self.car_graph.edges(data=True):
            # so that we sum across edges which are being used at least once rather than the entire network
            occupants = data.get("occupants", 0)
            if occupants == 0:
                continue

            capacity = max(data.get("capacity", 1), 1)
            free_flow_time = data.get("free_flow_time", 0)
            current_travel_time = data.get("current_travel_time", 0)

            ratio = occupants/capacity
            delay = current_travel_time - free_flow_time

            ratios.append(ratio)
            delays.append(delay)

            if free_flow_time > 0:
                relative_delay = delay / free_flow_time
                relative_delays.append(relative_delay)

        if len(ratios) == 0:
            return {
                "average_congestion": 0,
                "average_delay": 0,
                "average_relative_delay": 0
            }


        return {
            "average_congestion": sum(ratios)/len(ratios),
            "average_delay": sum(delays)/len(delays),
            "average_relative_delay": sum(relative_delays)/len(relative_delays),
        }


    def step(self):
        self.schedule.step() # each step shld be 1 min
        self.current_time += self.step_time

        active = sum(agent.current_journey is not None for agent in self.schedule.agents)
        traffic_stats = self.get_traffic_stats()

        self.network_stats.append({
            "time": self.current_time,
            "active_trips": active,
            "average_congestion": traffic_stats["average_congestion"],
            "average_delay": traffic_stats["average_delay"],
            "average_relative_delay": traffic_stats["average_relative_delay"],
        })
