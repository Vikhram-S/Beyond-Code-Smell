import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
from pathlib import Path
from src.figures.style_config import set_publication_style

def render_fig2_conformance_decay(data_path: Path, output_dir: Path):
    """
    Renders Fig 2: Conformance Decay Rate over session index faceted by repository size.
    Features individual repo trajectories with mean trendlines and confidence bands.
    """
    palette = set_publication_style()
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame()
    if data_path.exists():
        try:
            raw_df = pd.read_csv(data_path)
            if "step_idx" in raw_df.columns:
                df = raw_df
        except Exception:
            pass

    if df.empty:
        raise FileNotFoundError(
            f"No real session dataset at {data_path}. Refusing synthetic figures for the paper."
        )

    fig, axes = plt.subplots(1, 3, figsize=(10.0, 3.8), sharey=True, dpi=600)
    sizes = ["small", "medium", "large"]
    titles = ["Small Repos (<200 LOC/mod)", "Medium Repos (200-1k LOC)", "Large Repos (>1k LOC)"]

    for idx, (size, title_str) in enumerate(zip(sizes, titles)):
        ax = axes[idx]
        sub_df = df[df["repo_size"] == size]

        def _ci_band(data, x_col, y_col, ax, color, ls, lw, marker, ms, label):
            """
            Plot individual faint trajectories + mean line + shaded 95% CI band.
            95% CI = mean ± 1.96 × SE  (SE = std / sqrt(n))
            Convention: shaded band (not error bars) — consistent across Figs 2–5.
            """
            # Faint individual trajectories
            for repo, grp in data.groupby("repo_id"):
                ax.plot(grp[x_col], grp[y_col], color=color, alpha=0.20,
                        linewidth=0.8, linestyle=ls)

            # Per-step mean ± 95% CI
            grouped = data.groupby(x_col)[y_col]
            xs   = sorted(data[x_col].unique())
            mus  = [grouped.mean()[x]  for x in xs]
            sems = [grouped.sem()[x]   for x in xs]
            lo   = [m - 1.96 * s for m, s in zip(mus, sems)]
            hi   = [m + 1.96 * s for m, s in zip(mus, sems)]

            ax.fill_between(xs, lo, hi, color=color, alpha=0.18, zorder=2)
            ax.plot(xs, mus, color=color, linewidth=lw, linestyle=ls,
                    marker=marker, markersize=ms,
                    markeredgecolor="white", markeredgewidth=1.2,
                    label=label, zorder=3)

        # 1. Agent trajectories
        agent_sub = sub_df[sub_df["subject"] == "agent"]
        _ci_band(agent_sub, "step_idx", "cnlv", ax,
                 color=palette["agent"], ls="-", lw=2.8,
                 marker="o", ms=7,
                 label="Agent Sessions" if idx == 0 else None)

        # 2. Human baseline
        human_sub = sub_df[sub_df["subject"] == "human"]
        _ci_band(human_sub, "step_idx", "cnlv", ax,
                 color=palette["human"], ls="--", lw=2.4,
                 marker="s", ms=6.5,
                 label="Matched Human Baseline" if idx == 0 else None)

        # Custom Facet Header Title Banner
        ax.set_title(title_str, fontsize=10.5, fontweight="bold", pad=8)
        ax.set_xlabel("Session / Commit Index ($t$)", fontsize=10, fontweight="bold")
        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels(["Session 1", "Session 2", "Session 3"])
        
        if idx == 0:
            ax.set_ylabel("Complexity-Norm. Drift ($\\text{CNLV}$)", fontsize=10.5, fontweight="bold")

    # Global Legend formatting
    fig.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.05),
        ncol=2,
        frameon=True,
        facecolor="#FAFAFA",
        edgecolor="#D0D0D0",
        fontsize=10
    )
    
    plt.suptitle("Figure 2: Architectural Conformance Decay Trajectories Across Repo Size Tiers", fontsize=11.5, fontweight="bold", y=1.12)
    plt.tight_layout()

    pdf_path = output_dir / "fig2_conformance_decay.pdf"
    svg_path = output_dir / "fig2_conformance_decay.svg"
    png_path = output_dir / "fig2_conformance_decay.png"
    plt.savefig(pdf_path, format="pdf", bbox_inches="tight")
    plt.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.savefig(png_path, format="png", dpi=600, bbox_inches="tight")
    plt.close()

    print(f"Rendered elite Fig 2 conformance decay plot: {pdf_path}")
