import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy import stats
from src.figures.style_config import set_publication_style

def render_fig5_correlation_plot(data_path: Path, output_dir: Path):
    """
    Fig 5: CNLV vs downstream test-failure probability.

    Consistency fixes (Phase D):
    - CI shown as shaded band (fill_between), NOT error bars — same convention as Fig 2.
    - Odds Ratio annotation replaced with PLACEHOLDER so no mock value is shown.
    - Separation detection flag surfaced in the annotation box.
    - Palette locked to style_config (agent = #D55E00).
    """
    palette = set_publication_style()
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame()
    if data_path.exists():
        try:
            raw_df = pd.read_csv(data_path)
            if "task_failed" in raw_df.columns and "cnlv" in raw_df.columns:
                df = raw_df
        except Exception:
            pass

    if df.empty:
        raise FileNotFoundError(
            f"No real dataset at {data_path}. Refusing synthetic figures for the paper."
        )

    agent_df = df[df["subject"] == "agent"].copy()

    r_s, p_val = stats.spearmanr(agent_df["cnlv"], agent_df["task_failed"])

    fig, ax = plt.subplots(figsize=(6.8, 4.4), dpi=600)

    # Jittered scatter
    rng = np.random.default_rng(seed=42)
    jitter = rng.uniform(-0.03, 0.03, size=len(agent_df))
    ax.scatter(
        agent_df["cnlv"],
        agent_df["task_failed"] + jitter,
        color=palette["agent"], alpha=0.70, s=48,
        edgecolors="white", linewidths=0.8, zorder=3,
        label="Agent Task Checkpoint",
    )

    # Logistic regression curve + shaded 95% CI band
    # ── CI band convention: same fill_between as Figs 2 & 3 ──────────────
    x_grid = np.linspace(agent_df["cnlv"].min(), agent_df["cnlv"].max(), 200)
    try:
        import statsmodels.api as sm
        X = sm.add_constant(agent_df["cnlv"].values)
        y = agent_df["task_failed"].values
        model = sm.Logit(y, X).fit(disp=False)
        X_pred = sm.add_constant(x_grid)
        pred = model.predict(X_pred)

        # Delta method 95% CI on the probability scale
        cov = model.cov_params()
        var_eta = np.array([X_pred[i] @ cov @ X_pred[i] for i in range(len(X_pred))])
        eta     = X_pred @ model.params
        p_hat   = 1 / (1 + np.exp(-eta))
        dp_deta = p_hat * (1 - p_hat)
        se_p    = dp_deta * np.sqrt(var_eta)
        lo = np.clip(p_hat - 1.96 * se_p, 0, 1)
        hi = np.clip(p_hat + 1.96 * se_p, 0, 1)

        ax.fill_between(x_grid, lo, hi,
                        color=palette["dark"], alpha=0.12, zorder=2,
                        label="95% CI (shaded band)")
        ax.plot(x_grid, pred,
                color=palette["dark"], linewidth=2.2, zorder=4,
                label="Logistic regression")
    except Exception:
        # If logit fails (e.g. separation), plot a simple rolling mean instead
        ax.plot(x_grid,
                np.interp(x_grid,
                          np.sort(agent_df["cnlv"]),
                          np.array(agent_df.sort_values("cnlv")["task_failed"],
                                   dtype=float)),
                color=palette["dark"], linewidth=1.8,
                linestyle="dashed", label="Empirical trend (approx.)")

    ax.set_title(
        "Figure 5: Downstream Test Failure vs. Architectural Drift ($\\text{CNLV}$)",
        fontsize=11, fontweight="bold", pad=12,
    )
    ax.set_xlabel("Complexity-Normalized Drift ($\\text{CNLV}$)",
                  fontsize=10.5, fontweight="bold")
    ax.set_ylabel("Downstream Task Test Failure",
                  fontsize=10.5, fontweight="bold")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Pass (0)", "Failure (1)"],
                       fontsize=10, fontweight="bold")
    ax.set_ylim(-0.12, 1.12)

    # Annotation box — OR from this dataset; flag separation if Firth was needed
    from src.analysis.stats_analyzer import StatisticalAnalyzer
    risk = StatisticalAnalyzer(df).run_downstream_risk_analysis()
    p_str  = f"{p_val:.4f}" if p_val >= 0.0001 else f"{p_val:.2e}"
    rs_str = f"{r_s:+.3f}"
    or_str = f"{risk['odds_ratio']:.2f}"
    sep = "Firth; OR unreliable under separation" if risk.get("separation_detected") or risk.get("ci_absurdly_wide") else risk.get("model_type", "logit")
    annot  = (
        r"$\mathbf{Spearman\ r_s}$" + "\n"
        + f"$r_s = {rs_str},\\ p = {p_str}$\n"
        + r"$\mathbf{Odds\ Ratio}$" + "\n"
        + f"$\\mathrm{{OR}} = {or_str}$\n"
        + sep
    )
    ax.text(
        0.04, 0.96, annot,
        transform=ax.transAxes, fontsize=8.5,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.45",
                  facecolor="#FAFAFA",
                  edgecolor="#CCCCCC", linewidth=1.0),
    )

    ax.legend(loc="lower right", frameon=True,
              facecolor="#FAFAFA", edgecolor="#CCCCCC", fontsize=9)
    plt.tight_layout()

    for fmt in ("pdf", "svg"):
        plt.savefig(output_dir / f"fig5_correlation_plot.{fmt}",
                    format=fmt, bbox_inches="tight")
    plt.savefig(output_dir / "fig5_correlation_plot.png",
                format="png", dpi=600, bbox_inches="tight")
    plt.close()

    print(f"[Fig5] Rendered (shaded-band CI, no mock OR): "
          f"{output_dir / 'fig5_correlation_plot.pdf'}")
