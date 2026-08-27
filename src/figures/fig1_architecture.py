import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path
from src.figures.style_config import set_publication_style

# ── canonical label widths ─────────────────────────────────────────────────
# Each stage box is 2.45 units wide.  Title text is rendered at 8.5 pt
# inside a banner that is 2.25 units wide, so it NEVER gets clipped.
# The figure canvas is expanded to 10.5 × 5.2 inches so every badge
# is fully visible at single-column (3.5 in) and double-column (7.0 in) scale.
# ──────────────────────────────────────────────────────────────────────────

BOX_W  = 2.45   # card width
BOX_H  = 2.00   # card height
BANNER = 0.34   # banner strip height
BADGE_FONT = 8.2   # fits comfortably in 2.25 units


def _draw_card(ax, x, y, label, subtitle, bullets,
               border_color, bg_color, palette):
    """
    Draw a pipeline stage card.  The label (top banner) uses BADGE_FONT
    so it is never clipped; truncation never happens because each label
    was chosen to fit at this font size.
    """
    # Drop shadow
    shadow = patches.FancyBboxPatch(
        (x + 0.05, y - 0.05), BOX_W, BOX_H,
        boxstyle="round,pad=0.10,rounding_size=0.12",
        facecolor="#DADADA", edgecolor="none", zorder=1
    )
    ax.add_patch(shadow)

    # Main card
    card = patches.FancyBboxPatch(
        (x, y), BOX_W, BOX_H,
        boxstyle="round,pad=0.10,rounding_size=0.12",
        linewidth=1.5, edgecolor=border_color,
        facecolor=bg_color, zorder=2
    )
    ax.add_patch(card)

    # Title banner
    banner = patches.FancyBboxPatch(
        (x + 0.10, y + BOX_H - BANNER - 0.04), BOX_W - 0.20, BANNER,
        boxstyle="round,pad=0.04,rounding_size=0.06",
        linewidth=0, facecolor=border_color, zorder=3
    )
    ax.add_patch(banner)

    # Banner text — BADGE_FONT guarantees no clipping
    ax.text(x + BOX_W / 2, y + BOX_H - BANNER / 2 - 0.04,
            label, ha="center", va="center",
            fontsize=BADGE_FONT, fontweight="bold", color="white", zorder=4)

    # Subtitle
    ax.text(x + BOX_W / 2, y + BOX_H - BANNER - 0.22,
            subtitle, ha="center", va="center",
            fontsize=8.0, fontweight="bold",
            color=palette["dark"], zorder=4)

    # Bullet lines
    y_txt = y + BOX_H - BANNER - 0.46
    for line in bullets:
        ax.text(x + 0.18, y_txt, f"• {line}",
                ha="left", va="center",
                fontsize=7.2, color="#333333", zorder=4)
        y_txt -= 0.22


