#!/usr/bin/env python3
"""
nouzen_analysis.py
==================
Full experimental analysis for NOUZEN AprilTag docking validation.
Reads all mission_*.csv files, produces aggregate statistics and
publication-quality figures for the SCSS paper.

ALL values are computed from data — nothing is hardcoded.

Usage:
    python3 nouzen_analysis.py <logs_dir> [--out <output_dir>]

Example:
    python3 nouzen_analysis.py ./logs_EPS/logs_EPS --out ./figures
"""

import argparse
import glob
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy import stats as sp_stats

# ── optional: Wilson CI ──────────────────────────────────────────
try:
    from statsmodels.stats.proportion import proportion_confint
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


# ═══════════════════════════════════════════════════════════════
# 0.  GLOBAL STYLE
# ═══════════════════════════════════════════════════════════════

PALETTE = {
    'home':     '#2196F3',
    'input_a':  '#4CAF50',
    'input_b':  '#8BC34A',
    'output_a': '#FF9800',
    'output_b': '#F44336',
}
DOCK_ORDER = ['home', 'input_a', 'input_b', 'output_a', 'output_b']

def dock_color(dock_id):
    return PALETTE.get(dock_id, '#9E9E9E')

def apply_style():
    plt.rcParams.update({
        'font.family':       'sans-serif',
        'font.sans-serif':   ['DejaVu Sans', 'Helvetica', 'Arial'],
        'font.size':         10,
        'axes.titlesize':    12,
        'axes.labelsize':    11,
        'xtick.labelsize':   9,
        'ytick.labelsize':   9,
        'legend.fontsize':   9,
        'figure.dpi':        200,
        'savefig.dpi':       200,
        'savefig.bbox':      'tight',
        'axes.spines.top':   False,
        'axes.spines.right': False,
        'axes.grid':         True,
        'grid.alpha':        0.3,
        'grid.linewidth':    0.5,
    })

def save(fig, name, out_dir):
    path = os.path.join(out_dir, f'{name}.png')
    fig.savefig(path, facecolor='white')
    plt.close(fig)
    print(f'  ✓ {path}')
    return path


# ═══════════════════════════════════════════════════════════════
# 1.  DATA LOADING + BLOCK ASSIGNMENT
# ═══════════════════════════════════════════════════════════════

def load_all_csvs(logs_dir):
    """Load and concatenate all mission CSV files."""
    pattern = os.path.join(logs_dir, 'mission_*.csv')
    files = sorted(glob.glob(pattern))
    if not files:
        sys.exit(f'ERROR: no CSV files found in {logs_dir}')

    frames = []
    for f in files:
        df = pd.read_csv(f)
        df['_source_file'] = os.path.basename(f)
        frames.append(df)

    df = pd.concat(frames, ignore_index=True)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def assign_blocks(df):
    """
    Assign each row to Block A / B / C based on mission_name pattern
    and temporal ordering.

    Block B = test_full_ap missions.
    Block A = single-dock missions from the FIRST session window (morning).
    Block C = single-dock missions from the SECOND session window (afternoon).
    """
    df = df.copy()
    df['block'] = ''

    # Block B: all test_full_ap
    mask_b = df['mission_name'] == 'test_full_ap'
    df.loc[mask_b, 'block'] = 'B'

    # For single-dock missions, split by temporal midpoint
    single = df[~mask_b].copy()
    if len(single) > 0:
        # Find the gap between Block A and Block C
        # Use the test_full_ap start time as the divider
        block_b_rows = df[mask_b]
        if len(block_b_rows) > 0:
            b_start = block_b_rows['timestamp'].min()
            df.loc[(~mask_b) & (df['timestamp'] < b_start), 'block'] = 'A'
            df.loc[(~mask_b) & (df['timestamp'] > b_start), 'block'] = 'C'
        else:
            # No Block B? All single-dock = Block A
            df.loc[~mask_b, 'block'] = 'A'

    return df


def mission_level_results(df):
    """
    For test_full_ap: compute per-mission success (all 4 docks OK).
    Returns a DataFrame with one row per mission file.
    """
    tfap = df[(df['mission_name'] == 'test_full_ap')].copy()
    results = []
    for src, grp in tfap.groupby('_source_file'):
        dock_rows = grp[grp['action'] == 'dock']
        n_dock = len(dock_rows)
        n_ok = (dock_rows['result'] == 'SUCCESS').sum()
        total_dur = grp['duration_sec'].sum()
        mission_ok = (n_dock == 4) and (n_ok == 4)
        results.append({
            'file': src,
            'n_docks': n_dock,
            'n_success': n_ok,
            'mission_pass': mission_ok,
            'total_duration_sec': total_dur,
        })
    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════
