# Literature Review: 2020-2026

## Scope and method

This review covers primary papers most relevant to Labyrinth Breach: learned
pursuit-evasion, curriculum learning, partial observability, MARL evaluation,
credit assignment, and pursuit-evasion benchmarks. Full PDFs were downloaded
and read for the thirteen papers marked **full review**. The 2026 MA2MB article is
listed separately because only the publisher abstract was accessible at review
time.

The search window was January 2020 through July 2026. Candidate work was located
through IEEE, PMLR, NeurIPS, AAAI, OpenReview, publisher pages, and author-hosted
or arXiv copies, using combinations of `multi-agent pursuit evasion`, `MARL
evaluation`, `pursuit curriculum`, `sensor constrained pursuit`, `visibility
pursuit`, and `credit assignment`. Papers were retained when they contributed
an implemented learning method, benchmark, evaluation protocol, or physical
demonstration directly relevant to at least one design decision in this project.
For each full paper, the extraction recorded task/team structure, observation
assumptions, algorithm, seed count, evaluation budget, ablations, held-out test
design, and hardware evidence. This is a targeted critical review, not a
systematic review or bibliometric claim about the whole field.

Primary publication records were rechecked on July 16, 2026. This verification
confirmed the 2025 ViPER and EPG proceedings, the ICLR 2026 R2PS acceptance, the
2026 AAAI Symposium paper (vol. 8, no. 1, pp. 2-10), and the 2026 MA2MB journal
record (vol. 203, article 105530). It also corrected the MACA proceedings pages
to 2971-2979.

## Critical synthesis