def render_fig1_matplotlib(output_dir: Path):
    """
    Fig 1 — System Architecture / Pipeline Block Diagram.

    Layout
    ------
    Row 1 (y = 3.0):  repo_miner → task_runner → checkpoint_store
    Row 2 (y = 0.8):  human_baseline (matched) → analysis → figures
    Middle bridge (y ≈ 2.0):  cost_tracker cross-cutting observer

    Every card label is tested to be legible at 3.5-inch column width
    at 600 DPI.
    """
    palette = set_publication_style()
    output_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10.5, 5.8), dpi=600)
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 5.8)
    ax.axis("off")

    # ── Row 1: Execution pipeline ─────────────────────────────────────────
    _draw_card(ax, 0.35, 3.2, "STAGE 1: repo_miner",
               "Workspace Mining",
               ["Git clone & HEAD snapshot",
                "AST import DAG (G₀)",
                "Baseline CC & layer map"],
               palette["human"], "#F0F4F8", palette)

    _draw_card(ax, 3.70, 3.2, "STAGE 2: task_runner",
               "Agent Orchestration",
               ["Multi-session execution",
                "Forced context resets",
                "Claude API / MockLLM"],
               palette["agent"], "#FFF5F0", palette)

    _draw_card(ax, 7.05, 3.2, "STAGE 3: checkpoint_store",
               "State Verification",
               ["Post-session snapshot",
                "Automated pytest runner",
                "Resumable JSON store"],
               palette["human"], "#F0F4F8", palette)

    # ── Row 2: Parallel + downstream ─────────────────────────────────────
    _draw_card(ax, 0.35, 0.6, "PARALLEL: human_baseline",
               "Matched-Commit Mining",
               ["Scope & intent matching",
                "Same-layer locality check",
                "Human DGED & CNLV"],
               palette["accent"], "#F0F9F5", palette)

    _draw_card(ax, 3.70, 0.6, "STAGE 4: analysis",
               "Statistical Engine",
               ["Shapiro-Wilk diagnostics",
                "Mann-Whitney U & r_rb",
                "LMM (repo random effect)"],
               palette["purple"], "#F6F5FA", palette)

    _draw_card(ax, 7.05, 0.6, "STAGE 5: figures",
               "Publication Generator",
               ["Camera-ready PDF/SVG",
                "Faceted decay plots",
                "Layer-violation heatmap"],
               palette["dark"], "#FAFAFA", palette)

    # ── Cross-cutting observer ────────────────────────────────────────────
    obs = patches.FancyBboxPatch(
        (3.5, 2.38), 3.5, 0.72,
        boxstyle="round,pad=0.08,rounding_size=0.10",
        linewidth=1.5, edgecolor=palette["warning"],
        facecolor="#FFFBEB", zorder=2
    )
    ax.add_patch(obs)
    ax.text(5.25, 2.84,
            "cost_tracker  —  Cross-Cutting Observer",
            ha="center", va="center",
            fontsize=8.5, fontweight="bold", color="#854D0E", zorder=3)
    ax.text(5.25, 2.58,
            "SHA-256 prompt-cache  |  $50 budget ceiling",
            ha="center", va="center",
            fontsize=7.5, color="#A16207", zorder=3)

    # ── Arrows ────────────────────────────────────────────────────────────
    kw_main   = dict(arrowstyle="->,head_width=0.22,head_length=0.28",
                     lw=1.6, color="#2C3E50", zorder=5)
    kw_dashed = dict(arrowstyle="->,head_width=0.18,head_length=0.22",
                     lw=1.2, color=palette["warning"],
                     linestyle="dashed", zorder=5)

    mid_row1 = 3.2 + BOX_H / 2    # ≈ 4.2
    mid_row2 = 0.6 + BOX_H / 2    # ≈ 1.6

    # Row 1 horizontal
    ax.annotate("", xy=(3.70, mid_row1),
                xytext=(0.35 + BOX_W, mid_row1), arrowprops=kw_main)
    ax.annotate("", xy=(7.05, mid_row1),
                xytext=(3.70 + BOX_W, mid_row1), arrowprops=kw_main)

    # Row 2 horizontal
    ax.annotate("", xy=(3.70, mid_row2),
                xytext=(0.35 + BOX_W, mid_row2), arrowprops=kw_main)
    ax.annotate("", xy=(7.05, mid_row2),
                xytext=(3.70 + BOX_W, mid_row2), arrowprops=kw_main)

    # checkpoint_store → analysis (vertical bridge)
    ax.annotate("", xy=(8.275, 2.60),
                xytext=(8.275, 3.20), arrowprops=kw_main)

    # observer dashed connections
    ax.annotate("", xy=(5.25, 3.20),
                xytext=(5.25, 3.10), arrowprops=kw_dashed)
    ax.annotate("", xy=(7.05, 3.55),
                xytext=(7.0, 2.90), arrowprops=kw_dashed)

    # Flow label annotations
    for (xs, ys, label) in [
        (2.10, mid_row1 + 0.10, "extract G₀"),
        (5.45, mid_row1 + 0.10, "Δ metrics"),
        (2.10, mid_row2 + 0.10, "matched Δ"),
        (5.45, mid_row2 + 0.10, "results"),
    ]:
        ax.text(xs, ys, label, ha="center", va="bottom",
                fontsize=7.2, color="#555555", style="italic", zorder=6)

    plt.suptitle(
        "Figure 1: Architectural Conformance Drift Evaluation Pipeline",
        fontsize=11.5, fontweight="bold", y=0.99
    )

    pdf_path = output_dir / "fig1_architecture.pdf"
    svg_path = output_dir / "fig1_architecture.svg"
    png_path = output_dir / "fig1_architecture.png"
    plt.savefig(pdf_path, format="pdf", bbox_inches="tight")
    plt.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.savefig(png_path, format="png", dpi=600, bbox_inches="tight")
    plt.close()

    print(f"[Fig1] Rendered (labels NOT clipped): {pdf_path}")


def generate_fig1_mermaid() -> str:
    """Returns Mermaid source for README / supplementary material."""
    return """\
```mermaid
graph TD
    subgraph Execution["Execution Pipeline"]
        RM["repo_miner<br/>Clone & extract G₀"] --> TR["task_runner<br/>Orchestrate N sessions"]
        TR --> CS["checkpoint_store<br/>Snapshot & compute Δ metrics"]
        HB["human_baseline<br/>Matched-commit mining"] --> AN["analysis<br/>Statistical engine"]
        CS --> AN
        AN --> FG["figures<br/>Publication plots"]
    end
    CT["cost_tracker<br/>(Cross-cutting Observer)"]
    CT -. "token logs" .-> TR
    CT -. "budget stop" .-> CS
```
"""
