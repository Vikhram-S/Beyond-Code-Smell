# Statistical Analysis Summary Report [PRELIMINARY / DRY-RUN]

**Study Title:** *Beyond Code Smell: Measuring Architectural Conformance Drift in Long-Horizon Autonomous Coding Agent Sessions*  
**Data Status:** [PRELIMINARY / DRY-RUN]  
**Dataset Scope:** Total Observations = 108 across 18 Repositories  

---

## 1. Distributional Assumption Diagnostics & Methodological Rationale

* **Shapiro-Wilk Test for Normality (CNLV):**
  * Agent Distribution: $W = 0.8541$, $p = 1.0390e-05$
  * Human Distribution: $W = 0.6304$, $p = 2.0848e-10$
* **Methodological Justification:** Data violates normality assumption (Shapiro-Wilk p < 0.05). Non-parametric Mann-Whitney U test is strictly required.

---

## 2. Descriptive Statistics (Medians & Interquartile Ranges)

| Subject | Size Tier | Domain | Metric | N | Median | IQR (Q1–Q3) | Mean ± Std |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Agent | Large | Library | CNLV | 3 | 0.2857 | 0.1096 (0.2582–0.3679) | 0.3222 ± 0.1141 |
| Agent | Large | Web | CNLV | 12 | 0.1527 | 0.2208 (0.1042–0.3250) | 0.2204 ± 0.1352 |
| Agent | Medium | Cli | CNLV | 3 | 0.1026 | 0.0577 (0.0513–0.1090) | 0.0726 ± 0.0632 |
| Agent | Medium | Library | CNLV | 9 | 0.1429 | 0.0526 (0.1316–0.1842) | 0.1755 ± 0.1175 |
| Agent | Medium | Web | CNLV | 6 | 0.1266 | 0.0830 (0.0815–0.1645) | 0.1245 ± 0.0863 |
| Agent | Small | Cli | CNLV | 9 | 0.0303 | 0.0500 (0.0000–0.0500) | 0.0331 ± 0.0402 |
| Agent | Small | Library | CNLV | 6 | 0.0139 | 0.0347 (0.0000–0.0347) | 0.0340 ± 0.0539 |
| Agent | Small | Web | CNLV | 6 | 0.0000 | 0.0188 (0.0000–0.0188) | 0.0084 ± 0.0131 |
| Human | Large | Library | CNLV | 3 | 0.0000 | 0.0238 (0.0000–0.0238) | 0.0159 ± 0.0275 |
| Human | Large | Web | CNLV | 12 | 0.0339 | 0.0476 (0.0000–0.0476) | 0.0372 ± 0.0402 |

---

## 3. Inferential Hypothesis Testing & Mixed-Effects Modeling

### A. Non-Parametric Mann-Whitney U Test (Agent vs. Human Baseline)
* **Test Statistic:** Mann-Whitney $U = 2189.5$
* **p-value:** $p = 1.1933e-06$ (Significant at $lpha = 0.05$: `True`)
* **Effect Size (Rank-Biserial Correlation $r_{rb}$):** $r_{rb} = -0.502$ (Large Effect)
* **Median Comparison:** Agent Median $\text{CNLV} = 0.0952$ vs. Human Median $\text{CNLV} = 0.0000$.

### B. Linear Mixed-Effects Trajectory Model (LMM)
* **Model Formula:** `cnlv ~ step_idx + (1 | repo_id)`
* **Fixed Effect Session Slope ($eta_{session}$):** $eta = 0.0144$ ($p = 3.5814e-01$)
* **Random Effect Repo Variance ($\sigma_{repo}^2$):** $\sigma^2 = 0.0080$
* **Interpretation:** For each sequential agent session, cnlv increases by 0.0144 units (p = 3.5814e-01, random repo variance = 0.0080).

---

## 4. Power Analysis & Minimum Detectable Effect Size (MDES)

* **Sample Sizes:** $N_{agent} = 54$, $N_{human} = 54$
* **Target Power ($1-\beta$):** 80% ($lpha = 0.05$)
* **Minimum Detectable Effect Size (Cohen's $d$):** $d_{MDES} = 0.539$
* **Power Assessment:** Sample size (N1=54, N2=54) provides 80% power to detect effect sizes d >= 0.539.

---

## 5. Practical Utility: Correlation with Downstream Test Failure

* **Spearman Rank Correlation ($r_s$):** $r_s = 0.400$ ($p = 2.6998e-03$)
* **Logistic Regression Odds Ratio:** $	ext{OR} = 20695.78$ ($p = 3.1768e-03$)
* **Key Finding:** Architectural drift (CNLV) significantly predicts downstream task test failure (Spearman r_s = 0.400, p = 2.6998e-03). Each unit increase in CNLV increases the odds of downstream test failure by 20695.78x (Odds Ratio = 20695.78).
