# E01 atom evidence sheet (for human verification)

Generated 2026-11-26 from OpenAlex (works up to 2020, the scheduling anchor plus the frozen synonym group).
- **Columns:** for each atom, its definition, the three most-cited matching works, and the abstract sentence that contains the term.
- **Check per row:** does the work actually *study* this constraint, or only mention it (Cross-engine J07)?
- **Reviewer:** a person, not an AI agent. Mark each row [x] studied, [m] mention only, or [?] unclear.
- **Mapping status:** an atom becomes "verified" in `src/gffs/sched/atoms.py` only after this review.

## release_dates
**Definition used:** an activity cannot start before its release (ready) time  
**Synonym group (frozen):** release dates, release times, ready times

| Work | Year | Cited | Sentence with the term | Review |
|---|---|---|---|---|
| Benchmarks for basic scheduling problems (https://doi.org/10.1016/0377-2217(93)90182-m) | 1993 | 2829 | (term only in title, or no abstract) | [ ] |
| Bounds on Multiprocessing Timing Anomalies (https://doi.org/10.1137/0117039) | 1969 | 2770 | 2 / 1 Jan 2022 Cross Ref A Combinatorial 2-Approximation Algorithm for the Parallel-Machine Scheduling with Release Times and Submodular PenaltiesMathematics, Vol. | [ ] |
| Scheduling Algorithms (https://doi.org/10.1007/978-3-662-03088-2) | 1995 | 1166 | (term only in title, or no abstract) | [ ] |

## deadlines
**Definition used:** an activity must finish by its deadline  
**Synonym group (frozen):** deadlines, due dates

| Work | Year | Cited | Sentence with the term | Review |
|---|---|---|---|---|
| Scheduling Algorithms for Multiprogramming in a Hard-Real-Time Environment (https://doi.org/10.1145/321738.321743) | 1973 | 9848 | It is also shown that full processor utilization can be achieved by dynamically assigning priorities on the basis of their current deadlines. | [ ] |
| Event-Triggered Real-Time Scheduling of Stabilizing Control Tasks (https://doi.org/10.1109/tac.2007.904277) | 2007 | 5005 | This controller has for objective guaranteeing that (control unrelated) software tasks meet their deadlines and that stabilizing control tasks asymptotically stabilize the plant. | [ ] |
| Benchmarks for basic scheduling problems (https://doi.org/10.1016/0377-2217(93)90182-m) | 1993 | 2829 | (term only in title, or no abstract) | [ ] |

## resource_calendar
**Definition used:** resource capacity varies over time (reduced availability in given intervals)  
**Synonym group (frozen):** machine availability, unavailability periods, resource calendars, maintenance activities

| Work | Year | Cited | Sentence with the term | Review |
|---|---|---|---|---|
| Bounds on Multiprocessing Timing Anomalies (https://doi.org/10.1137/0117039) | 1969 | 2770 | 01n02 / 10 December 2021 Cross Ref Single-machine scheduling with machine unavailability periods and resource dependent processing timesEuropean Journal of Operational Research, Vol. | [ ] |
| Scheduling with limited machine availability (https://doi.org/10.1016/s0377-2217(98)00367-1) | 2000 | 521 | (term only in title, or no abstract) | [ ] |
| A survey of scheduling with deterministic machine availability constraints (https://doi.org/10.1016/j.cie.2009.04.014) | 2009 | 452 | (term only in title, or no abstract) | [ ] |

## time_lags
**Definition used:** generalised precedence: minimum (or maximum) time between activity starts  
**Synonym group (frozen):** time lags, generalized precedence

| Work | Year | Cited | Sentence with the term | Review |
|---|---|---|---|---|
| Resource-constrained project scheduling: Notation, classification, models, and methods (https://doi.org/10.1016/s0377-2217(98)00204-5) | 1999 | 1751 | (term only in title, or no abstract) | [ ] |
| A Review of the Empirical Evidence on Generational Differences in Work Attitudes (https://doi.org/10.1007/s10869-010-9165-6) | 2010 | 1490 | (term only in title, or no abstract) | [ ] |
| Optimal Deep Learning LSTM Model for Electric Load Forecasting using Feature Selection and (https://doi.org/10.3390/en11071636) | 2018 | 1109 | However, developing and selecting accurate time series models is a challenging task as this requires training several different models for selecting the best amongst them along with substantial feature engineering to derive informative features and finding opt | [ ] |

## multi_mode
**Definition used:** each activity can be processed in one of several modes (duration/resource trade-offs)  
**Synonym group (frozen):** multi-mode, multimode

| Work | Year | Cited | Sentence with the term | Review |
|---|---|---|---|---|
| Resource-constrained project scheduling: Notation, classification, models, and methods (https://doi.org/10.1016/s0377-2217(98)00204-5) | 1999 | 1751 | (term only in title, or no abstract) | [ ] |
| PSPLIB - A project scheduling problem library (https://doi.org/10.1016/s0377-2217(96)00170-1) | 1997 | 1479 | (term only in title, or no abstract) | [ ] |
| Characterization and Generation of a General Class of Resource-Constrained Project Schedul (https://doi.org/10.1287/mnsc.41.10.1693) | 1995 | 733 | Instances for the single- and multi-mode resource-constrained project scheduling problem are benchmarked by using the state of the art (branch and bound) procedures. | [ ] |

## nonrenewable
**Definition used:** a resource with a total budget over the project (consumed, not renewed per period)  
**Synonym group (frozen):** nonrenewable, non-renewable resources

| Work | Year | Cited | Sentence with the term | Review |
|---|---|---|---|---|
| Markov Models & Optimization (https://openalex.org/W2143706916) | 1993 | 550 | This formulation includes an enormous variety of applied problems in engineering, operations research, management science and economics as special cases; examples include queueing systems, stochastic scheduling, inventory control, resource allocation problems, | [ ] |
| A survey on the resource-constrained project scheduling problem (https://doi.org/10.1080/07408179508936773) | 1995 | 361 | Specific papers involving nonrenewable resource constraints and time/cost-based objectives are discussed in detail because they present models that are close representations of real-world problems. | [ ] |
| A review of optimization approaches for hybrid distributed energy generation systems: Off- (https://doi.org/10.1016/j.scs.2018.05.027) | 2018 | 288 | (term only in title, or no abstract) | [ ] |

## setup_times
**Definition used:** extra time needed before an activity, possibly depending on the preceding activity  
**Synonym group (frozen):** setup times, setup costs

| Work | Year | Cited | Sentence with the term | Review |
|---|---|---|---|---|
| Optimal two‐ and three‐stage production schedules with setup times included (https://doi.org/10.1002/nav.3800010110) | 1954 | 3787 | (term only in title, or no abstract) | [ ] |
| Bounds on Multiprocessing Timing Anomalies (https://doi.org/10.1137/0117039) | 1969 | 2770 | 1 / 26 February 2021 Cross Ref A heuristic algorithm for identical parallel machine scheduling: splitting jobs, sequence-dependent setup times, and limited setup operatorsFlexible Services and Manufacturing Journal, Vol. | [ ] |
| A survey of scheduling problems with setup times or costs (https://doi.org/10.1016/j.ejor.2006.06.060) | 2006 | 1547 | (term only in title, or no abstract) | [ ] |

## preemption
**Definition used:** activities may be interrupted and resumed  
**Synonym group (frozen):** preemption, preemptive

| Work | Year | Cited | Sentence with the term | Review |
|---|---|---|---|---|
| Bounds on Multiprocessing Timing Anomalies (https://doi.org/10.1137/0117039) | 1969 | 2770 | 08 / 14 September 2021 Cross Ref Timing-Anomaly Free Dynamic Scheduling of Periodic DAG Tasks with Non-Preemptive Nodes2021 IEEE 27th International Conference on Embedded and Real-Time Computing Systems and Applications (RTCSA) / 1 Aug 2021 Cross Ref Graph-Bas | [ ] |
| NP-complete scheduling problems (https://doi.org/10.1016/s0022-0000(75)80008-0) | 1975 | 1693 | (term only in title, or no abstract) | [ ] |
| α2-Adrenergic Agonists for Regional Anesthesia: A Clinical Review of Clonidine (1984 - 199 (https://doi.org/10.1097/00000542-199609000-00026) | 1996 | 1080 | (term only in title, or no abstract) | [ ] |

## multi_resource
**Definition used:** several renewable resource types at once  
**Synonym group (frozen):** multi-resource, multiple resources

| Work | Year | Cited | Sentence with the term | Review |
|---|---|---|---|---|
| The Nucleolus of a Characteristic Function Game (https://doi.org/10.1137/0117107) | 1969 | 2208 | (term only in title, or no abstract) | [ ] |
| A Comparison of Heuristic and Optimum Solutions in Resource-Constrained Project Scheduling (https://doi.org/10.1287/mnsc.21.8.944) | 1975 | 535 | Results are presented for a total of eighty-three different multi-resource problems. | [ ] |
| Multi-resource packing for cluster schedulers (https://doi.org/10.1145/2619239.2626334) | 2014 | 362 | We present Tetris, a cluster scheduler that packs, i.e., matches multi-resource task requirements with resource availabilities of machines so as to increase cluster efficiency (makespan). | [ ] |

## precedence
**Definition used:** an activity starts only after its predecessors finish  
**Synonym group (frozen):** precedence constraints, precedence relations

| Work | Year | Cited | Sentence with the term | Review |
|---|---|---|---|---|
| A survey of variants and extensions of the resource-constrained project scheduling problem (https://doi.org/10.1016/j.ejor.2009.11.005) | 2009 | 1099 | (term only in title, or no abstract) | [ ] |
| Exact Algorithms for NP-Hard Problems: A Survey (https://doi.org/10.1007/3-540-36478-1_17) | 2003 | 797 | (term only in title, or no abstract) | [ ] |
| A genetic algorithm for multiprocessor scheduling (https://doi.org/10.1109/71.265940) | 1994 | 727 | The genetic operator proposed is based on the precedence relations between the tasks in the task graph. | [ ] |

