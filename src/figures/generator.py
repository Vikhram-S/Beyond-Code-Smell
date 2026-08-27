import argparse
from pathlib import Path

from src.figures.fig1_architecture import render_fig1_matplotlib, generate_fig1_mermaid
from src.figures.fig2_conformance_decay import render_fig2_conformance_decay
from src.figures.fig3_violin_comparison import render_fig3_violin_comparison
from src.figures.fig4_violation_heatmap import render_fig4_violation_heatmap
from src.figures.fig5_correlation_plot import render_fig5_correlation_plot
from src.figures.fig6_cost_envelope import render_fig6_cost_envelope

def generate_all_figures(data_path: Path, output_dir: Path, fig_num: int | None = None):
    output_dir.mkdir(parents=True, exist_ok=True)

    print("==================================================")
    print("Generating Camera-Ready Publication Figures")
    print(f"Data Input: {data_path} | Output Dir: {output_dir}")
    print("==================================================")

    if fig_num is None or fig_num == 1:
        render_fig1_matplotlib(output_dir)

    if fig_num is None or fig_num == 2:
        render_fig2_conformance_decay(data_path, output_dir)

    if fig_num is None or fig_num == 3:
        render_fig3_violin_comparison(data_path, output_dir)

    if fig_num is None or fig_num == 4:
        render_fig4_violation_heatmap(data_path, output_dir)

    if fig_num is None or fig_num == 5:
        render_fig5_correlation_plot(data_path, output_dir)

    if fig_num is None or fig_num == 6:
        render_fig6_cost_envelope(output_dir)

    print("\n==================================================")
    print("All figures successfully rendered to PDF and PNG!")
    print("==================================================")

def main():
    parser = argparse.ArgumentParser(description="Publication Figure Generator for Architectural Drift Paper")
    parser.add_argument("--data", type=str, default="results/descriptive_stats.csv", help="Path to statistical results CSV")
    parser.add_argument("--outdir", type=str, default="outputs/figures", help="Output directory for generated PDF/PNG figures")
    parser.add_argument("--fig", type=int, default=None, help="Optionally generate specific figure number (1-6)")
    args = parser.parse_args()

    generate_all_figures(
        data_path=Path(args.data),
        output_dir=Path(args.outdir),
        fig_num=args.fig
    )

if __name__ == "__main__":
    main()
