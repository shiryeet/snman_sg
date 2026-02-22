from mesa import Agent
import snman
import os
import random

import networkx as nx
import numpy as np
from matplotlib import pyplot as plt
from dataclasses import dataclass



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
    travel_time: float = None
    cost_vod: float = None
    length: float = None


class Traveler(Agent):

    def __init__(self, unique_id, model):
         super().__init__(unique_id, model)


    def choose_mode(self):
        """
        given an origin and destination, calculate cost_vods for bicycle and car.
        compare costs, then choose mode with lower cost (with any probability?)

        Returns
        -------
        mode
        """

    def start_journey(self):
        """
        based on mode chosen, create journey state?
        set agent as on a journey

        Returns
        -------
        Journey
        """

    def end_journey(self):
        """
        based on mode chosen, end timer?
        if more agents on same lane/route of same mode, then journey time increases?
        Returns
        -------
        end_time?
        """

    def calculate_emissions(self):
        """
        based on mode chosen and time? calculate emissions
        Returns
        -------
        emissions
        """

    def step(self):
        """
        if not on journey:
            choose mode
            start journey
        elif on journey:
            progress journey
            if finished: end journey

        Returns
        -------

        """


class Network(Model):
    def __init__(self, n=150, rng= None):
        super().__init__(rng = rng)

