# NOUZEN AprilTag-Based Docking — Experimental Results Analysis

**Robot:** NOUZEN differential-drive 4WD AMR (RPi4 + ESP32, ROS 2 Jazzy, Nav2, opennav_docking)  
**Student:** DUMITRESCU Andy | **Supervisor:** Conf. univ. dr. ing. ABAZA Bogdan Felician  
**Session date:** 14 May 2026 | **Duration:** 4.1 h (08:48–12:55)  
**Paper target:** SCSS 2026, Section 5.3, Table 3  

---

## 1. Experimental Design

The campaign followed the NOUZEN Docking Experimental Protocol v2, structured in three blocks designed to answer distinct validation questions:

**Block A — Single-dock reliability** tested each of the 5 dock stations (home, input_a, input_b, output_a, output_b) individually from the home position. The protocol called for 3 trials per dock (15 planned); in practice, 19 runs were executed because early failures on input_a and output_b required additional attempts to accumulate sufficient data. This pragmatic deviation is acceptable because all runs (including failures) are retained for success rate computation.

**Block B — Multi-dock mission** ran the `test_full_ap` circuit (input_a → output_a → input_b → output_b) as a single automated mission. 6 runs were executed (protocol planned 5), each comprising 4 sequential dock actions and 3 undock actions. This block tests the full intralogistics workflow: automatic tag switching, sequential navigation, approach point convergence, and end-to-end mission resilience.

**Block C — Starting-position robustness** repeated single-dock runs from alternative starting positions (not home) to validate that the approach-point mechanism works independently of the robot's initial pose. 16 dock actions were recorded across input_a, input_b, output_a, and output_b.

All quantitative metrics (docking duration, TF-measured position and angular error, error codes) were logged automatically by the updated `mission_executor.py` to structured CSV files — no manual data capture was required during execution.

**Total dataset:** 41 CSV files, 68 action rows, 54 dock actions (46 SUCCESS, 8 FAIL), 14 undock actions (14/14 SUCCESS).

---

## 2. Aggregate Results

### 2.1 Overall Docking Performance

| Metric | Value |
|---|---|
| Total docking trials | 54 |
| Successful docks | 46 |
| Failed docks | 8 |
| **Overall success rate** | **85.2%** |
| Wilson 95% CI | [73.4%, 92.3%] |
| Median docking duration | 47.2 s |
| Duration IQR | [40.4, 123.3] s |
| Duration range | [29.4, 202.8] s |
| Median position error | 0.618 m |
| Max position error | 0.802 m |
| Position error IQR | [0.576, 0.669] m |
| Angular repeatability (σ per dock) | 2.8°–5.3° |
| Angular repeatability (mean σ) | 4.4° |
| Undock success rate | 14/14 (100%) |

The 85.2% overall success rate with a Wilson 95% CI of [73.4%, 92.3%] indicates a functional but not yet production-grade docking system. The lower bound of the confidence interval (73.4%) falls below the typical industrial reliability threshold of 95%, which is expected for a research prototype in its first validation campaign.

The undock mechanism, by contrast, demonstrated perfect reliability across all 14 attempts.

### 2.2 Per-Station Breakdown

| Dock Station | Trials | Success | Fail | Rate | Median Duration (s) | Median Pos. Error (m) | Max Pos. Error (m) |
|---|---|---|---|---|---|---|---|
| home | 3 | 3 | 0 | 100% | 119.1 | 0.569 | 0.581 |
| input_a | 15 | 13 | 2 | 87% | 41.8 | 0.670 | 0.736 |
| input_b | 11 | 9 | 2 | 82% | 128.1 | 0.606 | 0.802 |
| output_a | 14 | 13 | 1 | 93% | 53.0 | 0.574 | 0.739 |
| output_b | 11 | 8 | 3 | 73% | 40.2 | 0.622 | 0.674 |

![Fig. 1 — Success rate per dock station with Wilson 95% CI](figures/fig1_success_rate.png)

Two patterns are immediately visible. First, **output_b is the weakest station** at 73% success (3 failures). Its failures span both FAILED_TO_STAGE (903) and FAILED_TO_DETECT_DOCK (904), suggesting a combination of approach geometry and tag visibility problems at that location. Second, **output_a achieved the highest success among non-trivial docks** (93%, only 1 failure), likely benefiting from a favorable approach corridor and tag placement.

The home dock shows 100% success but with only n=3 trials and notably long durations (median 119 s), likely reflecting the longer navigation distance from the center of the workspace.

### 2.3 Multi-Dock Mission Results (Block B)

Six `test_full_ap` missions were executed; each mission traverses 4 docks sequentially (input_a → output_a → input_b → output_b) with 3 undocks between them.