# 2.  WILSON CONFIDENCE INTERVAL
# ═══════════════════════════════════════════════════════════════

def wilson_ci(k, n, alpha=0.05):
    """Wilson score interval for binomial proportion."""
    if HAS_STATSMODELS:
        lo, hi = proportion_confint(k, n, alpha=alpha, method='wilson')
        return lo, hi
    # Manual fallback
    z = sp_stats.norm.ppf(1 - alpha / 2)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return center - margin, center + margin


# ═══════════════════════════════════════════════════════════════
# 3.  FIGURES
# ═══════════════════════════════════════════════════════════════

# ── Fig 1: Success rate per dock ──────────────────────────────

def fig_success_rate(dock_df, out_dir):
    """Bar chart: success rate per dock station with Wilson 95% CI."""
    fig, ax = plt.subplots(figsize=(7, 4))

    docks = [d for d in DOCK_ORDER if d in dock_df['dock_id'].unique()]
    rates, ci_lo, ci_hi, colors, ns = [], [], [], [], []

    for did in docks:
        sub = dock_df[dock_df['dock_id'] == did]
        n = len(sub)
        k = (sub['result'] == 'SUCCESS').sum()
        rate = k / n if n > 0 else 0
        lo, hi = wilson_ci(k, n) if n > 0 else (0, 0)
        rates.append(rate * 100)
        ci_lo.append((rate - lo) * 100)
        ci_hi.append((hi - rate) * 100)
        colors.append(dock_color(did))
        ns.append(n)

    x = np.arange(len(docks))
    bars = ax.bar(x, rates, color=colors, width=0.6, edgecolor='white',
                  linewidth=0.8, zorder=3)
    ax.errorbar(x, rates, yerr=[ci_lo, ci_hi], fmt='none', ecolor='#333',
                capsize=4, capthick=1.2, zorder=4)

    # Add n= labels
    for i, (bar, n) in enumerate(zip(bars, ns)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 3,
                f'n={n}', ha='center', va='bottom', fontsize=8, color='#555')

    ax.set_xticks(x)
    ax.set_xticklabels(docks, rotation=0)
    ax.set_ylabel('Success Rate (%)')
    ax.set_ylim(0, 115)
    ax.set_title('Docking Success Rate per Station (Wilson 95% CI)')
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))

    # Overall line
    n_all = len(dock_df)
    k_all = (dock_df['result'] == 'SUCCESS').sum()
    overall = k_all / n_all * 100
    ax.axhline(overall, color='#333', ls='--', lw=1, alpha=0.5)
    ax.text(len(docks) - 0.5, overall + 1.5,
            f'Overall: {overall:.0f}%', ha='right', fontsize=8, color='#333')

    fig.tight_layout()
    return save(fig, 'fig1_success_rate', out_dir)


# ── Fig 2: Position error box plot ───────────────────────────

def fig_pos_error_boxplot(ok_df, out_dir):
    """Box plot: position error per dock station."""
    fig, ax = plt.subplots(figsize=(7, 4))

    docks = [d for d in DOCK_ORDER if d in ok_df['dock_id'].unique()]
    data = [ok_df[ok_df['dock_id'] == d]['pos_error_m'].dropna().values
            for d in docks]
    colors = [dock_color(d) for d in docks]

    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='#222', lw=2),
                    whiskerprops=dict(color='#666'),
                    capprops=dict(color='#666'),
                    flierprops=dict(marker='o', markersize=5,
                                   markerfacecolor='#999', alpha=0.7))
    for patch, c in zip(bp['boxes'], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.7)

    # Overlay individual points
    for i, (d, vals) in enumerate(zip(docks, data)):
        jitter = np.random.default_rng(42).normal(0, 0.04, len(vals))
        ax.scatter(np.full_like(vals, i + 1) + jitter, vals,
                   color=dock_color(d), edgecolor='white', s=25,
                   linewidths=0.5, zorder=5, alpha=0.8)

    ax.set_xticklabels(docks)
    ax.set_ylabel('Position Error (m)')
    ax.set_title('Final Docking Position Error per Station')

    # Overall median line
    all_pos = ok_df['pos_error_m'].dropna()
    ax.axhline(all_pos.median(), color='#333', ls='--', lw=1, alpha=0.5)
    ax.text(len(docks) + 0.3, all_pos.median(),
            f'Median: {all_pos.median():.3f} m', va='center', fontsize=8,
            color='#333')

    fig.tight_layout()
    return save(fig, 'fig2_pos_error_boxplot', out_dir)


