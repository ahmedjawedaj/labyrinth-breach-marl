#!/usr/bin/env python3
"""
Publication-quality plotting for Labyrinth Breach MARL training results.
Generates IEEE-formatted figures spanning the full 3-phase curriculum
plus zero-shot unseen-maze evaluation.

CSV structure (from reward_breakdown.csv):
  Rows 0-143:      Early Open Arena (short restarts during debugging)
  Rows 144-3371:   Main training: Open Arena → Static Maze (v5_openarena + v5_staticmaze)
  Rows 3372-5863:  Dynamic Maze (v5_dynamicmaze) with multiple session restarts
  Rows 5864-5893:  Unseen Maze evaluation (inference only, no training)

For clean figures we use only the main contiguous training data:
  Phase 1: rows 144-3371  (Open Arena + Static Maze, ~3228 episodes)
  Phase 2: rows 3372-5863 (Dynamic Maze, all restarts merged, ~2492 episodes)
  Phase 3: rows 5864-5893 (Unseen Eval, ~30 episodes)
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import json, re, os

# ---------- IEEE-quality style ----------
matplotlib.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'legend.fontsize': 8.5,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.grid': True,
    'grid.alpha': 0.25,
    'grid.linewidth': 0.5,
})

OUT_DIR = 'paper'
os.makedirs(OUT_DIR, exist_ok=True)

# ============================================================
# 1. Load and parse CSV
# ============================================================
df = pd.read_csv('reward_breakdown.csv')

def parse_breakdown(s):
    s = str(s).strip('"').replace('""', '"')
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    s = s.replace('\\"', '"')
    try:
        return json.loads(s)
    except:
        pairs = re.findall(r'"(\w+)":\s*([-\d.]+)', s)
        return {k: float(v) for k, v in pairs}

breakdowns = df['reward_breakdown'].apply(parse_breakdown)
bd_df = pd.json_normalize(breakdowns)
df = pd.concat([df.drop(columns=['reward_breakdown']), bd_df], axis=1)

# Split by team
sent_full = df[df['team'] == 'Sentinel'].reset_index(drop=True)
run_full  = df[df['team'] == 'Runner'].reset_index(drop=True)

# ============================================================
# Define phase boundaries (from segment analysis)
# ============================================================
# We skip the first 144 early debug episodes for clean plots
PHASE_1_START = 144   # Open Arena + Static Maze main run
PHASE_1_END   = 3372
PHASE_2_START = 3372  # Dynamic Maze (all restarts merged)
PHASE_2_END   = 5864
PHASE_3_START = 5864  # Unseen Eval
PHASE_3_END   = len(sent_full)

# Use only main training data for continuous charts
sent = sent_full.iloc[PHASE_1_START:PHASE_2_END].reset_index(drop=True)
run  = run_full.iloc[PHASE_1_START:PHASE_2_END].reset_index(drop=True)
sent['ep_idx'] = range(len(sent))
run['ep_idx']  = range(len(run))

# Unseen eval data (separate)
sent_unseen = sent_full.iloc[PHASE_3_START:PHASE_3_END].reset_index(drop=True)
run_unseen  = run_full.iloc[PHASE_3_START:PHASE_3_END].reset_index(drop=True)

# Phase boundary in the re-indexed data
PHASE_BOUNDARY = PHASE_1_END - PHASE_1_START  # where Static→Dynamic transition happens

def smooth(y, window=50):
    return pd.Series(y).rolling(window, min_periods=1).mean()

BLUE = '#0D47A1'
RED = '#C62828'

def add_phase_bands(ax):
    ymin, ymax = ax.get_ylim()
    ax.axvspan(0, PHASE_BOUNDARY, alpha=0.08, color='#4CAF50', zorder=0)
    ax.axvspan(PHASE_BOUNDARY, len(sent), alpha=0.08, color='#FF9800', zorder=0)
    # Add phase labels at top
    ax.text(PHASE_BOUNDARY / 2, ymax * 0.96, 'Open Arena → Static Maze',
            ha='center', va='top', fontsize=7.5, fontstyle='italic', alpha=0.6)
    ax.text(PHASE_BOUNDARY + (len(sent) - PHASE_BOUNDARY) / 2, ymax * 0.96,
            'Dynamic Maze', ha='center', va='top', fontsize=7.5,
            fontstyle='italic', alpha=0.6)
    ax.axvline(x=PHASE_BOUNDARY, color='gray', linestyle=':', alpha=0.5, linewidth=1)

# ============================================================
# FIGURE 1: Total Reward Curves
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))

ax = axes[0]
ax.plot(sent['ep_idx'], sent['total_reward'], alpha=0.08, color='#2196F3', linewidth=0.4)
ax.plot(sent['ep_idx'], smooth(sent['total_reward']), color=BLUE,
        linewidth=2, label='50-ep rolling mean')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.4)
ax.set_xlabel('Episode')
ax.set_ylabel('Cumulative Reward')
ax.set_title('Sentinel Team')
ax.legend(loc='upper right')
add_phase_bands(ax)

ax = axes[1]
ax.plot(run['ep_idx'], run['total_reward'], alpha=0.08, color='#E91E63', linewidth=0.4)
ax.plot(run['ep_idx'], smooth(run['total_reward']), color=RED,
        linewidth=2, label='50-ep rolling mean')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.4)
ax.set_xlabel('Episode')
ax.set_ylabel('Cumulative Reward')
ax.set_title('Runner Team')
ax.legend(loc='upper right')
add_phase_bands(ax)

fig.suptitle('Per-Episode Cumulative Reward Across Curriculum Phases', fontsize=13, y=1.02)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/fig_reward_curves.pdf', bbox_inches='tight')
plt.savefig(f'{OUT_DIR}/fig_reward_curves.png', bbox_inches='tight')
plt.close()
print("Figure 1 saved: Total reward curves")

# ============================================================
# FIGURE 2: Reward Component Breakdown
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))

ax = axes[0]
ax.plot(sent['ep_idx'], smooth(sent['terminal_reward']), linewidth=1.8,
        label='Terminal (win/loss)', color='#1B5E20')
ax.plot(sent['ep_idx'], smooth(sent['shaping_reward']), linewidth=1.8,
        label='Shaping', color='#FF9800')
if 'trap_aware_reward' in sent.columns:
    ax.plot(sent['ep_idx'], smooth(sent['trap_aware_reward']), linewidth=1.8,
            label='Trap-aware', color='#7B1FA2')
ax.plot(sent['ep_idx'], smooth(sent['penalties']), linewidth=1.8,
        label='Penalties', color='#D32F2F')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.4)
ax.set_xlabel('Episode')
ax.set_ylabel('Reward Component')
ax.set_title('Sentinel — Reward Decomposition')
ax.legend(fontsize=8, loc='lower left')
add_phase_bands(ax)

ax = axes[1]
ax.plot(run['ep_idx'], smooth(run['terminal_reward']), linewidth=1.8,
        label='Terminal (win/loss)', color='#1B5E20')
ax.plot(run['ep_idx'], smooth(run['shaping_reward']), linewidth=1.8,
        label='Shaping', color='#FF9800')
ax.plot(run['ep_idx'], smooth(run['penalties']), linewidth=1.8,
        label='Penalties', color='#D32F2F')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.4)
ax.set_xlabel('Episode')
ax.set_ylabel('Reward Component')
ax.set_title('Runner — Reward Decomposition')
ax.legend(fontsize=8, loc='lower left')
add_phase_bands(ax)

fig.suptitle('Reward Component Breakdown Across Curriculum', fontsize=13, y=1.02)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/fig_reward_breakdown.pdf', bbox_inches='tight')
plt.savefig(f'{OUT_DIR}/fig_reward_breakdown.png', bbox_inches='tight')
plt.close()
print("Figure 2 saved: Reward component breakdown")

# ============================================================
# FIGURE 3: Dual Win Rate — Sentinel AND Runner
# ============================================================
fig, ax = plt.subplots(figsize=(10, 4.5))

sent_wins = (sent['terminal_reward'] > 0).astype(float)
run_wins  = (run['terminal_reward'] > 0).astype(float)

sentinel_wr = smooth(sent_wins, window=100)
runner_wr   = smooth(run_wins, window=100)

ax.plot(sent['ep_idx'], sentinel_wr, linewidth=2.5, color=BLUE,
        label='Sentinel Win Rate (100-ep)')
ax.plot(run['ep_idx'], runner_wr, linewidth=2.5, color=RED,
        label='Runner Win Rate (100-ep)')
ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5, label='Nash equilibrium (50%)')
ax.fill_between(sent['ep_idx'], sentinel_wr, 0.5,
                where=sentinel_wr >= 0.5, alpha=0.06, color=BLUE)
ax.fill_between(run['ep_idx'], runner_wr, 0.5,
                where=runner_wr >= 0.5, alpha=0.06, color=RED)

add_phase_bands(ax)
ax.set_xlabel('Episode')
ax.set_ylabel('Win Rate')
ax.set_title('Win Rate Convergence Across Curriculum Phases')
ax.set_ylim(-0.02, 1.02)
ax.legend(loc='center right')

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/fig_win_rate.pdf', bbox_inches='tight')
plt.savefig(f'{OUT_DIR}/fig_win_rate.png', bbox_inches='tight')
plt.close()
print("Figure 3 saved: Dual win rate curve")

# ============================================================
# FIGURE 4: Penalty reduction (Sentinel + Runner side by side)
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))

ax = axes[0]
ax.plot(sent['ep_idx'], smooth(sent['wall_loop_penalty'], 50),
        linewidth=2, color='#D32F2F', label='Wall-loop')
if 'cluster_penalty' in sent.columns:
    ax.plot(sent['ep_idx'], smooth(sent['cluster_penalty'], 50),
            linewidth=2, color='#F57C00', label='Cluster')
if 'sentinel_idle_penalty' in sent.columns:
    ax.plot(sent['ep_idx'], smooth(sent['sentinel_idle_penalty'], 50),
            linewidth=2, color='#7B1FA2', label='Idle')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.4)
ax.set_xlabel('Episode')
ax.set_ylabel('Penalty (per episode)')
ax.set_title('Sentinel Penalties')
ax.legend(fontsize=8)
add_phase_bands(ax)

ax = axes[1]
ax.plot(run['ep_idx'], smooth(run['wall_loop_penalty'], 50),
        linewidth=2, color='#D32F2F', label='Wall-loop')
ax.plot(run['ep_idx'], smooth(run['threat_approach_penalty'], 50),
        linewidth=2, color='#C62828', label='Threat-approach')
if 'exit_approach_regression' in run.columns:
    ax.plot(run['ep_idx'], smooth(run['exit_approach_regression'], 50),
            linewidth=2, color='#1565C0', label='Exit regression')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.4)
ax.set_xlabel('Episode')
ax.set_ylabel('Penalty (per episode)')
ax.set_title('Runner Penalties')
ax.legend(fontsize=8)
add_phase_bands(ax)

fig.suptitle('Penalty Reduction Over Training — Evidence of Behavioral Learning', fontsize=13, y=1.02)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/fig_penalty_reduction.pdf', bbox_inches='tight')
plt.savefig(f'{OUT_DIR}/fig_penalty_reduction.png', bbox_inches='tight')
plt.close()
print("Figure 4 saved: Penalty reduction")

# ============================================================
# FIGURE 5: Tactical Shaping Signals
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))

ax = axes[0]
if 'chase_progress' in sent.columns:
    ax.plot(sent['ep_idx'], smooth(sent['chase_progress'], 50),
            linewidth=2, color='#1B5E20', label='Chase progress')
if 'chase_regression' in sent.columns:
    ax.plot(sent['ep_idx'], smooth(sent['chase_regression'], 50),
            linewidth=2, color='#D32F2F', label='Chase regression')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.4)
ax.set_xlabel('Episode')
ax.set_ylabel('Shaping Reward')
ax.set_title('Sentinel — Pursuit Shaping')
ax.legend(fontsize=8)
add_phase_bands(ax)

ax = axes[1]
if 'evade_progress' in run.columns:
    ax.plot(run['ep_idx'], smooth(run['evade_progress'], 50),
            linewidth=2, color='#1B5E20', label='Evade progress')
if 'exit_approach_progress' in run.columns:
    ax.plot(run['ep_idx'], smooth(run['exit_approach_progress'], 50),
            linewidth=2, color='#1565C0', label='Exit approach')
if 'exit_approach_regression' in run.columns:
    ax.plot(run['ep_idx'], smooth(run['exit_approach_regression'], 50),
            linewidth=2, color='#D32F2F', label='Exit regression')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.4)
ax.set_xlabel('Episode')
ax.set_ylabel('Shaping Reward')
ax.set_title('Runner — Evasion & Exit-Seeking Shaping')
ax.legend(fontsize=8)
add_phase_bands(ax)

fig.suptitle('Distance-Based Shaping Signals Over Training', fontsize=13, y=1.02)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/fig_shaping_signals.pdf', bbox_inches='tight')
plt.savefig(f'{OUT_DIR}/fig_shaping_signals.png', bbox_inches='tight')
plt.close()
print("Figure 5 saved: Shaping signals")

# ============================================================
# FIGURE 6: Per-Phase Summary Bar Chart
# ============================================================
# Compute per-phase stats using the full data
phases = {
    'Open Arena\n+ Static': (PHASE_1_START, PHASE_1_END),
    'Dynamic\nMaze': (PHASE_2_START, PHASE_2_END),
    'Unseen\nMaze': (PHASE_3_START, PHASE_3_END),
}

phase_names = list(phases.keys())
sentinel_wr_per_phase = []
runner_wr_per_phase = []
sent_mean_reward = []
run_mean_reward = []

for name, (start, end) in phases.items():
    s = sent_full.iloc[start:end]
    r = run_full.iloc[start:end]
    sentinel_wr_per_phase.append((s['terminal_reward'] > 0).mean())
    runner_wr_per_phase.append((r['terminal_reward'] > 0).mean())
    sent_mean_reward.append(s['total_reward'].mean())
    run_mean_reward.append(r['total_reward'].mean())

fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

x = np.arange(len(phase_names))
width = 0.32

ax = axes[0]
bars1 = ax.bar(x - width/2, sentinel_wr_per_phase, width, label='Sentinel',
               color=BLUE, alpha=0.85)
bars2 = ax.bar(x + width/2, runner_wr_per_phase, width, label='Runner',
               color=RED, alpha=0.85)
ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
ax.set_ylabel('Win Rate')
ax.set_title('Win Rate by Curriculum Phase')
ax.set_xticks(x)
ax.set_xticklabels(phase_names, fontsize=9)
ax.set_ylim(0, 1.15)
ax.legend()
for bar in bars1:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
            f'{bar.get_height():.1%}', ha='center', va='bottom', fontsize=8, fontweight='bold')
for bar in bars2:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
            f'{bar.get_height():.1%}', ha='center', va='bottom', fontsize=8, fontweight='bold')

ax = axes[1]
bars1 = ax.bar(x - width/2, sent_mean_reward, width, label='Sentinel',
               color=BLUE, alpha=0.85)
bars2 = ax.bar(x + width/2, run_mean_reward, width, label='Runner',
               color=RED, alpha=0.85)
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
ax.set_ylabel('Mean Total Reward')
ax.set_title('Mean Reward by Curriculum Phase')
ax.set_xticks(x)
ax.set_xticklabels(phase_names, fontsize=9)
ax.legend()
for bar in bars1:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.05 if h >= 0 else h - 0.15,
            f'{h:+.2f}', ha='center', va='bottom' if h >= 0 else 'top',
            fontsize=8, fontweight='bold')
for bar in bars2:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h - 0.15,
            f'{h:+.2f}', ha='center', va='top', fontsize=8, fontweight='bold')

fig.suptitle('Per-Phase Performance Summary', fontsize=13, y=1.02)
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/fig_phase_summary.pdf', bbox_inches='tight')
plt.savefig(f'{OUT_DIR}/fig_phase_summary.png', bbox_inches='tight')
plt.close()
print("Figure 6 saved: Phase summary bar chart")

# ============================================================
# Print comprehensive summary statistics
# ============================================================
print("\n" + "="*60)
print("COMPREHENSIVE TRAINING SUMMARY")
print("="*60)

for name, (start, end) in phases.items():
    s = sent_full.iloc[start:end]
    r = run_full.iloc[start:end]
    n = len(s)
    clean_name = name.replace('\n', ' ')
    print(f"\n--- {clean_name} ({n} episodes) ---")
    print(f"  Sentinel win rate:     {(s['terminal_reward'] > 0).mean():.1%}")
    print(f"  Runner   win rate:     {(r['terminal_reward'] > 0).mean():.1%}")
    print(f"  Sentinel mean reward:  {s['total_reward'].mean():+.3f}")
    print(f"  Runner   mean reward:  {r['total_reward'].mean():+.3f}")
    print(f"  Sentinel wall-loop:    {s['wall_loop_penalty'].mean():.4f}")
    if 'cluster_penalty' in s.columns:
        print(f"  Sentinel cluster:      {s['cluster_penalty'].mean():.4f}")

# Dynamic Maze last 200 episodes
dm = sent_full.iloc[PHASE_2_START:PHASE_2_END]
dm_last = dm.tail(200)
rm_last = run_full.iloc[PHASE_2_START:PHASE_2_END].tail(200)
print(f"\n--- Dynamic Maze (last 200 episodes) ---")
print(f"  Sentinel win rate:     {(dm_last['terminal_reward'] > 0).mean():.1%}")
print(f"  Runner   win rate:     {(rm_last['terminal_reward'] > 0).mean():.1%}")

# Unseen Eval
print(f"\n--- Unseen Maze Evaluation ({len(sent_unseen)} episodes) ---")
print(f"  Sentinel win rate:     {(sent_unseen['terminal_reward'] > 0).mean():.1%}")
print(f"  Runner   win rate:     {(run_unseen['terminal_reward'] > 0).mean():.1%}")
print(f"  Sentinel mean reward:  {sent_unseen['total_reward'].mean():+.3f}")
print(f"  Runner   mean reward:  {run_unseen['total_reward'].mean():+.3f}")