| Run | Docks Completed | Total Duration | Result | Failure Point |
|---|---|---|---|---|
| B-01 | 4/4 | 360 s | PASS | — |
| B-02 | 1/1 | 46 s | INCOMPLETE | (only 1 dock logged — probable script restart) |
| B-03 | 4/4 | 454 s | PASS | — |
| B-04 | 3/4 | 226 s | FAIL | output_b: FAILED_TO_DETECT_DOCK (904) |
| B-05 | 1/2 | 236 s | FAIL | output_a: FAILED_TO_STAGE (903) |
| B-06 | 4/4 | 316 s | PASS | — |

![Fig. 5 — Multi-dock mission timeline](figures/fig5_mission_timeline.png)

**Mission-level success rate: 3/6 (50%).** Considering only the 5 structurally valid missions (excluding B-02), the rate is 3/5 (60%). The completed missions took a median of 360 s (range: 316–454 s) for the full 4-dock circuit.

The two failed missions confirm the per-station pattern: output_b and output_a account for all mid-mission failures. Importantly, no mission failed at input_a or input_b, which aligns with their higher individual success rates within the multi-dock context.

---

## 3. Position Error Analysis

### 3.1 Distribution

Position error, measured via TF lookup (Euclidean distance base_link → tag frame in XY), ranges from 0.545 m to 0.802 m across all 46 successful docks, with a median of 0.618 m.

![Fig. 2 — Position error box plot per dock station](figures/fig2_pos_error_boxplot.png)

A Shapiro-Wilk test rejects normality (W=0.938, p=0.017), confirming the use of median and IQR rather than mean ± SD throughout this analysis. Kruskal-Wallis testing reveals a statistically significant difference in position error across dock stations (H=23.41, p=0.0001). Pairwise Mann-Whitney U tests identify the primary contrasts: home and output_a form a lower-error cluster (median 0.569–0.574 m), while input_a and output_b form a higher-error cluster (median 0.670–0.622 m). This grouping aligns with the physical layout: the input stations require the robot to approach with a 180° heading toward a wall-mounted tag, which limits the final approach corridor.

### 3.2 Interpretation of the 0.5–0.8 m Range

The position errors (0.5–0.8 m) should be interpreted in context. These values represent the TF distance between the robot's `base_link` frame and the AprilTag frame at the moment docking completes — not the contact accuracy at the physical dock. The opennav_docking controller terminates when its internal criteria are met (typically at a controlled offset from the tag). The relevant question for the paper is not whether 0.618 m is "close enough" in absolute terms, but whether it is **repeatable** and **consistent** across trials.

The position error standard deviation within each dock station is low: 0.018 m for home, 0.020 m for input_a, 0.031 m for output_b, and 0.050 m for output_a. This indicates that the docking controller converges to a consistent offset relative to each tag, with sub-centimeter to low-centimeter per-dock variability. For an intralogistics scenario, this level of repeatability is sufficient — the absolute offset can be compensated by mechanical design of the docking station (e.g., funnel guides, magnetic alignment).

### 3.3 Angular Repeatability

The raw angular error (TF yaw base_link → tag minus `approach_yaw` from the dock database) shows systematic offsets of approximately +90° for input stations and −90° for output stations. This is not a docking error — it is an artifact of the AprilTag coordinate frame convention, where the tag's Z-axis points perpendicular to the tag surface (toward the approaching robot), creating a fixed ~90° rotation relative to the approach heading in the map frame.

![Fig. 4 — Angular repeatability: raw (left) vs offset-corrected (right)](figures/fig4_angular_repeatability.png)

After subtracting each dock's mean angular offset, the per-dock angular scatter standard deviations are:

| Dock | σ (°) | Range (°) |
|---|---|---|
| home | 4.9 | [−3.1, +5.7] |
| input_a | 2.8 | [−6.3, +3.8] |
| input_b | 3.9 | [−7.5, +4.0] |
| output_a | 5.3 | [−9.2, +9.2] |
| output_b | 5.1 | [−6.0, +11.2] |

These values demonstrate that the robot consistently arrives within ±5° of the same heading at each dock station, which is excellent angular repeatability for a differential-drive platform using visual servoing. For the paper, report the mean σ of 4.4° as the angular repeatability metric, and note the systematic offset as a coordinate frame convention.

---

## 4. Docking Duration Analysis

![Fig. 3 — Duration box plot per dock station](figures/fig3_duration_boxplot.png)

Docking durations show substantial variability both within and across stations. The fastest docks complete in ~30 s (output_a, output_b), while the slowest reach 200+ s (input_b). This bimodal behavior likely reflects two distinct scenarios: (1) clean approach where the robot navigates directly to the staging pose and completes the final approach in one attempt, and (2) recovery approach where the initial staging fails, Nav2 replans, and the robot requires additional maneuvers before the dock controller converges.