# ── Fig 3: Duration box plot ─────────────────────────────────

def fig_duration_boxplot(ok_df, out_dir):
    """Box plot: dock duration per station (successful docks only)."""
    fig, ax = plt.subplots(figsize=(7, 4))

    docks = [d for d in DOCK_ORDER if d in ok_df['dock_id'].unique()]
    data = [ok_df[ok_df['dock_id'] == d]['duration_sec'].dropna().values
            for d in docks]
    colors = [dock_color(d) for d in docks]

    bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                    medianprops=dict(color='#222', lw=2),
                    whiskerprops=dict(color='#666'),
                    capprops=dict(color='#666'),
                    flierprops=dict(marker='o', markersize=5,
                                   markerfacecolor='#999', alpha=0.7))
    for patch, c in zip(bp['boxes'], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.7)

    for i, (d, vals) in enumerate(zip(docks, data)):
        jitter = np.random.default_rng(42).normal(0, 0.04, len(vals))
        ax.scatter(np.full_like(vals, i + 1) + jitter, vals,
                   color=dock_color(d), edgecolor='white', s=25,
                   linewidths=0.5, zorder=5, alpha=0.8)

    ax.set_xticklabels(docks)
    ax.set_ylabel('Duration (s)')
    ax.set_title('Docking Duration per Station (successful docks)')

    fig.tight_layout()
    return save(fig, 'fig3_duration_boxplot', out_dir)


# ── Fig 4: Angular repeatability ─────────────────────────────

def fig_angular_repeatability(ok_df, out_dir):
    """
    Per-dock angular error with systematic offset removed.
    Shows the angular SCATTER (repeatability), not the raw offset.
    Also shows raw values as faded markers for context.
    """
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    docks = [d for d in DOCK_ORDER if d in ok_df['dock_id'].unique()]

    # Left panel: raw angular error
    ax = axes[0]
    for i, did in enumerate(docks):
        vals = ok_df[ok_df['dock_id'] == did]['ang_error_deg'].dropna()
        jitter = np.random.default_rng(42).normal(0, 0.06, len(vals))
        ax.scatter(np.full(len(vals), i) + jitter, vals,
                   color=dock_color(did), edgecolor='white',
                   s=35, linewidths=0.5, alpha=0.8, zorder=3)
        ax.errorbar(i, vals.mean(), yerr=vals.std(), fmt='D',
                    color='#222', markersize=6, capsize=5, zorder=4)

    ax.set_xticks(range(len(docks)))
    ax.set_xticklabels(docks, rotation=0)
    ax.set_ylabel('Angular Error (°)')
    ax.set_title('Raw Angular Error (TF yaw − approach_yaw)')
    ax.axhline(0, color='#999', ls='-', lw=0.5)

    # Right panel: offset-corrected (per-dock mean subtracted)
    ax = axes[1]
    for i, did in enumerate(docks):
        vals = ok_df[ok_df['dock_id'] == did]['ang_error_deg'].dropna()
        centered = vals - vals.mean()
        jitter = np.random.default_rng(42).normal(0, 0.06, len(vals))
        ax.scatter(np.full(len(vals), i) + jitter, centered,
                   color=dock_color(did), edgecolor='white',
                   s=35, linewidths=0.5, alpha=0.8, zorder=3)
        ax.errorbar(i, 0, yerr=vals.std(), fmt='D',
                    color='#222', markersize=6, capsize=5, zorder=4)
        # Label std
        ax.text(i + 0.25, vals.std() + 0.5,
                f'σ={vals.std():.1f}°', fontsize=8, color='#555')

    ax.set_xticks(range(len(docks)))
    ax.set_xticklabels(docks, rotation=0)
    ax.set_ylabel('Angular Scatter (°)')
    ax.set_title('Angular Repeatability (offset-corrected)')
    ax.axhline(0, color='#999', ls='-', lw=0.5)

    fig.tight_layout()
    return save(fig, 'fig4_angular_repeatability', out_dir)


# ── Fig 5: Multi-dock mission timeline ───────────────────────