| Paper | Evidence actually reported | Relevance to Labyrinth Breach | Required response in our study |
|---|---|---|---|
| De Souza Jr. et al., *Decentralized Multi-Agent Pursuit using Deep Reinforcement Learning*, RA-L 2021 (**full review**, first posted 2020) | Decentralized non-holonomic pursuit; curriculum and formation-reward ablations; three training runs; scaling tests; direct transfer to three drones. Curriculum reached about 100% capture after 1.5M steps while no-curriculum remained below 80% after 4M in the reported comparison. | Closest support for our curriculum and anti-clustering hypotheses. Their open arena is simpler, but their ablation and hardware evidence are stronger. | Pair curriculum/direct-dynamic runs by seed, match total environment steps, quantify Sentinel spread and capture time, and avoid claiming robotics validation without hardware. |
| Grupen et al., *Multi-Agent Curricula and Emergent Implicit Signaling*, 2021 (**full review**) | Three pursuers; environment and behavioral curricula; five random seeds; 50,000 epochs of 500 trajectories; capture and information-theoretic influence analysis. | Shows that curriculum claims should connect to coordination evidence, not only final return. | Report policy-seed variation, pincer/spread metrics, and a curriculum ablation. Do not call coordination “communication” without an information measure. |
| Yu et al., *The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games*, NeurIPS 2022 (**full review**) | MAPPO/IPPO across MPE, SMAC, Google Football, and Hanabi; typically 3-10 seeds depending on testbed; extensive ablations of epochs, clipping, value normalization, batch size, death masking, and centralized inputs. | Justifies PPO as a serious baseline but also shows that implementation details materially affect conclusions. | Preserve exact trainer configs, add a centralized-credit baseline where compute permits, and report multiple policy seeds rather than one reward trace. |
| Gorsane et al., *Towards a Standardised Performance Evaluation Protocol for Cooperative MARL*, NeurIPS 2022 (**full review**) | Meta-analysis of 75 papers; identifies inconsistent environments, budgets, seeds, uncertainty, and ablations; proposes independent runs, fixed evaluation episodes, per-task metrics, uncertainty, robust aggregates, and reproducible settings. Their default protocol recommends 10 independent runs and 32 evaluation episodes per interval. | Direct basis for our strict artifact and statistical protocol. Three seeds are a minimum project compromise, not the field’s strongest standard. | Use independent policy seeds as the replicate; fixed episode counts rather than wall-clock windows; per-layout tables; hierarchical uncertainty; artifact and missing-run audits. |
| Sun et al., *MatrixWorld*, 2023 (**full review**) | Safety-constrained grid pursuit-evasion; explicit collision responsibility/resolution; co-evolution algorithms; 30 generations with 400 training epochs per side; multiple asymmetric team configurations. | Closest benchmark comparison. MatrixWorld is lightweight and safety-centered; Labyrinth Breach is continuous, Unity-based, partially observed, and dynamically topological. | Add collision and wall-transition safety metrics; compare benchmark features honestly; do not imply superiority without running common algorithms. |
| Kouzeghar et al., *Multi-Target Pursuit by a Decentralized Heterogeneous UAV Swarm*, ICRA 2023 (**full review**) | Role-based MADDPG with pursuer and Voronoi-rewarded scout roles; 5 pursuers against 2 faster targets in simulation and a 6-Crazyflie demonstration. The hardware section reports a 0.4983 m average pursuer-target distance from one displayed trajectory, but no independent-seed count, fixed evaluation budget, or component ablation is reported. | Demonstrates that heterogeneous pursuit/exploration roles can transfer to hardware, while also showing why qualitative trajectories alone are insufficient evidence. | Keep role and spread metrics, but require independent seeds and fixed-count trials. Do not treat a single qualitative trajectory as statistical validation. |
| Chen et al., *A Dual Curriculum Learning Framework for Multi-UAV Pursuit-Evasion*, 2023 (**full review**) | DualCL combines an intrinsic-parameter curriculum with an external environment generator; six test scenarios, including two out-of-distribution scenes; three seeds and 3,000 testing episodes per reported score; component ablations; Crazyflie execution using motion-capture state and a virtual evader. | Closest curriculum and unseen-environment comparator. It trains across task distributions and evaluates much more heavily than the original Labyrinth report. | Retain the matched curriculum/direct-training ablation, increase topology diversity when compute permits, and distinguish executable hardware transfer from closed-loop physical evader validation. |
| Zheng et al., *Faster Target Encirclement with Utilization of Obstacles*, ACML 2023 / PMLR 2024 (**full review**) | MADDPG encirclement with obstacle contribution angles and a two-stage strategy; 200,000 training episodes, five seeds, and 200 evaluation rounds per seed (1,000 per configuration); systematic target-speed, team-size, obstacle-count, and three-component ablations. | Direct evidence that obstacles can become tactical resources and that event rewards can alter coalition behavior. Its encirclement objective and scripted target differ from our learned two-team exit game. | Report trap use, corridor blocking, spread, and capture efficiency together; the trap-reward ablation must test whether walls improve outcomes or merely inflate shaped return. |
| Gonultas and Isler, *Learning to Play Pursuit-Evasion with Dynamic and Sensor Constraints*, 2024 (**full review**) | 1v1 zero-sum POSG with car-like dynamics; recurrent mixture-density belief model; curriculum over sensor coverage and evader speed; three trained models and 500 episodes each for reported comparisons; optimal-control and learned baselines; F1TENTH/JetRacer deployment. | Strongest reference for partial observability and dynamics-aware robotics validation. Their learned belief model is substantially richer than our last-known-position vector. | Compare memory-on/off and eventually LSTM memory; state clearly that our kinematics and sensing are simplified; avoid hardware-level claims. |
| Wang et al., *ViPER*, CoRL/PMLR 2025 (**full review**) | SAC with graph attention and privileged critic; 4,000 training maps and 100 held-out maps; 30 random starts per comparison map; team-size, map-complexity, known/unknown-map, failure, and architecture ablations; three Crazyflie drones plus TurtleBot demonstration. | Sets a high bar for held-out topology testing and coordination analysis. Its visibility-clearing task differs from learned 3v2 capture/escape. | Expand beyond five held-out seeds if compute permits, use fixed trials per map, add qualitative coordination sequences, and present simulation-only scope as a limitation. |
| Lu et al., *Equilibrium Policy Generalization*, NeurIPS 2025 (**full review**) | Cross-graph GNN policies trained on 76 Dungeon maps discretized at two scales (152 graphs); 10 real-world and 10 unseen Dungeon test graphs; 500 trials per graph with a 128-step cap; equilibrium-guidance, SAC-loss, and distance-feature ablations. No independent training-seed count is stated in the paper. | Provides the clearest standard for a defensible cross-topology zero-shot claim and an actual game-theoretic oracle. Its graph game is discrete and generally fully observed, unlike our continuous POSG. | Use "held-out topology transfer" rather than equilibrium or robust zero-shot language; report per-topology results and do not infer Nash behavior from PPO. |
| Lu et al., *R2PS*, ICLR 2026 (**full review**) | Two pursuers against an optimal asynchronous evader under observation range 2; 300 training graphs, 100,000 training episodes, 10 unseen real-world test graphs, and 500 tests per graph; belief-update frequency, observation-range, scalability, and adversarial-opponent analyses. Independent training-seed counts are not stated. | Strongest recent partial-observability/cross-graph comparator. Its explicit belief set is much stronger than our last-known-position memory. | Treat memory-off as only a first ablation; add recurrent or belief-state memory as a future baseline and avoid worst-case robustness claims without adversarial best-response evaluation. |
| Akinmolayan et al., *Adaptive Interception in Dynamic Domains*, AAAI SSS 2026 (**full review**) | Hybrid classical-intercept/PPO controller; curriculum and action blending; 100 single-agent evaluation episodes; 94% versus 24% capture in a comparison where controller speeds differ; multi-agent self-play extension. | Directly relevant to our action-assist blending. It also illustrates why hybrid-controller comparisons must control dynamics and disclose the blend. | Treat action assist as a hybrid controller, disclose its coefficient (Sentinel 0.15 in the active rule config), and require assist-off evaluation before attributing behavior to the policy. |

