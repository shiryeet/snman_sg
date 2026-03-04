from leuvenmapmatching.util.dist_latlon import destination_radians
from mesa import Agent
from mesa import Model
from mesa.time import RandomActivation
from osgeo.gnm import Network
from patsy import origin
import math

import snman
import os
import random

import networkx as nx
import numpy as np
from matplotlib import pyplot as plt
from dataclasses import dataclass

## mesa version 2.1.5

#todo:
# stagger starts
# add/calculate trip times based on dist
# find snman method to calculate costs for after
# add edge states for traffic flow representation


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

    total_travel_time: float = None
    remaining_time: float = None
    cost_vod: float = None

    started: bool = False
    finished: bool = False
    started_time: float = None
    end_time: float = None



class Traveler(Agent):

    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.current_journey = None

    def choose_mode(self, origin, destination):
        """
        given an origin and destination, calculate cost_vods for bicycle and car.
        compare costs, then choose mode with lower cost (with any probability?)

        Returns
        -------
        mode, path, cost (dictionary)
        """

        graphs = {
            "bike": model.bike_graph,
            "car": model.car_graph,
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

        if not results:
            return None

        chosen_mode = min(results, key = lambda x: results[x]["cost"])

        return{
            "mode": chosen_mode,
            "path": results[chosen_mode]["path"],
            "cost": results[chosen_mode]["cost"],
        }

    def start_journey(self):
        """
        based on mode chosen, create journey state?
        1. pick origin and dest (for now ill just pick random nodes)
        2. choose mode
        3. remaining travel time, mark agent as on journey
        """
        G = self.model.graph

        # choose the origin and destination, origin and destination should be different nodes
        origin = random.choice(list(G.nodes()))
        destination = random.choice(list(G.nodes()))

        while destination == origin:
            destination = random.choice(list(G.nodes()))

        decision = self.choose_mode(origin, destination)
        if decision is None:
            return

        self.current_journey = Journey(
            agent_id=self.unique_id,
            origin=origin,
            destination=destination,
            mode=decision['mode'],

            path=decision['path'],
            current_edge_index=0,

            total_travel_time= 0.5, #need to fix this
            remaining_time=0.5, #need to fix this too
            cost_vod=decision['cost'],

            started=True,
            started_time=self.model.schedule.time
        )

        print(
            f"Agent {self.unique_id} started journey "
            f"{self.current_journey.origin} -> {self.current_journey.destination} "
            f"by {self.current_journey.mode}"
        )

    def progress_journey(self):
        journey = self.current_journey
        journey.remaining_time -= self.model.step_time

        if journey.remaining_time <= 0:
            journey.finished = True
            journey.end_time = self.model.schedule.time

    def end_journey(self):
        """
        based on mode chosen, end timer?
        if more agents on same lane/route of same mode, then journey time increases?
        Returns
        -------
        end_time?
        """

        self.current_journey = None

    def calculate_emissions(self):
        """
        based on mode chosen and time? calculate emissions
        Returns
        -------
        emissions
        """

    def step(self):
        if self.current_journey is None:
            self.start_journey()
            return

        if not self.current_journey.finished:
            self.progress_journey()

        if self.current_journey.finished:
            self.end_journey()



class Network(Model):
    def __init__(self, n=150, step_time = 1/12, start_time = 5, end_time = 11, rng= None):
        super().__init__(rng = rng)

        self.step_time = step_time
        self.start_time = start_time
        self.end_time = end_time

        self.current_time = start_time
        # set up like peak hours and shit?

        # load the graphs
        self.graph = snman.io.load_street_graph(
            edges_path=os.path.join(export_path, 'G_edges.gpkg'),
            nodes_path=os.path.join(export_path, 'G_nodes.gpkg'),
            crs=3414
        )

        self.car_graph = self.build_route_graph('cost_ln_desc_private_cars')
        self.bike_graph = self.build_route_graph('cost_ln_desc_cycling')

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
            agent = Traveler(i, self)
            self.schedule.add(agent)

    def build_route_graph(self, mode):
        # ok so based on some debugging and inspecting the attribute table in QGIS, i think that its because NetworkX graphs need
        # an edge and the REVERSE (so like v -> u) to be stored seperately since its a directed graph after all. but snman stores just the edge,
        # and labels the edge with the cost for both directions if present so when i plug it in with NetworkX its not recognized as bidirectional.
        # so i need to make a like graph for routes where each edge and its reverse is stored separately

        G = self.graph
        H = nx.DiGraph()

        H.add_nodes_from(G.nodes())

        for u, v, k, data in G.edges(keys=True, data=True):
            fwd = data.get(f"{mode}_>", math.inf)
            rev = data.get(f"{mode}_<", math.inf)

            if fwd is not None and not math.isinf(fwd):
                w = float(fwd)
                if H.has_edge(u, v):
                    H[u][v]['weight'] = min(w, H[u][v]['weight']) #need to fix this
                else:
                    H.add_edge(u, v, weight = w)

            if rev is not None and not math.isinf(rev):
                w = float(rev)
                if H.has_edge(v, u):
                    H[v][u]['weight'] = min(w, H[v][u]['weight'])
                else:
                    H.add_edge(v, u, weight = w)
        return H

    def step(self):
        self.schedule.step() # each step shld be 5 mins
        self.current_time += self.step_time
        active = sum(agent.current_journey is not None for agent in self.schedule.agents)
        print(f"Active journeys: {active}")

    """ 
    basically, for the model,we want to create the agents on the rebuilt snman street graph.
    then when we run the model, the agents do their thing (choose a path and mode.) at every tick, 
    the traveler moves along their path until the required amount of time has passed.
    """


# ---------- RUN THE MODEL --------------
model = Network(n=10)
for _ in range(20):
    model.step()