def fig_mission_timeline(df, out_dir):
    """
    Stacked horizontal bar: per-step duration for each test_full_ap run.
    Each step colored by dock_id. Failed steps marked with hatching.
    """
    tfap = df[df['mission_name'] == 'test_full_ap'].copy()
    missions = sorted(tfap['_source_file'].unique())

    fig, ax = plt.subplots(figsize=(9, max(3, len(missions) * 0.7 + 1)))

    for mi, mfile in enumerate(missions):
        grp = tfap[tfap['_source_file'] == mfile].sort_values('timestamp')
        cum = 0
        for _, row in grp.iterrows():
            color = dock_color(row['dock_id'])
            alpha = 0.9 if row['result'] == 'SUCCESS' else 0.4
            hatch = '///' if row['result'] == 'FAIL' else None
            w = row['duration_sec']
            label_text = row['dock_id']
            if row['action'] == 'undock':
                color = '#BDBDBD'
                label_text = 'undock'
            ax.barh(mi, w, left=cum, color=color, alpha=alpha,
                    edgecolor='white', linewidth=0.5, height=0.5,
                    hatch=hatch)
            if w > 15:
                ax.text(cum + w / 2, mi, f'{label_text}\n{w:.0f}s',
                        ha='center', va='center', fontsize=7, color='#222')
            cum += w

        # Mission label
        run_label = f'Run {mi + 1}'
        all_docks = grp[grp['action'] == 'dock']
        n_ok = (all_docks['result'] == 'SUCCESS').sum()
        n_total = len(all_docks)
        status = 'PASS' if (n_total == 4 and n_ok == 4) else 'FAIL'
        ax.text(-5, mi, f'{run_label} ({status})', ha='right', va='center',
                fontsize=8, fontweight='bold',
                color='#43A047' if status == 'PASS' else '#E53935')

    ax.set_yticks([])
    ax.set_xlabel('Duration (s)')
    ax.set_title('Multi-Dock Mission Timeline (test_full_ap)')
    ax.invert_yaxis()

    fig.tight_layout()
    return save(fig, 'fig5_mission_timeline', out_dir)


# ── Fig 6: Failure breakdown ─────────────────────────────────

def fig_failure_breakdown(dock_df, out_dir):
    """Horizontal bar: failure counts by error code and dock station."""
    fails = dock_df[dock_df['result'] == 'FAIL'].copy()

    if len(fails) == 0:
        print('  (no failures — skipping fig6)')
        return None

    fails['error_code'] = fails['error_code'].fillna('UNKNOWN')

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # Left: by error code
    ax = axes[0]
    ec_counts = fails['error_code'].value_counts().sort_values()
    colors_ec = ['#EF5350' if '903' in str(e) else
                 '#FF7043' if '904' in str(e) else
                 '#FFA726' if '905' in str(e) else '#BDBDBD'
                 for e in ec_counts.index]
    ec_counts.plot.barh(ax=ax, color=colors_ec, edgecolor='white')
    ax.set_xlabel('Count')
    ax.set_title('Failures by Error Code')

    # Right: by dock station
    ax = axes[1]
    dock_counts = fails['dock_id'].value_counts()
    dock_counts = dock_counts.reindex(
        [d for d in DOCK_ORDER if d in dock_counts.index])
    colors_dock = [dock_color(d) for d in dock_counts.index]
    dock_counts.plot.barh(ax=ax, color=colors_dock, edgecolor='white')
    ax.set_xlabel('Count')
    ax.set_title('Failures by Dock Station')

    fig.tight_layout()
    return save(fig, 'fig6_failure_breakdown', out_dir)


# ── Fig 7: Scatter pos_error vs duration ─────────────────────

def fig_scatter_pos_dur(ok_df, out_dir):
    """Scatter: position error vs docking duration (successful docks)."""
    fig, ax = plt.subplots(figsize=(7, 5))

    docks = [d for d in DOCK_ORDER if d in ok_df['dock_id'].unique()]
    for did in docks:
        sub = ok_df[ok_df['dock_id'] == did]
        ax.scatter(sub['duration_sec'], sub['pos_error_m'],
                   color=dock_color(did), edgecolor='white',
                   s=50, linewidths=0.5, alpha=0.8, label=did, zorder=3)

    ax.set_xlabel('Docking Duration (s)')
    ax.set_ylabel('Position Error (m)')
    ax.set_title('Position Error vs Docking Duration')
    ax.legend(loc='upper right', framealpha=0.9)

    # Correlation
    r, p = sp_stats.pearsonr(ok_df['duration_sec'].dropna(),
                              ok_df['pos_error_m'].dropna())
    ax.text(0.02, 0.98, f'r = {r:.3f} (p = {p:.3f})',
            transform=ax.transAxes, fontsize=9, va='top', color='#555')

    fig.tight_layout()
    return save(fig, 'fig7_scatter_pos_duration', out_dir)


