# Project Overview

## Project Name

Labyrinth Breach

## Summary

Labyrinth Breach is a Unity ML-Agents project for asymmetric multi-agent reinforcement learning in pursuit-evasion environments. The final environment uses 3 Sentinels as pursuers and 2 Runners as evaders in static and dynamic maze layouts.

The project is designed for an AI for Robotics final submission and a research-paper-ready prototype. It must support reproducible training, evaluation, ablation studies, and clear evidence of learned coordination.

## Goal

The goal is to build a configurable 3v2 pursuit-evasion system where agents learn spatial tactics, not only direct chasing.

Sentinels should learn:

- trapping
- pincer movement
- corridor denial
- exit blocking
- route cutting

Runners should learn:

- survival
- maze exploration
- split pressure
- decoy behavior
- exit reaching under uncertainty

## Environment

The environment evolves through staged complexity:

- open arena baseline
- static maze with exits
- dynamic maze with shifting walls
- unseen maze layouts for evaluation

The dynamic maze uses modular wall elements that can raise or lower during an episode. This changes routes, breaks memorization, and creates opportunities for tactical coordination.

## Agent Setup

The final setup is:

- 3 Sentinels as pursuers
- 2 Runners as evaders

Sentinels are slightly slower but optimized for blocking and coordinated capture. Runners are slightly faster and optimized for survival, route selection, and exit reaching. This asymmetry is configurable and is part of the research design.

## Research Question

The project tests whether standard team-reward multi-agent reinforcement learning can learn meaningful coordinated trap formation in dynamic maze pursuit-evasion, or whether trap-aware shaping, memory under broken line of sight, and dynamic topology are needed to produce stronger cooperation.

Core comparisons include:

- open arena vs static maze vs dynamic maze
- shared basic reward vs trap-aware reward
- memory enabled vs memory disabled
- seen maze seeds vs unseen maze seeds
- PPO vs MA-POCA if feasible

## Expected Outputs

The repository should produce:

- working Unity ML-Agents environments
- versioned training configs
- versioned environment and reward configs
- reproducible experiment manifests
- logs and metrics for each run
- paper-ready plots, tables, and summaries

