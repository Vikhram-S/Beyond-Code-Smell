# Beyond Code Smell: Measuring Architectural Conformance Drift in Long-Horizon Autonomous Coding Agent Sessions

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)

Official artifact repository and evaluation harness for the paper **"Beyond Code Smell: Measuring Architectural Conformance Drift in Long-Horizon Autonomous Coding Agent Sessions"**.

---

## 📌 Abstract

Autonomous coding agents increasingly execute multi-session, long-horizon software engineering tasks across multi-file codebases. While existing benchmarks measure localized code-quality erosion (e.g., SlopCodeBench), none evaluate whether agents preserve higher-level architectural models, module boundaries, and layering constraints over extended horizons.

In this study, we introduce an automated, fault-tolerant measurement instrument that extracts static dependency graphs $G=(V,E)$ and evaluates explicit architectural fitness functions. We formalize four quantitative drift metrics:
- **DGED**: Dependency Graph Edit Distance
- **LVC**: Layering Violation Count
- **CDR**: Conformance Decay Rate
- **CNLV**: Complexity-Normalized Layering Violation

Using a matched-pair design across open-source Python repositories ($N_1 = N_2 = 54$ matched observations), we compare autonomous agent session trajectories against historical human contributions satisfying scope, intent, and locality criteria.

---

## 📊 Key Empirical Findings

| Metric / Analysis | Result | Statistical Significance |
| :--- | :--- | :--- |
| **Mann–Whitney U Test** | $U = 2189.5$, $p = 1.19 \times 10^{-6}$ | **Statistically Significant** ($p < 0.001$) |
| **Rank-Biserial Effect Size** | $r_{\mathrm{rb}} = -0.502$ | **Large Effect Size** ($|r| \ge 0.50$) |
| **Agent vs. Human Median CNLV** | Agent $= 0.0952$ vs. Human $= 0.0000$ | Substantially higher drift in agent sessions |
| **Linear Mixed-Effects (LMM)** | $\beta_{\mathrm{session}} = 0.0144$ ($p = 0.3581$) | Drift introduces early at session 1 and stabilizes |
| **Downstream Task Failure** | Spearman $r_s = 0.400$ ($p = 2.70 \times 10^{-3}$) | Moderate-to-strong positive risk correlation |

---

## 📂 Repository Structure

```text
.
├── config.yaml                    # Configuration (repositories, model, budget cap)
├── pytest.ini                     # Pytest suite configuration
├── requirements.txt               # Project dependencies
├── LICENSE                        # MIT License
├── README.md                      # Repository documentation
├── paper/
│   ├── preprint.tex               # Full LaTeX manuscript source
│   ├── fig1_architecture.png      # Fig 1: Harness Architecture
│   ├── fig2_conformance_decay.png # Fig 2: Decay Trajectory Plot
│   ├── fig3_violin_comparison.png # Fig 3: Split-Violin Domain Distribution
│   └── fig5_correlation_plot.png  # Fig 5: Correlation with Downstream Risk
├── results/
│   ├── real_mined_dataset.csv     # Raw mined evaluation dataset
│   ├── descriptive_stats.csv      # Stratified descriptive statistics
│   ├── inferential_stats.csv      # Statistical test outcomes (U, LMM, Logit)
│   └── statistical_summary_report.md # Full empirical summary report
├── src/
│   ├── utils/                     # Logging & resilient execution helpers
│   ├── metrics/                   # Drift metric formulas (DGED, LVC, CDR, CNLV)
│   ├── cost_tracker/              # Disk-cached LLM tracker & budget enforcer
│   ├── repo_miner/                # Import graph extraction via grimp
│   ├── task_runner/               # Provider-agnostic session orchestrator
│   ├── checkpoint_store/          # Idempotent state persistence
│   ├── human_baseline/            # Matched human commit extractor
│   └── pipeline.py                # Main CLI entrypoint
├── tests/                         # Unit tests verifying metric correctness
└── docs/                          # Detailed specification documents
    ├── phase1_repo_and_task_corpus_design.md
    ├── phase2_metrics_and_extraction_spec.md
    └── dry_run_output.md
```

---

## ⚡ Quickstart & Reproducibility

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/Vikhram-S/Beyond-Code-Smell.git
cd Beyond-Code-Smell

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Test Suite
Verify metric formula correctness and statistical diagnostics:
```bash
pytest
```

### 3. $0.00 Cost Dry-Run Pipeline Verification
Validate the full evaluation pipeline, metric calculation, and graph extraction at **zero API cost** using the mock LLM adapter:
```bash
python -m src.pipeline --dry-run
```

### 4. Empirical Evaluation Run
To execute the benchmark against live LLM providers under a configurable budget cap (default: $50.00):
```bash
export ANTHROPIC_API_KEY="your-api-key"
python -m src.pipeline --config config.yaml
```

---

## 📖 Citation

If you use this benchmark, metric formulation, or dataset in your research, please cite:

```bibtex
@article{vikhram2026beyondcodesmell,
  title={Beyond Code Smell: Measuring Architectural Conformance Drift in Long-Horizon Autonomous Coding Agent Sessions},
  author={Vikhram S},
  journal={Empirical Software Engineering Preprint Under Peer Review},
  year={2026},
  url={https://github.com/Vikhram-S/Beyond-Code-Smell}
}
```

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
