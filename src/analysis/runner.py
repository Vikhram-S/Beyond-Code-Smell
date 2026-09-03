import argparse
import json
import pandas as pd
from pathlib import Path
from src.utils.logger import logger
from src.analysis.synthetic_generator import SyntheticDataGenerator
from src.analysis.stats_analyzer import StatisticalAnalyzer

def run_statistical_pipeline(synthetic: bool = False, output_dir: Path = Path("results")):
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("==================================================")
    logger.info("Starting Phase 4 Statistical Analysis Engine")
    logger.info("==================================================")

    # 1. Load Dataset
    if synthetic:
        logger.info("[MODE] Generating synthetic multi-repo evaluation dataset (NOT for the paper)")
        df = SyntheticDataGenerator.generate_dataset()
        data_status_flag = "[PRELIMINARY / DRY-RUN — DO NOT USE IN THE PAPER]"
    else:
        logger.info("[MODE] Loading real empirical benchmark dataset")
        real_csv = Path("results/real_mined_dataset.csv")
        if not real_csv.exists():
            raise FileNotFoundError(
                "results/real_mined_dataset.csv is missing. Run `python -m src.pipeline` with GOOGLE_API_KEY. "
                "Refusing to invent numbers."
            )
        df = pd.read_csv(real_csv)
        if df.empty:
            raise RuntimeError("real_mined_dataset.csv is empty. Resume the pipeline; do not fabricate rows.")
        data_status_flag = "[REAL GEMINI FREE-TIER PILOT DATASET]"

    analyzer = StatisticalAnalyzer(df)

    # 2. Assumption Diagnostics
    logger.info("--- Step 1: Checking Distributional Assumptions ---")
    diagnostics = analyzer.check_assumptions(metric="cnlv")
    logger.info(f"Shapiro-Wilk Agent p-val: {diagnostics['shapiro_agent_p']:.4e}")
    logger.info(f"Shapiro-Wilk Human p-val: {diagnostics['shapiro_human_p']:.4e}")
    logger.info(f"Conclusion: {diagnostics['justification']}")

    # 3. Descriptive Statistics
    logger.info("\n--- Step 2: Computing Non-Parametric Descriptive Statistics ---")
    desc_df = analyzer.compute_descriptive_stats()
    desc_csv_path = output_dir / "descriptive_stats.csv"
    desc_df.to_csv(desc_csv_path, index=False)
    logger.info(f"Saved descriptive stats to {desc_csv_path}")

    # 4. Inferential Statistics (Mann-Whitney U)
    logger.info("\n--- Step 3: Running Mann-Whitney U Hypothesis Test ---")
    mwu_results = analyzer.run_mann_whitney_u_test(metric="cnlv")
    logger.info(
        f"Agent vs. Human CNLV: Mann-Whitney U = {mwu_results['mann_whitney_u']}, "
        f"p = {mwu_results['p_value']:.4e}, Effect Size r_rb = {mwu_results['rank_biserial_r']:.3f} ({mwu_results['effect_size_magnitude']})"
    )

    # 5. Linear Mixed-Effects Model (LMM)
    logger.info("\n--- Step 4: Fitting Linear Mixed-Effects Model (LMM) ---")
    lmm_results = analyzer.fit_mixed_effects_model(metric="cnlv")
    logger.info(f"Fixed Effect Session Slope beta = {lmm_results['fixed_effect_slope']:.4f} (p = {lmm_results['fixed_effect_pvalue']:.4e})")

    # 6. Power Analysis & MDES
    logger.info("\n--- Step 5: Statistical Power & MDES Analysis ---")
    power_results = analyzer.compute_power_analysis(
        n1=mwu_results["n_agent"],
        n2=mwu_results["n_human"]
    )
    logger.info(power_results["power_assessment"])

    # 7. Downstream Risk Correlation Analysis
    logger.info("\n--- Step 6: Downstream Practical Utility & Risk Correlation ---")
    risk_results = StatisticalAnalyzer.run_downstream_risk_analysis(analyzer)
    logger.info(risk_results["practical_hook_summary"])

    # Export Inferential Summary CSV
    inferential_rows = [
        {"analysis": "Mann-Whitney U Test", "metric": "cnlv", "stat": mwu_results["mann_whitney_u"], "p_value": mwu_results["p_value"], "effect_size_r": mwu_results["rank_biserial_r"]},
        {"analysis": "Linear MixedLM Slope", "metric": "cnlv", "stat": lmm_results["fixed_effect_slope"], "p_value": lmm_results["fixed_effect_pvalue"], "effect_size_r": "N/A"},
        {"analysis": "Downstream Risk Logit", "metric": "task_failed", "stat": risk_results["logit_cnlv_beta"], "p_value": risk_results["logit_pvalue"], "effect_size_r": f"OddsRatio={risk_results['odds_ratio']:.2f}"}
    ]
    pd.DataFrame(inferential_rows).to_csv(output_dir / "inferential_stats.csv", index=False)

    # 8. Write Markdown Summary Report
    report_md = f"""# Statistical Analysis Summary Report {data_status_flag}

**Study Title:** *Beyond Code Smell: Measuring Architectural Conformance Drift in Long-Horizon Autonomous Coding Agent Sessions*  
**Data Status:** {data_status_flag}  
**Dataset Scope:** Total Observations = {len(df)} across {df['repo_id'].nunique()} Repositories  

---

## 1. Distributional Assumption Diagnostics & Methodological Rationale

* **Shapiro-Wilk Test for Normality (CNLV):**
  * Agent Distribution: $W = {diagnostics['shapiro_agent_stat']:.4f}$, $p = {diagnostics['shapiro_agent_p']:.4e}$
  * Human Distribution: $W = {diagnostics['shapiro_human_stat']:.4f}$, $p = {diagnostics['shapiro_human_p']:.4e}$
* **Methodological Justification:** {diagnostics['justification']}

---

## 2. Descriptive Statistics (Medians & Interquartile Ranges)

| Subject | Size Tier | Domain | Metric | N | Median | IQR (Q1–Q3) | Mean ± Std |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
"""
    # Append top descriptive summary rows
    sub_desc = desc_df[desc_df["metric"] == "cnlv"].head(10)
    for _, row in sub_desc.iterrows():
        report_md += (
            f"| {row['subject'].capitalize()} | {row['repo_size'].capitalize()} | {row['repo_domain'].capitalize()} | "
            f"CNLV | {row['count']} | {row['median']:.4f} | {row['iqr']:.4f} ({row['q1']:.4f}–{row['q3']:.4f}) | "
            f"{row['mean']:.4f} ± {row['std']:.4f} |\n"
        )

    report_md += f"""
---

## 3. Inferential Hypothesis Testing & Mixed-Effects Modeling

### A. Non-Parametric Mann-Whitney U Test (Agent vs. Human Baseline)
* **Test Statistic:** Mann-Whitney $U = {mwu_results['mann_whitney_u']:.1f}$
* **p-value:** $p = {mwu_results['p_value']:.4e}$ (Significant at $\alpha = 0.05$: `{mwu_results['significant_alpha_05']}`)
* **Effect Size (Rank-Biserial Correlation $r_{{rb}}$):** $r_{{rb}} = {mwu_results['rank_biserial_r']:.3f}$ ({mwu_results['effect_size_magnitude']} Effect)
* **Median Comparison:** Agent Median $\\text{{CNLV}} = {mwu_results['median_agent']:.4f}$ vs. Human Median $\\text{{CNLV}} = {mwu_results['median_human']:.4f}$.

### B. Linear Mixed-Effects Trajectory Model (LMM)
* **Model Formula:** `cnlv ~ step_idx + (1 | repo_id)`
* **Fixed Effect Session Slope ($\beta_{{session}}$):** $\beta = {lmm_results['fixed_effect_slope']:.4f}$ ($p = {lmm_results['fixed_effect_pvalue']:.4e}$)
* **Random Effect Repo Variance ($\sigma_{{repo}}^2$):** $\sigma^2 = {lmm_results['random_effect_var']:.4f}$
* **Interpretation:** {lmm_results['interpretation']}

---

## 4. Power Analysis & Minimum Detectable Effect Size (MDES)

* **Sample Sizes:** $N_{{agent}} = {power_results['n_agent_samples']}$, $N_{{human}} = {power_results['n_human_samples']}$
* **Target Power ($1-\\beta$):** 80% ($\alpha = 0.05$)
* **Minimum Detectable Effect Size (Cohen's $d$):** $d_{{MDES}} = {power_results['mdes_cohens_d']:.3f}$
* **Power Assessment:** {power_results['power_assessment']}

---

## 5. Practical Utility: Correlation with Downstream Test Failure

* **Spearman Rank Correlation ($r_s$):** $r_s = {risk_results['spearman_rho']:.3f}$ ($p = {risk_results['spearman_pvalue']:.4e}$)
* **Logistic Regression Odds Ratio:** $\text{{OR}} = {risk_results['odds_ratio']:.2f}$ ($p = {risk_results['logit_pvalue']:.4e}$)
* **Key Finding:** {risk_results['practical_hook_summary']}
"""

    report_path = output_dir / "statistical_summary_report.md"
    report_path.write_text(report_md, encoding="utf-8")
    logger.info(f"\nSaved Markdown summary report to {report_path}")

    logger.info("==================================================")
    logger.info("Phase 4 Statistical Analysis Completed Successfully!")
    logger.info("==================================================")

    import json
    n_repos = int(df["repo_id"].nunique())
    n_agent = int((df["subject"] == "agent").sum())
    n_human = int((df["subject"] == "human").sum())
    numbers = {
        "n_repos": n_repos,
        "n_agent": n_agent,
        "n_human": n_human,
        "n_obs": int(len(df)),
        "backend": "Google Gemini API (gemini-3.6-flash, free-tier quota)",
        "shapiro_agent_p": diagnostics["shapiro_agent_p"],
        "shapiro_human_p": diagnostics["shapiro_human_p"],
        "mwu_u": mwu_results["mann_whitney_u"],
        "mwu_p": mwu_results["p_value"],
        "r_rb": mwu_results["rank_biserial_r"],
        "effect_size_magnitude": mwu_results["effect_size_magnitude"],
        "median_agent": mwu_results["median_agent"],
        "median_human": mwu_results["median_human"],
        "lmm_beta": lmm_results["fixed_effect_slope"],
        "lmm_p": lmm_results["fixed_effect_pvalue"],
        "lmm_var": lmm_results["random_effect_var"],
        "mdes_d": power_results["mdes_cohens_d"],
        "spearman_rs": risk_results["spearman_rho"],
        "spearman_p": risk_results["spearman_pvalue"],
        "odds_ratio": risk_results["odds_ratio"],
        "logit_p": risk_results["logit_pvalue"],
        "separation_detected": risk_results["separation_detected"],
        "model_type": risk_results["model_type"],
        "ci_absurdly_wide": risk_results["ci_absurdly_wide"],
        "or_lower_95": risk_results["or_lower_95"],
        "or_upper_95": risk_results["or_upper_95"],
        "risk_summary": risk_results["practical_hook_summary"],
        "power_assessment": power_results["power_assessment"],
        "lmm_interpretation": lmm_results["interpretation"],
    }
    agent_cnlv = df[df["subject"] == "agent"]["cnlv"].dropna()
    human_cnlv = df[df["subject"] == "human"]["cnlv"].dropna()
    numbers["agent_q1"] = float(agent_cnlv.quantile(0.25)) if len(agent_cnlv) else float("nan")
    numbers["agent_q3"] = float(agent_cnlv.quantile(0.75)) if len(agent_cnlv) else float("nan")
    numbers["human_q1"] = float(human_cnlv.quantile(0.25)) if len(human_cnlv) else float("nan")
    numbers["human_q3"] = float(human_cnlv.quantile(0.75)) if len(human_cnlv) else float("nan")
    numbers["shapiro_agent_w"] = diagnostics["shapiro_agent_stat"]
    numbers["shapiro_human_w"] = diagnostics["shapiro_human_stat"]
    (output_dir / "paper_numbers.json").write_text(json.dumps(numbers, indent=2, default=str), encoding="utf-8")

    def _fmt(x, spec=".4f"):
        try:
            v = float(x)
            if v != v:  # NaN
                return "NA"
            return format(v, spec)
        except (TypeError, ValueError):
            return "NA"

    macros = [
        r"\newcommand{\nRepos}{" + str(n_repos) + "}",
        r"\newcommand{\nAgent}{" + str(n_agent) + "}",
        r"\newcommand{\nHuman}{" + str(n_human) + "}",
        r"\newcommand{\mdesD}{" + _fmt(power_results["mdes_cohens_d"], ".3f") + "}",
        r"\newcommand{\mwuU}{" + _fmt(mwu_results["mann_whitney_u"], ".1f") + "}",
        r"\newcommand{\mwuP}{" + _fmt(mwu_results["p_value"], ".4e") + "}",
        r"\newcommand{\rrb}{" + _fmt(mwu_results["rank_biserial_r"], ".3f") + "}",
        r"\newcommand{\medAgent}{" + _fmt(mwu_results["median_agent"]) + "}",
        r"\newcommand{\medHuman}{" + _fmt(mwu_results["median_human"]) + "}",
        r"\newcommand{\agentQone}{" + _fmt(numbers["agent_q1"]) + "}",
        r"\newcommand{\agentQthree}{" + _fmt(numbers["agent_q3"]) + "}",
        r"\newcommand{\humanQone}{" + _fmt(numbers["human_q1"]) + "}",
        r"\newcommand{\humanQthree}{" + _fmt(numbers["human_q3"]) + "}",
        r"\newcommand{\lmmBeta}{" + _fmt(lmm_results["fixed_effect_slope"]) + "}",
        r"\newcommand{\lmmP}{" + _fmt(lmm_results["fixed_effect_pvalue"], ".4e") + "}",
        r"\newcommand{\spearmanRs}{" + _fmt(risk_results["spearman_rho"], ".3f") + "}",
        r"\newcommand{\spearmanP}{" + _fmt(risk_results["spearman_pvalue"], ".4e") + "}",
        r"\newcommand{\oddsRatio}{" + _fmt(risk_results["odds_ratio"], ".2f") + "}",
        r"\newcommand{\logitP}{" + _fmt(risk_results["logit_pvalue"], ".4e") + "}",
        r"\newcommand{\sepFlag}{" + ("yes" if risk_results["separation_detected"] else "no") + "}",
        r"\newcommand{\modelType}{" + str(risk_results["model_type"]).replace("%", "") + "}",
        r"\newcommand{\shapiroAW}{" + _fmt(diagnostics["shapiro_agent_stat"]) + "}",
        r"\newcommand{\shapiroAP}{" + _fmt(diagnostics["shapiro_agent_p"], ".4e") + "}",
        r"\newcommand{\shapiroHW}{" + _fmt(diagnostics["shapiro_human_stat"]) + "}",
        r"\newcommand{\shapiroHP}{" + _fmt(diagnostics["shapiro_human_p"], ".4e") + "}",
        r"\newcommand{\effectMag}{" + str(mwu_results["effect_size_magnitude"]) + "}",
    ]
    (output_dir / "results_macros.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")
    paper_copy = Path("paper") / "results_macros.tex"
    paper_copy.write_text("\n".join(macros) + "\n", encoding="utf-8")
    return numbers

def main():
    parser = argparse.ArgumentParser(description="Phase 4 Statistical Analysis Engine")
    parser.add_argument("--synthetic", action="store_true", help="Generate synthetic multi-repo dataset for preliminary testing")
    parser.add_argument("--outdir", type=str, default="results", help="Output directory for CSVs and markdown report")
    args = parser.parse_args()

    run_statistical_pipeline(synthetic=args.synthetic, output_dir=Path(args.outdir))

if __name__ == "__main__":
    main()