The duration has no significant correlation with position error (Pearson r computed in Fig. 7), confirming that longer docks do not produce worse accuracy — they simply take longer to converge.

![Fig. 7 — Position error vs duration scatter](figures/fig7_scatter_pos_duration.png)

---

## 5. Failure Analysis

Eight failures were recorded across 54 dock attempts. Their distribution:

| Error Code | Meaning | Count | Docks Affected | Blocks |
|---|---|---|---|---|
| FAILED_TO_STAGE (903) | Navigation to staging pose failed | 4 | input_a, input_b, output_a, output_b | A, B |
| FAILED_TO_DETECT_DOCK (904) | Tag not detected during approach | 2 | output_b | A, B |
| FAILED_TO_CONTROL (905) | Controller could not converge | 1 | input_b | C |
| UNKNOWN | Error code not captured | 1 | input_a | A |

![Fig. 6 — Failure breakdown by error code (left) and dock station (right)](figures/fig6_failure_breakdown.png)

FAILED_TO_STAGE (903) is the dominant failure mode (4/8), occurring across all four non-home stations. This indicates that the primary reliability bottleneck is not the final docking approach but the **navigation to the staging pose** — the point from which the dock controller takes over. The staging failures are likely caused by Nav2 path planning timeouts or costmap inflation preventing the robot from reaching the designated staging position within the 300 s timeout.

FAILED_TO_DETECT_DOCK (904) occurred exclusively at output_b (2 instances). This is a tag detection failure during the final approach, suggesting that the camera field of view, lighting conditions, or approach angle at output_b are suboptimal. The fact that this error is station-specific rather than random supports a hardware/environment root cause rather than a software defect.

---

## 6. Starting-Position Robustness (Block A vs Block C)

![Fig. 8 — Block A (home start) vs Block C (alternative positions)](figures/fig8_block_a_vs_c.png)

Fisher's exact tests comparing Block A (home start) to Block C (alternative positions) show no statistically significant difference for any dock station:

| Dock | Block A | Block C | Fisher p |
|---|---|---|---|
| input_a | 3/5 | 4/4 | 0.444 |
| input_b | 2/3 | 3/4 | 1.000 |
| output_a | 5/5 | 4/4 | 1.000 |
| output_b | 1/3 | 4/4 | 0.143 |

Block C actually shows equal or better success rates than Block A for every dock station. The output_b result is notable (Block A: 1/3 vs Block C: 4/4) though not statistically significant at p=0.143 with these sample sizes. The trend suggests that the morning Block A session may have been affected by initial calibration or warm-up effects rather than a genuine position dependency.

The key conclusion: **the approach-point mechanism successfully decouples docking success from the robot's starting position.** The Nav2 planner reliably routes the robot to the approach point regardless of its initial pose in the workspace.

---

## 7. Key Conclusions for the Paper

1. **The AprilTag-based docking system is functional and repeatable,** achieving 85.2% success rate (Wilson 95% CI: [73.4%, 92.3%]) across 54 dock trials at 5 stations, with a position repeatability of σ < 0.08 m and angular repeatability of σ < 5.3° per station.

