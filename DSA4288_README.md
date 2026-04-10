# Adapting SNMan for a Singapore Context and Agent Based Modelling (DSA4288)

## Overview
This repository contains my DSA4288 honours project work, based on the SNMan (Street Network Manipulator) toolkit.
The project applies SNMan to Singapore's street network, and investigates the potential structural and behavioural outcomes of a reallocated network for cycling, with agent-based modelling

## Main repository structure
- `snman/` — original SNMan source code, with modifications for Singapore
- `sg/` — Singapore-specific analysis notebooks, scripts, and ABM work
- `custom_inputs/` — Singapore-specific input files seperate from the original SNMan pipeline (GTFS data)
- `inputs/` — pipeline input files
- `outputs/` — generated outputs from the SNMan pipeline

## Main modifications from upstream
- Singapore-specific geospatial inputs and configuration of SNMan
- notebooks and scrips for Singapore-specific analysis
- Agent Based Model implementation and exploratory work (in `sg/ABM/`)

## Notes
See the original README for upstream installation and package information
