import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import json, re

matplotlib.rcParams['font.family'] = 'serif'
matplotlib.rcParams['font.size'] = 11

# Load data
df = pd.read_csv('reward_breakdown.csv')

# Parse the JSON breakdown column
def parse_breakdown(s):
    # CSV uses "" as escape for " inside quoted fields
    # The raw value looks like: {"capture_reward":0.1, ...} but with "" for "
    s = str(s).strip('"')
    s = s.replace('""', '"')
    # If still wrapped in quotes, strip again
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    # Replace escaped backslash-quote patterns
    s = s.replace('\\"', '"')
    try:
        return json.loads(s)
    except:
        # Fallback: use regex to extract key-value pairs
        pairs = re.findall(r'"(\w+)":\s*([-\d.]+)', s)
        return {k: float(v) for k, v in pairs}

breakdowns = df['reward_breakdown'].apply(parse_breakdown)
bd_df = pd.json_normalize(breakdowns)
df = pd.concat([df.drop(columns=['reward_breakdown']), bd_df], axis=1)

sent = df[df['team'] == 'Sentinel'].reset_index(drop=True)
run  = df[df['team'] == 'Runner'].reset_index(drop=True)

# Add sequential episode index
sent['ep_idx'] = range(len(sent))
run['ep_idx']  = range(len(run))

# Smoothing function
def smooth(y, window=50):
    return pd.Series(y).rolling(window, min_periods=1).mean()

# ============ FIGURE 1: Total Reward Curves ============
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Sentinel
ax = axes[0]
ax.plot(sent['ep_idx'], sent['total_reward'], alpha=0.15, color='#2196F3', linewidth=0.5)
ax.plot(sent['ep_idx'], smooth(sent['total_reward']), color='#1565C0', linewidth=2, label='Smoothed (50-ep)')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
ax.set_xlabel('Episode')
ax.set_ylabel('Total Reward')
ax.set_title('Sentinel Team — Cumulative Reward per Episode')
ax.legend()
ax.grid(True, alpha=0.3)

# Runner
ax = axes[1]
ax.plot(run['ep_idx'], run['total_reward'], alpha=0.15, color='#E91E63', linewidth=0.5)
ax.plot(run['ep_idx'], smooth(run['total_reward']), color='#AD1457', linewidth=2, label='Smoothed (50-ep)')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
ax.set_xlabel('Episode')
ax.set_ylabel('Total Reward')
ax.set_title('Runner Team — Cumulative Reward per Episode')
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('paper/fig_reward_curves.pdf', dpi=300, bbox_inches='tight')
plt.savefig('paper/fig_reward_curves.png', dpi=150, bbox_inches='tight')
print("Figure 1 saved: Total reward curves")

# ============ FIGURE 2: Reward Component Breakdown ============
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Sentinel breakdown
ax = axes[0]
ax.plot(sent['ep_idx'], smooth(sent['terminal_reward']), linewidth=2, label='Terminal (±1.0)', color='#1B5E20')
ax.plot(sent['ep_idx'], smooth(sent['shaping_reward']), linewidth=2, label='Shaping', color='#FF9800')
ax.plot(sent['ep_idx'], smooth(sent['exploration_reward']), linewidth=2, label='Exploration', color='#9C27B0')
ax.plot(sent['ep_idx'], smooth(sent['penalties']), linewidth=2, label='Penalties', color='#F44336')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
ax.set_xlabel('Episode')
ax.set_ylabel('Reward Component')
ax.set_title('Sentinel — Reward Component Breakdown')
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

# Runner breakdown
ax = axes[1]
ax.plot(run['ep_idx'], smooth(run['terminal_reward']), linewidth=2, label='Terminal (±1.0)', color='#1B5E20')
ax.plot(run['ep_idx'], smooth(run['shaping_reward']), linewidth=2, label='Shaping', color='#FF9800')
ax.plot(run['ep_idx'], smooth(run['exploration_reward']), linewidth=2, label='Exploration', color='#9C27B0')
ax.plot(run['ep_idx'], smooth(run['penalties']), linewidth=2, label='Penalties', color='#F44336')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
ax.set_xlabel('Episode')
ax.set_ylabel('Reward Component')
ax.set_title('Runner — Reward Component Breakdown')
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('paper/fig_reward_breakdown.pdf', dpi=300, bbox_inches='tight')
plt.savefig('paper/fig_reward_breakdown.png', dpi=150, bbox_inches='tight')
print("Figure 2 saved: Reward component breakdown")

# ============ FIGURE 3: Win Rate (rolling) ============
fig, ax = plt.subplots(figsize=(10, 5))

# Sentinel win = terminal_reward > 0 (episode_win = 3.0)
sent_wins = (sent['terminal_reward'] > 0).astype(float)
win_rate = smooth(sent_wins, window=100)
ax.plot(sent['ep_idx'], win_rate, linewidth=2.5, color='#1565C0', label='Sentinel Win Rate (100-ep rolling)')
ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5, label='50% baseline')
ax.set_xlabel('Episode')
ax.set_ylabel('Win Rate')
ax.set_title('Sentinel Win Rate Over Training')
ax.set_ylim(0, 1)
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('paper/fig_win_rate.pdf', dpi=300, bbox_inches='tight')
plt.savefig('paper/fig_win_rate.png', dpi=150, bbox_inches='tight')
print("Figure 3 saved: Win rate curve")

# ============ FIGURE 4: Penalty reduction over training ============
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(sent['ep_idx'], smooth(sent['wall_loop_penalty'], window=50), linewidth=2, color='#F44336', label='Wall-loop penalty (Sentinel)')
ax.plot(run['ep_idx'], smooth(run['threat_approach_penalty'], window=50), linewidth=2, color='#E91E63', label='Threat-approach penalty (Runner)')
ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
ax.set_xlabel('Episode')
ax.set_ylabel('Penalty Value (per episode)')
ax.set_title('Penalty Reduction Over Training — Evidence of Learning')
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('paper/fig_penalty_reduction.pdf', dpi=300, bbox_inches='tight')
plt.savefig('paper/fig_penalty_reduction.png', dpi=150, bbox_inches='tight')
print("Figure 4 saved: Penalty reduction")

# Print summary stats
print("\n=== Summary Statistics ===")
print(f"Total episodes: {len(sent)}")
print(f"\nSentinel mean total reward: {sent['total_reward'].mean():.3f}")
print(f"Runner mean total reward:   {run['total_reward'].mean():.3f}")
print(f"\nSentinel win rate (overall): {(sent['terminal_reward'] > 0).mean():.1%}")
print(f"Sentinel win rate (last 100): {(sent['terminal_reward'].tail(100) > 0).mean():.1%}")
print(f"\nMean wall_loop_penalty first 100: {sent['wall_loop_penalty'].head(100).mean():.4f}")
print(f"Mean wall_loop_penalty last 100:  {sent['wall_loop_penalty'].tail(100).mean():.4f}")