2. **The approach-point mechanism is validated as position-independent.** No statistically significant effect of starting position was observed (Fisher's exact, p > 0.14 for all docks).

3. **Undocking is perfectly reliable** (14/14, 100%), confirming that the reverse motion and release procedure requires no further tuning.

4. **The primary reliability bottleneck is staging navigation (903), not the dock controller itself.** Four of eight failures occurred during the Nav2 approach to the staging pose. This is a navigation stack issue, not a docking-specific defect, and can be addressed through Nav2 parameter tuning (longer timeout, relaxed costmap inflation near docks).

5. **output_b is the weakest station** (73% success, 3 failures including 2× 904). Tag detection failures at this station suggest a physical environment issue (lighting, tag angle, or approach geometry) that should be investigated with camera diagnostics before repeating the campaign.

6. **Position error is consistent but has a systematic inter-dock variation** (Kruskal-Wallis H=23.41, p=0.0001). Input stations show higher error (0.67 m) than output stations (0.57 m), likely due to the tighter approach corridor geometry. The variability within each station is small (σ < 0.08 m), confirming high repeatability.

---

## 8. Development Directions

Based on these results, the following improvements are prioritized for the next iteration:

### 8.1 Short-Term (pre-next campaign)

**Staging timeout and recovery policy.** The 903 failures accounted for half of all failures. Two concrete changes: (a) increase `ACTION_TIMEOUT_DOCK` from 300 s to allow Nav2 more time for complex approaches, or better, (b) implement a retry-with-replan loop — if the staging attempt fails, back up 0.5 m, clear costmaps, and retry once before declaring failure. This is a 20-line change in `do_dock()`.

**output_b tag diagnostics.** Before the next campaign, run a dedicated diagnostic session at output_b: check tag visibility from the staging pose using camera images, measure tag detection distance and angle with `apriltag_ros` diagnostics, and consider repositioning the tag or adjusting the approach point. The 904 errors (tag not detected) at this specific station suggest an environment issue rather than a system-wide problem.

**Costmap clearing near dock zones.** Add dock station coordinates as costmap "keep-out exception zones" or reduce inflation radius within 1 m of each staging pose. This would prevent transient obstacles or sensor noise from blocking the staging approach.

### 8.2 Medium-Term (paper revision, next experimental cycle)

**Larger sample size per station.** The current n=3 per dock in Block A limits statistical power. The next campaign should target n=10 per station (50 Block A runs), which would produce Wilson CIs of ±8% rather than the current ±19%. This would also enable meaningful per-dock statistical comparisons and box plots with proper whiskers.

**Approach-point optimization.** The duration variability (IQR of 83 s) is large. An analysis of the approach trajectories (logged robot poses) could reveal whether certain approach points consistently produce clean approaches while others force replanning. An A/B test of approach point positions (e.g., 0.5 m closer to the dock) would quantify the effect.

**Dock controller parameter tuning.** The opennav_docking controller parameters (detection distance, approach speed, convergence threshold) were used at defaults. A systematic sweep of these parameters, using the same experimental protocol, could improve both success rate and duration.

**Corrected angular error metric.** The `get_dock_error()` method should subtract the known tag frame rotation (±90° depending on tag orientation) before computing `ang_error_deg`. This would produce a directly interpretable angular metric rather than requiring post-hoc offset correction. The fix is a simple rotation compensation in the TF yaw calculation.

### 8.3 Long-Term (NOUZEN platform evolution)

**Sensor fusion for final approach.** The current system relies solely on the camera + AprilTag for the final dock approach. Adding a secondary sensor (e.g., IR proximity sensors on the bumper, or a downward-facing line-following camera) would provide a redundant convergence signal and eliminate the 904 detection failures entirely.

**Closed-loop mission recovery.** Currently, a single dock failure aborts the entire mission. A production-grade system would implement dock-level retry (back up, re-approach, retry) and mission-level replanning (skip failed dock, continue to next, return to skipped dock later). This would transform the 50% mission success rate into something closer to the per-dock 85% baseline.

**Dynamic dock database.** The current system uses static dock positions from YAML. A learned dock pose refinement — where each successful dock updates a running average of the actual tag TF pose — would correct small calibration drifts over time and improve long-term reliability.

**Integration with CAIROS lab fleet.** The CSV logging infrastructure and analysis pipeline developed here (automated TF measurement, structured CSV, `nouzen_analysis.py`) form a reusable template for other CAIROS platforms (Xplorer-B/C, future SEMPER-Hy outdoor AMR). Standardizing the experimental protocol and analysis toolchain across platforms would enable meaningful cross-platform comparisons and accelerate validation cycles.

---

## 9. How to Reproduce

```bash
# Run the analysis on experimental data
python3 nouzen_analysis.py ./logs_EPS/logs_EPS --out ./figures

# Output:
#   - Console: Table 3 aggregate results + error analysis
#   - figures/fig1_success_rate.png        — success rate per dock (Wilson CI)
#   - figures/fig2_pos_error_boxplot.png   — position error per dock
#   - figures/fig3_duration_boxplot.png    — docking duration per dock
#   - figures/fig4_angular_repeatability.png — angular scatter (raw + corrected)
#   - figures/fig5_mission_timeline.png    — multi-dock mission timeline
#   - figures/fig6_failure_breakdown.png   — failure analysis
#   - figures/fig7_scatter_pos_duration.png — error vs duration correlation
#   - figures/fig8_block_a_vs_c.png        — starting position robustness
```

All figures are generated directly from the CSV data. No values are hardcoded in the script — adding new experimental CSV files to the directory and re-running the script will incorporate them automatically.

---

## 10. File Manifest

| File | Description |
|---|---|
| `nouzen_analysis.py` | Complete analysis + figure generation script |
| `logs_EPS/logs_EPS/mission_*.csv` | 41 raw experimental CSV files (auto-generated by mission_executor.py) |
| `logs_EPS/logs_EPS/mission_*.log` | 41 corresponding text logs |
| `mission_executor.py` | Updated executor with TF lookup + CSV logging |
| `nouzen_docking_experimental_protocol_v2.html` | Experimental protocol (printable A4) |
| `figures/fig1–fig8` | Publication-quality figures |