# ── Fig 8: Block A vs Block C comparison ─────────────────────

def fig_block_comparison(dock_df, out_dir):
    """
    Grouped bar: success rate by block (A vs C) per dock station.
    Validates starting-position robustness.
    """
    ac = dock_df[dock_df['block'].isin(['A', 'C'])].copy()
    if len(ac[ac['block'] == 'C']) == 0:
        print('  (no Block C data — skipping fig8)')
        return None

    docks = [d for d in DOCK_ORDER
             if d in ac['dock_id'].unique()
             and d in ac[ac['block'] == 'A']['dock_id'].unique()
             and d in ac[ac['block'] == 'C']['dock_id'].unique()]

    if not docks:
        print('  (no overlapping docks between A and C — skipping fig8)')
        return None

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(docks))
    w = 0.35

    for bi, (block, offset) in enumerate([('A', -w/2), ('C', w/2)]):
        rates, ns = [], []
        for did in docks:
            sub = ac[(ac['block'] == block) & (ac['dock_id'] == did)]
            n = len(sub)
            k = (sub['result'] == 'SUCCESS').sum()
            rates.append(k / n * 100 if n > 0 else 0)
            ns.append(n)
        color = '#1976D2' if block == 'A' else '#E64A19'
        bars = ax.bar(x + offset, rates, w, color=color, alpha=0.8,
                      edgecolor='white', label=f'Block {block}')
        for i, (bar, n) in enumerate(zip(bars, ns)):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 2,
                    f'n={n}', ha='center', fontsize=7, color='#555')

    ax.set_xticks(x)
    ax.set_xticklabels(docks)
    ax.set_ylabel('Success Rate (%)')
    ax.set_ylim(0, 120)
    ax.set_title('Block A (from Home) vs Block C (Alt. Positions)')
    ax.legend()

    fig.tight_layout()
    return save(fig, 'fig8_block_a_vs_c', out_dir)


# ═══════════════════════════════════════════════════════════════
# 4.  TABLE 3 PRINTOUT
# ═══════════════════════════════════════════════════════════════

def print_table3(dock_df, ok_df, mission_results):
    """Print aggregate results for paper Table 3."""
    n = len(dock_df)
    k = (dock_df['result'] == 'SUCCESS').sum()
    lo, hi = wilson_ci(k, n)

    print('\n' + '=' * 65)
    print('  TABLE 3 — AGGREGATE DOCKING RESULTS')
    print('=' * 65)
    print(f'  Total docking trials:          {n}')
    print(f'  Successful:                    {k}')
    print(f'  Failed:                        {n - k}')
    print(f'  Overall success rate:          {k/n:.1%}')
    print(f'  Wilson 95% CI:                 [{lo:.1%}, {hi:.1%}]')
    print()
    print(f'  Duration — median:             {ok_df["duration_sec"].median():.1f} s')
    print(f'  Duration — IQR:                [{ok_df["duration_sec"].quantile(.25):.1f}, '
          f'{ok_df["duration_sec"].quantile(.75):.1f}] s')
    print(f'  Duration — range:              [{ok_df["duration_sec"].min():.1f}, '
          f'{ok_df["duration_sec"].max():.1f}] s')
    print()
    print(f'  Pos. error — median:           {ok_df["pos_error_m"].median():.4f} m')
    print(f'  Pos. error — max:              {ok_df["pos_error_m"].max():.4f} m')
    print(f'  Pos. error — IQR:              [{ok_df["pos_error_m"].quantile(.25):.4f}, '
          f'{ok_df["pos_error_m"].quantile(.75):.4f}] m')
    print()

    # Angular repeatability (offset-corrected per-dock std)
    ang_stds = []
    for did in ok_df['dock_id'].unique():
        vals = ok_df[ok_df['dock_id'] == did]['ang_error_deg'].dropna()
        if len(vals) > 1:
            ang_stds.append(vals.std())
    if ang_stds:
        print(f'  Angular repeatability (σ):     '
              f'[{min(ang_stds):.1f}°, {max(ang_stds):.1f}°] per dock')
        print(f'  Angular repeatability (mean σ): {np.mean(ang_stds):.1f}°')
    print()

    # Mission-level
    if len(mission_results) > 0:
        n_m = len(mission_results)
        k_m = mission_results['mission_pass'].sum()
        print(f'  Multi-dock missions:           {n_m}')
        print(f'  Mission success rate:          {k_m}/{n_m} = {k_m/n_m:.0%}')
        ok_missions = mission_results[mission_results['mission_pass']]
        if len(ok_missions) > 0:
            print(f'  Mission duration — median:     '
                  f'{ok_missions["total_duration_sec"].median():.0f} s')
    print()

    # Per-dock breakdown
    print('  ── Per Dock Station ──')
    print(f'  {"Dock":12s} {"n":>4s} {"OK":>4s} {"Fail":>4s} {"Rate":>6s}  '
          f'{"Med.Dur(s)":>10s}  {"Med.Pos(m)":>10s}  {"Max.Pos(m)":>10s}')
    for did in DOCK_ORDER:
        sub = dock_df[dock_df['dock_id'] == did]
        if len(sub) == 0:
            continue
        n_d = len(sub)
        k_d = (sub['result'] == 'SUCCESS').sum()
        sub_ok = sub[sub['result'] == 'SUCCESS']
        dur = f'{sub_ok["duration_sec"].median():.1f}' if len(sub_ok) > 0 else '—'
        pos_med = f'{sub_ok["pos_error_m"].median():.4f}' if len(sub_ok) > 0 else '—'
        pos_max = f'{sub_ok["pos_error_m"].max():.4f}' if len(sub_ok) > 0 else '—'
        print(f'  {did:12s} {n_d:4d} {k_d:4d} {n_d-k_d:4d} {k_d/n_d:6.0%}  '
              f'{dur:>10s}  {pos_med:>10s}  {pos_max:>10s}')
    print('=' * 65)