## Additional recent work

- Kapoor et al., *Assigning Credit with Partial Reward Decoupling in Multi-Agent
  Proximal Policy Optimization*, RLC 2024: attention-based partial reward
  decoupling improves MAPPO credit assignment. It motivates a centralized or
  learned-credit baseline; our event rewards are not an equivalent method.
- Zhao and Xie, *Multi-level Advantage Credit Assignment for Cooperative MARL*,
  AISTATS 2025: reasons over individual, joint, and correlated agent subsets.
  This is especially relevant because pincer and corridor events involve
  different coalition sizes.
- Zhao et al., *MA2MB: Multi-agent Mutual-Advising Model-Based Reinforcement
  Learning for Pursuit and Evasion Games*, Robotics and Autonomous Systems 2026:
  the publisher abstract describes adversary uncertainty, mutual advising in a
  learned world model, and collaborative adversarial SAC. The full article was
  not accessible, so no detailed empirical comparison is made here.

## Research gap after reading

Labyrinth Breach should not be positioned as a new MARL algorithm. Its strongest
defensible contribution is a configurable and auditable Unity benchmark for a
combination not covered cleanly by the closest papers: two learned asymmetric
teams, continuous planar actions, exit-directed evasion, partial observation,
within-episode topology changes, and event-level reward provenance.

The benchmark contribution becomes publishable only if the empirical study
demonstrates what each configurable mechanism changes. At minimum, that means:

1. Three independently trained curriculum policies, with five preferred.
2. Fixed-count evaluation on one seen and at least five held-out layouts.
3. Memory, tactical-reward, dynamic-wall, curriculum, and action-assist ablations.
4. Per-seed learning curves, paired effect sizes, confidence intervals, and raw
   episode tables.
5. At least one stronger MARL baseline or a clearly scoped statement that the
   article contributes a benchmark rather than an algorithm.
6. A recurrent or explicit-belief memory baseline if partial-observability
   improvement becomes a headline claim.
7. Collision/wall-transition safety auditing and explicit simulation-only limits.

## Evidence gap relative to the strongest comparators

The upgraded protocol is substantially stronger than the original course
report, but it remains below the largest recent studies. Gorsane et al. recommend
ten independent runs by default; this project uses three because each policy
requires a four-stage two-role curriculum. ViPER evaluates 100 held-out maps
with 30 starts per comparison map; this project initially reserves five held-out
topologies with 100 episodes per policy-topology cell. Gonultas and Isler and De
Souza Jr. et al. include physical robots; this project remains Unity-only. EPG
uses 152 training graphs and two 10-graph held-out suites, while R2PS uses 300
training graphs and 10 unseen real-world graphs. Five held-out topologies are
therefore a minimum controlled test, not evidence of broad layout invariance.
These are not citation formalities: they determine the defensible venue and claim
scope. A simulation benchmark or workshop/preprint path is credible after the
registered matrix is complete, whereas a hardware-robotics claim is not.

## Primary sources

- [De Souza Jr. et al.](https://arxiv.org/abs/2010.08193)
- [Grupen et al.](https://arxiv.org/abs/2106.11156)
- [Yu et al.](https://papers.neurips.cc/paper_files/paper/2022/hash/9c1535a02f0ce079433344e14d910597-Abstract-Datasets_and_Benchmarks.html)
- [Gorsane et al.](https://proceedings.neurips.cc/paper_files/paper/2022/hash/249f73e01f0a2bb6c8d971b565f159a7-Abstract-Conference.html)
- [MatrixWorld](https://arxiv.org/abs/2307.14854)
- [Kouzeghar et al.](https://arxiv.org/abs/2303.01799)
- [DualCL](https://arxiv.org/abs/2312.12255)
- [Zheng et al.](https://proceedings.mlr.press/v222/zheng24b.html)
- [Gonultas and Isler](https://arxiv.org/abs/2405.05372)
- [ViPER](https://proceedings.mlr.press/v270/wang25k.html)
- [EPG](https://papers.nips.cc/paper_files/paper/2025/hash/45a30141c6719e9cfedfb51f1c665a37-Abstract-Conference.html)
- [R2PS](https://arxiv.org/abs/2511.17367)
- [Akinmolayan et al.](https://ojs.aaai.org/index.php/AAAI-SS/article/view/42510)
- [Kapoor et al.](https://openreview.net/forum?id=nfSlBFKFmq)
- [Zhao and Xie](https://proceedings.mlr.press/v258/zhao25c.html)
- [MA2MB](https://doi.org/10.1016/j.robot.2026.105530)
