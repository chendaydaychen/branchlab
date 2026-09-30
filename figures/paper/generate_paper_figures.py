#!/usr/bin/env python3
"""Generate vector, publication-ready figures for the BranchLab paper."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


OUT = Path(__file__).resolve().parent

# Restrained, color-blind-friendly palette. Every category also has a text label.
INK = "#20262E"
MUTED = "#5D6875"
GRID = "#CBD2D9"
LIGHT = "#F5F7F9"
BLUE = "#3B6FB6"
BLUE_L = "#E7F0FA"
GREEN = "#2F855A"
GREEN_L = "#E8F5EE"
ORANGE = "#C66A1B"
ORANGE_L = "#FBEFDF"
RED = "#B54747"
RED_L = "#F9E8E8"
PURPLE = "#7653A6"
PURPLE_L = "#F0EAF8"

mpl.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8.0,
        "axes.titlesize": 9.0,
        "axes.labelsize": 8.0,
        "xtick.labelsize": 7.2,
        "ytick.labelsize": 7.2,
        "axes.edgecolor": INK,
        "axes.linewidth": 0.7,
        "text.color": INK,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
    }
)


def box(ax, xy, wh, text, fc=LIGHT, ec=INK, lw=0.8, radius=0.035,
        fontsize=7.5, weight="normal", align="center", z=2):
    x, y = xy
    w, h = wh
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        facecolor=fc, edgecolor=ec, linewidth=lw, zorder=z,
    )
    ax.add_patch(p)
    ha = "center" if align == "center" else "left"
    tx = x + w / 2 if ha == "center" else x + 0.025
    ax.text(tx, y + h / 2, text, ha=ha, va="center", fontsize=fontsize,
            weight=weight, linespacing=1.25, zorder=z + 1)
    return p


def arrow(ax, start, end, color=INK, lw=0.9, style="-|>", rad=0.0,
          dashed=False, z=1):
    a = FancyArrowPatch(
        start, end, arrowstyle=style, mutation_scale=8,
        linewidth=lw, color=color,
        connectionstyle=f"arc3,rad={rad}",
        linestyle=(0, (3, 2)) if dashed else "solid", zorder=z,
    )
    ax.add_patch(a)
    return a


def label(ax, x, y, text, color=MUTED, size=6.8, ha="center", weight="normal"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=size,
            color=color, weight=weight)


def base_ax(figsize):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def save(fig, stem):
    for ext in ("pdf", "svg", "png"):
        kwargs = {"dpi": 300} if ext == "png" else {}
        fig.savefig(OUT / f"{stem}.{ext}", **kwargs)
    plt.close(fig)


def architecture():
    fig, ax = base_ax((7.05, 3.55))

    ax.text(0.5, 0.965, "BranchLab: Transaction Runtime for Multi-Branch Agents",
            ha="center", va="top", fontsize=10, weight="bold")

    # Inputs.
    box(ax, (0.015, 0.67), (0.13, 0.13), "User task\n+ conversation", BLUE_L, BLUE)
    box(ax, (0.015, 0.46), (0.13, 0.13), "Tool / API\npolicies", PURPLE_L, PURPLE)
    box(ax, (0.015, 0.25), (0.13, 0.13), "Current data\nsnapshot", ORANGE_L, ORANGE)

    # Speculative execution plane.
    ax.add_patch(FancyBboxPatch((0.19, 0.20), 0.39, 0.65,
                               boxstyle="round,pad=0.015,rounding_size=0.025",
                               facecolor="#FFFFFF", edgecolor=GRID, linewidth=1.0))
    label(ax, 0.385, 0.82, "SPECULATIVE EXECUTION PLANE", INK, 7.3, weight="bold")
    box(ax, (0.225, 0.665), (0.32, 0.105), "Shared-prefix executor\n(dialogue + deterministic reads)", BLUE_L, BLUE)
    box(ax, (0.225, 0.50), (0.32, 0.09), "Automatic fork at first write intent", LIGHT, INK)
    arrow(ax, (0.385, 0.665), (0.385, 0.595), BLUE)

    # Branches.
    bw, by, bh = 0.092, 0.285, 0.13
    xs = [0.215, 0.34, 0.465]
    for i, x in enumerate(xs, 1):
        fc = GREEN_L if i == 2 else LIGHT
        ec = GREEN if i == 2 else GRID
        box(ax, (x, by), (bw, bh), f"Branch {i}\nprivate state", fc, ec, fontsize=7.0)
        arrow(ax, (0.385, 0.50), (x + bw / 2, by + bh), BLUE, rad=(x - 0.34) * 0.7)
    label(ax, 0.386, 0.235, "isolated continuations  •  winner-only materialization",
          MUTED, 6.6)

    # Contract and commit plane.
    ax.add_patch(FancyBboxPatch((0.62, 0.20), 0.235, 0.65,
                               boxstyle="round,pad=0.015,rounding_size=0.025",
                               facecolor="#FFFFFF", edgecolor=GRID, linewidth=1.0))
    label(ax, 0.738, 0.82, "SEMANTIC COMMIT PLANE", INK, 7.3, weight="bold")
    box(ax, (0.65, 0.665), (0.175, 0.105), "LLM task-clause\ncompiler", PURPLE_L, PURPLE)
    box(ax, (0.65, 0.505), (0.175, 0.095), "Trusted operation\nsafety floor", ORANGE_L, ORANGE)
    box(ax, (0.65, 0.345), (0.175, 0.095), "Bind branch, snapshot,\noperation, arguments", LIGHT, INK, fontsize=6.9)
    box(ax, (0.65, 0.225), (0.175, 0.065), "Deterministic validator", GREEN_L, GREEN,
        fontsize=7.0, weight="bold")
    arrow(ax, (0.738, 0.665), (0.738, 0.605), PURPLE)
    arrow(ax, (0.738, 0.505), (0.738, 0.445), ORANGE)
    arrow(ax, (0.738, 0.345), (0.738, 0.295), INK)
    arrow(ax, (0.557, 0.35), (0.65, 0.39), GREEN)

    # Storage / external world.
    box(ax, (0.885, 0.61), (0.10, 0.15), "Database\n(MVCC / locks)", ORANGE_L, ORANGE, fontsize=7.0)
    box(ax, (0.885, 0.36), (0.10, 0.15), "External\ntools", PURPLE_L, PURPLE, fontsize=7.0)
    box(ax, (0.885, 0.18), (0.10, 0.10), "Audit log", LIGHT, INK, fontsize=7.0)
    arrow(ax, (0.825, 0.26), (0.885, 0.675), GREEN, rad=-0.17)
    arrow(ax, (0.825, 0.26), (0.885, 0.435), GREEN, rad=-0.08)
    arrow(ax, (0.825, 0.25), (0.885, 0.23), INK)

    # Input arrows.
    arrow(ax, (0.145, 0.735), (0.225, 0.715), BLUE)
    arrow(ax, (0.145, 0.525), (0.65, 0.715), PURPLE, rad=-0.12)
    arrow(ax, (0.145, 0.315), (0.225, 0.70), ORANGE, rad=0.14)

    # Unified state bar.
    ax.add_patch(Rectangle((0.19, 0.075), 0.665, 0.075, facecolor=LIGHT,
                           edgecolor=GRID, linewidth=0.8))
    ax.text(0.22, 0.112, "Unified state", va="center", weight="bold", fontsize=6.8)
    ax.text(0.395, 0.112, r"$D$: data state", va="center", color=ORANGE, fontsize=6.8)
    ax.text(0.605, 0.112, r"$B$: branch state", va="center", color=BLUE, fontsize=6.8)
    ax.text(0.755, 0.112, r"$S$: task semantics", va="center", color=PURPLE, fontsize=6.8)

    save(fig, "fig1-branchlab-architecture")


def lifecycle():
    fig, ax = base_ax((7.05, 3.15))
    ax.text(0.5, 0.96, "Lifecycle of a Multi-Branch Agent Transaction",
            ha="center", va="top", fontsize=10, weight="bold")

    # Time axis.
    y0 = 0.78
    arrow(ax, (0.06, y0), (0.95, y0), INK, lw=0.8)
    for x, t in [(0.10, "task"), (0.38, "fork"), (0.74, "select"), (0.92, "commit")]:
        ax.plot([x, x], [y0 - 0.018, y0 + 0.018], color=INK, lw=0.7)
        label(ax, x, y0 + 0.055, t, INK, 6.8)

    # Shared prefix.
    ax.add_patch(Rectangle((0.10, 0.62), 0.28, 0.075, facecolor=BLUE_L,
                           edgecolor=BLUE, linewidth=0.8))
    ax.text(0.24, 0.657, "one shared dialogue / read prefix", ha="center", va="center",
            fontsize=7.2, weight="bold")
    for x, txt in [(0.13, "read user"), (0.22, "read order"), (0.31, "confirm")]:
        ax.plot([x, x], [0.61, 0.705], color=BLUE, lw=0.7)
        label(ax, x, 0.58, txt, MUTED, 6.3)

    # Fork point.
    ax.plot([0.38, 0.38], [0.24, 0.73], color=BLUE, lw=1.0, linestyle=(0, (3, 2)))
    box(ax, (0.335, 0.46), (0.09, 0.07), "first write\nintent", BLUE_L, BLUE, fontsize=6.5)

    # Lanes.
    lane_y = [0.48, 0.36, 0.24]
    colors = [GRID, GREEN, GRID]
    fills = [LIGHT, GREEN_L, LIGHT]
    for i, (y, ec, fc) in enumerate(zip(lane_y, colors, fills), 1):
        ax.plot([0.38, 0.78], [y, y], color=ec, lw=1.2)
        box(ax, (0.45, y - 0.035), (0.18, 0.07), f"LLM continuation {i}", fc, ec, fontsize=6.8)
        box(ax, (0.655, y - 0.035), (0.10, 0.07), "private\nstate", fc, ec, fontsize=6.4)
        arrow(ax, (0.38, 0.62), (0.40, y), BLUE, rad=(y - 0.36) * 0.5)
    label(ax, 0.525, 0.16, "Shared observations are inherited; post-fork writes never cross branches.", MUTED, 6.8)

    # Winner selection and commit.
    box(ax, (0.79, 0.33), (0.085, 0.095), "winner\nbranch 2", GREEN_L, GREEN, fontsize=6.8, weight="bold")
    arrow(ax, (0.755, 0.36), (0.79, 0.377), GREEN)
    box(ax, (0.89, 0.33), (0.09, 0.095), "contract\nvalidate", PURPLE_L, PURPLE, fontsize=6.8)
    arrow(ax, (0.875, 0.377), (0.89, 0.377), GREEN)
    arrow(ax, (0.935, 0.33), (0.935, 0.24), GREEN)
    box(ax, (0.89, 0.15), (0.09, 0.07), "materialize", GREEN_L, GREEN,
        fontsize=6.8, weight="bold")
    label(ax, 0.835, 0.28, "discard 1 & 3", RED, 6.3)

    save(fig, "fig2-transaction-lifecycle")


def contract_pipeline():
    fig, ax = base_ax((7.05, 3.35))
    ax.text(0.5, 0.96, "Trusted Semantic Contract Compilation and Validation",
            ha="center", va="top", fontsize=10, weight="bold")

    # Inputs.
    box(ax, (0.02, 0.63), (0.16, 0.16), "Task context\nrequest · dialogue\nwrite intent", BLUE_L, BLUE, fontsize=6.8)
    box(ax, (0.02, 0.31), (0.16, 0.16), "Operation spec\nAPI · policy\nDB constraints", ORANGE_L, ORANGE, fontsize=6.8)

    # Compilation streams.
    box(ax, (0.235, 0.63), (0.18, 0.16), "LLM task clauses\nauthorization\nsemantic dependencies\ntolerated changes", PURPLE_L, PURPLE, fontsize=6.2)
    box(ax, (0.235, 0.31), (0.18, 0.16), "Trusted safety floor\nnon-removable\npredicates\n(per operation)", ORANGE_L, ORANGE, fontsize=6.0)
    arrow(ax, (0.18, 0.71), (0.235, 0.71), BLUE)
    arrow(ax, (0.18, 0.39), (0.235, 0.39), ORANGE)

    # Harden and bind.
    box(ax, (0.47, 0.50), (0.15, 0.14), "Harden\nschema + union", LIGHT, INK, fontsize=7.0, weight="bold")
    arrow(ax, (0.415, 0.71), (0.47, 0.59), PURPLE)
    arrow(ax, (0.415, 0.39), (0.47, 0.55), ORANGE)
    box(ax, (0.47, 0.27), (0.15, 0.14), "Bind\nbranch · snapshot\nop · args", LIGHT, INK, fontsize=6.8, weight="bold")
    arrow(ax, (0.545, 0.50), (0.545, 0.415), INK)

    # Validate.
    box(ax, (0.675, 0.45), (0.15, 0.18), "Deterministic validator\ncheck predicates\non current state", GREEN_L, GREEN, fontsize=6.8, weight="bold")
    arrow(ax, (0.62, 0.34), (0.675, 0.51), INK)
    box(ax, (0.675, 0.20), (0.15, 0.10), "Current snapshot $S_t$", ORANGE_L, ORANGE, fontsize=7.0)
    arrow(ax, (0.75, 0.30), (0.75, 0.445), ORANGE)

    # Outcomes.
    box(ax, (0.855, 0.61), (0.13, 0.12), "Benign\nREBASE + COMMIT", GREEN_L, GREEN,
        fontsize=6.1, weight="bold")
    box(ax, (0.855, 0.31), (0.13, 0.12), "Harmful\nREJECT / REPLAN", RED_L, RED,
        fontsize=6.1, weight="bold")
    arrow(ax, (0.825, 0.56), (0.855, 0.67), GREEN)
    arrow(ax, (0.825, 0.50), (0.855, 0.37), RED)
    label(ax, 0.928, 0.53, "predicate result", MUTED, 6.3)

    # Trust boundary.
    ax.plot([0.445, 0.445], [0.13, 0.86], color=RED, lw=0.8, linestyle=(0, (3, 2)))
    label(ax, 0.435, 0.12, "untrusted proposal", RED, 6.4, ha="right")
    label(ax, 0.455, 0.12, "trusted execution", GREEN, 6.4, ha="left")

    save(fig, "fig3-semantic-contract-pipeline")


def controller_comparison():
    fig, ax = base_ax((7.05, 3.25))
    ax.text(0.5, 0.96, "Why Physical Conflicts Are Not Task Conflicts",
            ha="center", va="top", fontsize=10, weight="bold")

    cols = [(0.035, "2PL", BLUE), (0.355, "Strict OCC", ORANGE), (0.675, "BranchLab", GREEN)]
    for x, title, color in cols:
        ax.add_patch(FancyBboxPatch((x, 0.13), 0.29, 0.72,
                                   boxstyle="round,pad=0.012,rounding_size=0.02",
                                   facecolor="#FFFFFF", edgecolor=GRID, linewidth=0.9))
        ax.text(x + 0.145, 0.81, title, ha="center", va="center", weight="bold",
                color=color, fontsize=9)

    # 2PL.
    box(ax, (0.075, 0.64), (0.21, 0.09), "read order + acquire lock", BLUE_L, BLUE, fontsize=7.0)
    arrow(ax, (0.18, 0.64), (0.18, 0.56), BLUE)
    box(ax, (0.075, 0.47), (0.21, 0.09), "LLM reasoning while lock held", LIGHT, BLUE, fontsize=6.9)
    arrow(ax, (0.18, 0.47), (0.18, 0.39), BLUE)
    box(ax, (0.075, 0.30), (0.21, 0.09), "concurrent update: BLOCKED", RED_L, RED, fontsize=7.0, weight="bold")
    label(ax, 0.18, 0.205, "safe, but long critical section", MUTED, 6.7)

    # OCC.
    box(ax, (0.395, 0.64), (0.21, 0.09), "read version $v_0$", ORANGE_L, ORANGE, fontsize=7.0)
    arrow(ax, (0.50, 0.64), (0.50, 0.56), ORANGE)
    box(ax, (0.395, 0.47), (0.21, 0.09), "benign update: $v_0 \\rightarrow v_1$", LIGHT, ORANGE, fontsize=7.0)
    arrow(ax, (0.50, 0.47), (0.50, 0.39), ORANGE)
    box(ax, (0.395, 0.30), (0.21, 0.09), "$v_0 \\ne v_1$: ABORT", RED_L, RED, fontsize=7.1, weight="bold")
    label(ax, 0.50, 0.205, "non-blocking, but false conflicts", MUTED, 6.7)

    # BranchLab.
    box(ax, (0.715, 0.64), (0.21, 0.09), "read semantic dependencies", GREEN_L, GREEN, fontsize=7.0)
    arrow(ax, (0.82, 0.64), (0.82, 0.56), GREEN)
    box(ax, (0.715, 0.47), (0.21, 0.09), "validate task predicates", LIGHT, GREEN, fontsize=7.0)
    arrow(ax, (0.82, 0.47), (0.78, 0.39), GREEN)
    arrow(ax, (0.82, 0.47), (0.87, 0.39), RED)
    box(ax, (0.695, 0.29), (0.125, 0.10), "benign\nCOMMIT", GREEN_L, GREEN, fontsize=6.8, weight="bold")
    box(ax, (0.835, 0.29), (0.125, 0.10), "harmful\nREJECT", RED_L, RED, fontsize=6.8, weight="bold")
    label(ax, 0.82, 0.205, "concurrency follows task semantics", MUTED, 6.7)

    save(fig, "fig4-controller-comparison")


def evidence_summary():
    fig, axs = plt.subplots(1, 3, figsize=(7.05, 2.65), gridspec_kw={"wspace": 0.52})
    fig.suptitle("Empirical Evidence Across Real Agent Traces and PostgreSQL",
                 y=1.00, fontsize=10, weight="bold")

    # Panel A: opportunity.
    ax = axs[0]
    ax.barh([1, 0], [43.7, 60.9], color=[BLUE, PURPLE], height=0.48)
    ax.set_yticks([1, 0], ["Tool calls\nshareable", "Repeated\nexact reads"])
    ax.set_xlim(0, 70)
    ax.set_xlabel("Fraction of observed calls (%)")
    ax.set_title("(a) Sharing opportunity")
    for y, v in [(1, 43.7), (0, 60.9)]:
        ax.text(v + 1.5, y, f"{v:.1f}%", va="center", fontsize=7.2, weight="bold")
    ax.grid(axis="x", color=GRID, lw=0.5, alpha=0.8)
    ax.set_axisbelow(True)

    # Panel B: paired semantics. A benign change is "admitted" only if the
    # concurrent update actually enters and the transaction still commits.
    # Harmful changes are prevented either by blocking (2PL) or rejection.
    ax = axs[1]
    modes = ["2PL", "OCC", "BranchLab"]
    benign = [0, 0, 71]
    harmful = [71, 71, 71]
    x = range(3)
    ax.bar([i - 0.18 for i in x], benign, width=0.36, label="benign admitted",
           color=GREEN)
    ax.bar([i + 0.18 for i in x], harmful, width=0.36, label="harmful prevented",
           color=RED, hatch="///")
    ax.set_xticks(list(x), modes, rotation=20)
    ax.set_ylim(0, 79)
    ax.set_ylabel("Accepted traces (of 71)")
    ax.set_title("(b) Paired disturbances")
    ax.grid(axis="y", color=GRID, lw=0.5, alpha=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=6.2, loc="upper center", bbox_to_anchor=(0.5, -0.23), ncol=1)
    for i, v in enumerate(benign):
        ax.text(i - 0.18, v + (3 if v else 2), str(v), ha="center", fontsize=7.0, weight="bold")
    for i, v in enumerate(harmful):
        ax.text(i + 0.18, v + 3, str(v), ha="center", fontsize=7.0, weight="bold")

    # Panel C: high-contention goodput.
    ax = axs[2]
    values = [27.01, 78.38, 179.70]
    errs = [0.19, 3.52, 5.13]
    colors = [BLUE, ORANGE, GREEN]
    ax.bar(modes, values, yerr=errs, capsize=2.5, color=colors, width=0.62,
           error_kw={"elinewidth": 0.8, "capthick": 0.8})
    ax.set_ylim(0, 205)
    ax.set_ylabel("Successful goodput (ops/s)")
    ax.set_title("(c) 32-worker long stress")
    ax.tick_params(axis="x", rotation=20)
    ax.grid(axis="y", color=GRID, lw=0.5, alpha=0.8)
    ax.set_axisbelow(True)
    for i, v in enumerate(values):
        ax.text(i, v + errs[i] + 6, f"{v:.1f}", ha="center", fontsize=7.0, weight="bold")

    for ax in axs:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.subplots_adjust(left=0.075, right=0.99, bottom=0.27, top=0.82)
    save(fig, "fig5-evidence-summary")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    architecture()
    lifecycle()
    contract_pipeline()
    controller_comparison()
    evidence_summary()
    print(f"Generated paper figures in {OUT}")