# ═══════════════════════════════════════════════════════════════
# 5.  ERROR ANALYSIS PRINTOUT
# ═══════════════════════════════════════════════════════════════

def print_error_analysis(dock_df):
    fails = dock_df[dock_df['result'] == 'FAIL'].copy()
    if len(fails) == 0:
        print('\n  No failures recorded.')
        return

    print('\n' + '=' * 65)
    print('  ERROR ANALYSIS')
    print('=' * 65)

    fails['error_code'] = fails['error_code'].fillna('UNKNOWN')
    for ec in sorted(fails['error_code'].unique()):
        sub = fails[fails['error_code'] == ec]
        docks_affected = ', '.join(sorted(sub['dock_id'].unique()))
        blocks_affected = ', '.join(sorted(sub['block'].unique()))
        print(f'  {ec:35s}  count={len(sub)}  '
              f'docks=[{docks_affected}]  blocks=[{blocks_affected}]')
    print('=' * 65)


# ═══════════════════════════════════════════════════════════════
# 6.  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='NOUZEN docking analysis')
    parser.add_argument('logs_dir', help='Directory with mission_*.csv files')
    parser.add_argument('--out', default='./figures',
                        help='Output directory for figures (default: ./figures)')
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    apply_style()

    print('Loading CSVs...')
    df = load_all_csvs(args.logs_dir)
    df = assign_blocks(df)
    print(f'  {len(df)} total rows, '
          f'blocks: {df["block"].value_counts().to_dict()}')

    dock_df = df[df['action'] == 'dock'].copy()
    ok_df = dock_df[dock_df['result'] == 'SUCCESS'].copy()
    mission_res = mission_level_results(df)

    print(f'  {len(dock_df)} dock actions: '
          f'{len(ok_df)} success, {len(dock_df) - len(ok_df)} fail')

    # ── Print aggregate results ──
    print_table3(dock_df, ok_df, mission_res)
    print_error_analysis(dock_df)

    # ── Generate figures ──
    print('\nGenerating figures...')
    fig_success_rate(dock_df, args.out)
    fig_pos_error_boxplot(ok_df, args.out)
    fig_duration_boxplot(ok_df, args.out)
    fig_angular_repeatability(ok_df, args.out)
    fig_mission_timeline(df, args.out)
    fig_failure_breakdown(dock_df, args.out)
    fig_scatter_pos_dur(ok_df, args.out)
    fig_block_comparison(dock_df, args.out)

    print(f'\nDone. {len(os.listdir(args.out))} files in {args.out}/')


if __name__ == '__main__':
    main()
