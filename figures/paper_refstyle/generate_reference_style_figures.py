#!/usr/bin/env python3
"""Generate BranchLab figures in a compact VLDB systems-paper style."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


OUT = Path(__file__).resolve().parent

INK = "#15191E"
EDGE = "#35404C"
OUTER = "#EEF7F3"
BLUE = "#DDEAF7"
BLUE_D = "#4B87B9"
GREEN = "#E4F5E2"
GREEN_D = "#5A9D58"
PEACH = "#F8E7DC"
PEACH_D = "#C87A45"
GRAY = "#F4F5F6"
GRAY_D = "#7B858F"
PURPLE = "#EEE7F7"
PURPLE_D = "#74559A"
RED = "#F8E6E6"
RED_D = "#B64A4A"

mpl.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8.0,
        "text.color": INK,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.025,
    }
)


def canvas(figsize=(7.05, 3.85)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def rounded(ax, x, y, w, h, text="", fc=GRAY, ec=EDGE, lw=0.85,
            r=0.025, fs=7.3, weight="normal", ls="solid", z=2):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.009,rounding_size={r}",
        facecolor=fc, edgecolor=ec, linewidth=lw, linestyle=ls, zorder=z,
    )
    ax.add_patch(patch)
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fs, weight=weight, linespacing=1.18, zorder=z + 1)
    return patch


def frame(ax, x, y, w, h, title, fc="none", ec=INK, dashed=True, title_y=None,
          title_fs=8.3):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.010,rounding_size=0.028",
        facecolor=fc, edgecolor=ec, linewidth=0.9,
        linestyle=(0, (4, 3)) if dashed else "solid", zorder=0,
    )
    ax.add_patch(patch)
    ty = y + h - 0.035 if title_y is None else title_y
    ax.text(x + w / 2, ty, title, ha="center", va="center",
            fontsize=title_fs, weight="bold", zorder=4,
            bbox=dict(facecolor=OUTER if fc == "none" else fc, edgecolor="none", pad=0.8))
    return patch


def arr(ax, p1, p2, color=INK, lw=0.9, dashed=False, rad=0.0, z=1):
    patch = FancyArrowPatch(
        p1, p2, arrowstyle="-|>", mutation_scale=8.5,
        linewidth=lw, color=color,
        linestyle=(0, (3, 2)) if dashed else "solid",
        connectionstyle=f"arc3,rad={rad}", zorder=z,
    )
    ax.add_patch(patch)
    return patch


def line_label(ax, x, y, text, color=INK, fs=6.5, weight="normal", rotation=0):
    ax.text(x, y, text, ha="center", va="center", fontsize=fs,
            color=color, weight=weight, rotation=rotation, zorder=5,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.82, pad=0.45))


def save(fig, stem):
    for ext in ("pdf", "svg", "png"):
        fig.savefig(OUT / f"{stem}.{ext}", dpi=320 if ext == "png" else None)
    plt.close(fig)


def data_ops(ax, start_x=0.43, y=0.86):
    widths = [0.018, 0.026, 0.048, 0.030, 0.014, 0.038, 0.057]
    x = start_x
    for i, w in enumerate(widths):
        h = 0.075 if i % 3 else 0.10
        ax.add_patch(Rectangle((x, y), w, h, facecolor="#62A6D5",
                               edgecolor="#355F7E", linewidth=0.75))
        x += w + 0.014
    return x


def overall_architecture():
    fig, ax = canvas((7.05, 4.15))

    rounded(ax, 0.025, 0.035, 0.95, 0.92, fc=OUTER, ec=INK, lw=0.9, r=0.04, z=-5)

    # Top workload strip.
    rounded(ax, 0.065, 0.835, 0.11, 0.085, "User task", PEACH, PEACH_D,
            fs=7.6, weight="bold")
    ax.text(0.245, 0.89, "Plan & sample", ha="center", va="center",
            fontsize=8.0, weight="bold")
    arr(ax, (0.175, 0.875), (0.345, 0.875), INK, lw=1.0)
    data_ops(ax, 0.365, 0.835)
    ax.text(0.615, 0.812, "candidate data operations", ha="center", va="center", fontsize=6.8)

    # Main framework boundary.
    frame(ax, 0.055, 0.105, 0.89, 0.67, "BranchLab Transaction Management Framework",
          fc="none", dashed=True, title_y=0.765, title_fs=9.1)

    # Left: speculative manager.
    frame(ax, 0.075, 0.155, 0.41, 0.53, "Speculative Transaction Manager",
          fc=BLUE, dashed=False, title_y=0.655, title_fs=8.1)
    rounded(ax, 0.11, 0.535, 0.34, 0.075, "Shared Prefix Executor", fc=GRAY, ec=EDGE,
            fs=7.4, weight="bold")
    ax.text(0.28, 0.505, "one dialogue + deterministic reads", ha="center", fontsize=6.3)
    rounded(ax, 0.11, 0.405, 0.34, 0.065, "Fork Controller  ·  first write intent",
            fc="white", ec=EDGE, fs=6.8)
    arr(ax, (0.28, 0.535), (0.28, 0.475), BLUE_D)

    # Fork branches.
    branch_x = [0.105, 0.235, 0.365]
    for i, x in enumerate(branch_x, 1):
        fc, ec = (GREEN, GREEN_D) if i == 2 else (GRAY, GRAY_D)
        rounded(ax, x, 0.245, 0.105, 0.105, f"Branch {i}\nprivate state", fc, ec, fs=6.6)
        arr(ax, (0.28, 0.405), (x + 0.0525, 0.35), BLUE_D, rad=(x - 0.235) * 0.7)
    ax.text(0.28, 0.205, "isolated continuations · select one winner", ha="center", fontsize=6.4)

    # Right top: state tracker.
    ax.add_patch(Rectangle((0.525, 0.535), 0.38, 0.14, facecolor=PEACH,
                           edgecolor=EDGE, linewidth=0.85))
    ax.text(0.715, 0.65, "Unified State Tracker", ha="center", va="center",
            fontsize=8.0, weight="bold")
    for x, txt, color in [
        (0.545, "Data\nstate", PEACH_D),
        (0.665, "Branch\nstate", BLUE_D),
        (0.785, "Task\nsemantics", PURPLE_D),
    ]:
        rounded(ax, x, 0.555, 0.10, 0.065, txt, "white", color, fs=6.5)

    # Right bottom: semantic engine.
    ax.add_patch(Rectangle((0.525, 0.16), 0.38, 0.32, facecolor=GREEN,
                           edgecolor=EDGE, linewidth=0.85))
    ax.text(0.715, 0.455, "Semantic Concurrency-Control Engine",
            ha="center", va="center", fontsize=8.0, weight="bold")
    rounded(ax, 0.55, 0.35, 0.14, 0.07, "LLM task\nclauses", PURPLE, PURPLE_D, fs=6.5)
    rounded(ax, 0.74, 0.35, 0.14, 0.07, "Operation\nsafety floor", PEACH, PEACH_D, fs=6.5)
    rounded(ax, 0.55, 0.235, 0.14, 0.07, "Contract\nbinder", GRAY, EDGE, fs=6.5)
    rounded(ax, 0.74, 0.235, 0.14, 0.07, "Deterministic\nvalidator", "white", GREEN_D,
            fs=6.5, weight="bold")
    arr(ax, (0.62, 0.35), (0.62, 0.305), PURPLE_D)
    arr(ax, (0.81, 0.35), (0.81, 0.305), PEACH_D)
    arr(ax, (0.69, 0.27), (0.74, 0.27), INK)

    # Cross-module signals.
    arr(ax, (0.485, 0.59), (0.525, 0.59), BLUE_D)
    line_label(ax, 0.505, 0.615, "observations", BLUE_D, 5.9)
    arr(ax, (0.525, 0.445), (0.485, 0.445), GREEN_D)
    line_label(ax, 0.505, 0.42, "fork / commit", GREEN_D, 5.9)
    arr(ax, (0.715, 0.535), (0.715, 0.48), PEACH_D)
    line_label(ax, 0.76, 0.505, "state", PEACH_D, 5.9)

    # Bottom accesses.
    for x in (0.18, 0.27, 0.36):
        arr(ax, (x, 0.155), (x, 0.075), INK)
    ax.text(0.27, 0.125, "shared / private data access", ha="center", va="center", fontsize=6.3)
    arr(ax, (0.81, 0.235), (0.81, 0.075), GREEN_D)
    ax.text(0.855, 0.12, "validated\ncommit", ha="center", va="center", fontsize=6.2,
            color=GREEN_D)
    rounded(ax, 0.425, 0.045, 0.27, 0.055, "Database  ·  tools  ·  audit log",
            "white", EDGE, fs=6.8, weight="bold")

    save(fig, "fig-r1-overall-architecture")


def branch_execution():
    fig, ax = canvas((7.05, 3.85))
    rounded(ax, 0.025, 0.035, 0.95, 0.92, fc=OUTER, ec=INK, lw=0.9, r=0.04, z=-5)
    ax.text(0.50, 0.915, "Shared-Prefix Execution and Isolated Branching",
            ha="center", va="center", fontsize=9.3, weight="bold")

    frame(ax, 0.06, 0.13, 0.25, 0.68, "Shared Prefix Manager", fc=BLUE,
          dashed=False, title_y=0.775, title_fs=8.0)
    rounded(ax, 0.085, 0.63, 0.20, 0.075, "Common dialogue", "white", BLUE_D, fs=7.0)
    rounded(ax, 0.085, 0.50, 0.20, 0.075, "Read-only tool calls", "white", BLUE_D, fs=7.0)
    rounded(ax, 0.085, 0.37, 0.20, 0.075, "Snapshot-aware cache", "white", BLUE_D, fs=7.0)
    rounded(ax, 0.085, 0.22, 0.20, 0.085, "Fork trigger\nfirst write intent", PEACH, PEACH_D, fs=6.7,
            weight="bold")
    for ya, yb in [(0.63, 0.575), (0.50, 0.445), (0.37, 0.305)]:
        arr(ax, (0.185, ya), (0.185, yb), BLUE_D)

    frame(ax, 0.355, 0.13, 0.37, 0.68, "Branch Execution Pool", fc="none",
          dashed=True, title_y=0.775, title_fs=8.0)
    ys = [0.60, 0.44, 0.28]
    for i, y in enumerate(ys, 1):
        fc, ec = (GREEN, GREEN_D) if i == 2 else (GRAY, GRAY_D)
        rounded(ax, 0.385, y, 0.13, 0.09, f"LLM\ncontinuation {i}", fc, ec, fs=6.4)
        rounded(ax, 0.56, y, 0.13, 0.09, "Private messages\n+ write set", fc, ec, fs=6.2)
        arr(ax, (0.515, y + 0.045), (0.56, y + 0.045), ec)
        arr(ax, (0.285, 0.26), (0.385, y + 0.045), BLUE_D, rad=(y - 0.44) * 0.35)

    frame(ax, 0.765, 0.13, 0.18, 0.68, "Resolution", fc=GREEN,
          dashed=False, title_y=0.775, title_fs=8.0)
    rounded(ax, 0.79, 0.58, 0.13, 0.09, "Candidate\nscoring", "white", GREEN_D, fs=6.7)
    rounded(ax, 0.79, 0.42, 0.13, 0.09, "Winner\nselection", "white", GREEN_D, fs=6.7, weight="bold")
    rounded(ax, 0.79, 0.25, 0.13, 0.10, "Validate +\nmaterialize", "white", GREEN_D, fs=6.7,
            weight="bold")
    arr(ax, (0.855, 0.58), (0.855, 0.515), GREEN_D)
    arr(ax, (0.855, 0.42), (0.855, 0.355), GREEN_D)
    for y in ys:
        arr(ax, (0.69, y + 0.045), (0.79, 0.625), GRAY_D, rad=(0.44 - y) * 0.5)

    ax.add_patch(Rectangle((0.35, 0.055), 0.38, 0.055, facecolor=PEACH,
                           edgecolor=EDGE, linewidth=0.8))
    ax.text(0.54, 0.082, "Branch table: parent · snapshot · status · private namespace",
            ha="center", va="center", fontsize=6.5)
    arr(ax, (0.54, 0.13), (0.54, 0.11), PEACH_D)
    ax.text(0.855, 0.075, "winner only", ha="center", fontsize=6.2, color=GREEN_D, weight="bold")
    arr(ax, (0.855, 0.25), (0.855, 0.10), GREEN_D)

    save(fig, "fig-r2-shared-prefix-branching")


def semantic_engine():
    fig, ax = canvas((7.05, 3.85))
    rounded(ax, 0.025, 0.035, 0.95, 0.92, fc=OUTER, ec=INK, lw=0.9, r=0.04, z=-5)
    ax.text(0.50, 0.915, "Semantic Contract Engine",
            ha="center", va="center", fontsize=9.3, weight="bold")

    # Top inputs.
    rounded(ax, 0.06, 0.77, 0.18, 0.085, "Task context", BLUE, BLUE_D, fs=7.2, weight="bold")
    rounded(ax, 0.31, 0.77, 0.18, 0.085, "Target write", BLUE, BLUE_D, fs=7.2, weight="bold")
    rounded(ax, 0.56, 0.77, 0.18, 0.085, "Operation policy", PEACH, PEACH_D, fs=7.2, weight="bold")
    rounded(ax, 0.81, 0.77, 0.13, 0.085, "Current state", PEACH, PEACH_D, fs=7.0, weight="bold")

    frame(ax, 0.06, 0.17, 0.36, 0.51, "Contract Compilation", fc=PURPLE,
          dashed=False, title_y=0.645, title_fs=8.0)
    rounded(ax, 0.09, 0.49, 0.14, 0.09, "LLM clause\nextractor", "white", PURPLE_D, fs=6.7)
    rounded(ax, 0.255, 0.49, 0.135, 0.09, "Safety-floor\nregistry", PEACH, PEACH_D, fs=6.7)
    rounded(ax, 0.09, 0.285, 0.30, 0.125,
            "Contract hardener\nschema check\n+ non-removable predicates",
            "white", EDGE, fs=6.0, weight="bold")
    rounded(ax, 0.09, 0.19, 0.30, 0.065,
            "authorization · dependencies\ntolerances · effects",
            GRAY, GRAY_D, fs=5.8)
    arr(ax, (0.15, 0.77), (0.16, 0.58), BLUE_D)
    arr(ax, (0.40, 0.77), (0.20, 0.58), BLUE_D, rad=0.12)
    arr(ax, (0.65, 0.77), (0.322, 0.58), PEACH_D, rad=-0.10)
    arr(ax, (0.16, 0.49), (0.19, 0.41), PURPLE_D)
    arr(ax, (0.322, 0.49), (0.29, 0.41), PEACH_D)

    # Trust boundary.
    ax.plot([0.46, 0.46], [0.12, 0.71], color=RED_D, lw=0.9, linestyle=(0, (4, 3)))
    ax.text(0.445, 0.13, "LLM proposal", ha="right", va="center", fontsize=6.2, color=RED_D)
    ax.text(0.475, 0.13, "trusted runtime", ha="left", va="center", fontsize=6.2, color=GREEN_D)

    frame(ax, 0.50, 0.17, 0.44, 0.51, "Deterministic Commit Protocol", fc=GREEN,
          dashed=False, title_y=0.645, title_fs=8.0)
    rounded(ax, 0.53, 0.475, 0.17, 0.115,
            "Runtime binder\nbranch · snapshot\nop · args",
            "white", EDGE, fs=6.1)
    rounded(ax, 0.75, 0.49, 0.16, 0.09, "Predicate checker\nlatest DB state",
            "white", GREEN_D, fs=6.4, weight="bold")
    rounded(ax, 0.53, 0.30, 0.17, 0.09, "Benign change\nREBASE + COMMIT",
            "white", GREEN_D, fs=6.4, weight="bold")
    rounded(ax, 0.75, 0.30, 0.16, 0.09, "Harmful change\nREJECT / REPLAN",
            RED, RED_D, fs=6.4, weight="bold")
    rounded(ax, 0.61, 0.205, 0.20, 0.05, "audit: evidence + decision", GRAY, GRAY_D, fs=6.2)
    arr(ax, (0.39, 0.355), (0.53, 0.535), PURPLE_D)
    arr(ax, (0.70, 0.535), (0.75, 0.535), INK)
    arr(ax, (0.875, 0.77), (0.83, 0.58), PEACH_D)
    arr(ax, (0.83, 0.49), (0.615, 0.39), GREEN_D, rad=0.10)
    arr(ax, (0.83, 0.49), (0.83, 0.39), RED_D)
    arr(ax, (0.615, 0.30), (0.68, 0.255), GREEN_D)
    arr(ax, (0.83, 0.30), (0.75, 0.255), RED_D)

    save(fig, "fig-r3-semantic-contract-engine")


def end_to_end_example():
    fig, ax = canvas((7.05, 3.95))
    rounded(ax, 0.025, 0.035, 0.95, 0.92, fc=OUTER, ec=INK, lw=0.9, r=0.04, z=-5)
    ax.text(0.50, 0.92, "End-to-End Example: Update a Passenger Name",
            ha="center", va="center", fontsize=9.3, weight="bold")

    # Shared phase.
    frame(ax, 0.055, 0.18, 0.25, 0.62, "Shared Phase", fc=BLUE,
          dashed=False, title_y=0.765, title_fs=8.0)
    rounded(ax, 0.08, 0.63, 0.20, 0.075, "Read user + order", "white", BLUE_D, fs=6.9)
    rounded(ax, 0.08, 0.50, 0.20, 0.075, "Check policy", "white", BLUE_D, fs=6.9)
    rounded(ax, 0.08, 0.37, 0.20, 0.075, "Ask confirmation", "white", BLUE_D, fs=6.9)
    rounded(ax, 0.08, 0.23, 0.20, 0.085, "Write intent\nMei Lee → Mei Garcia", PEACH, PEACH_D,
            fs=6.6, weight="bold")
    for ya, yb in [(0.63, 0.575), (0.50, 0.445), (0.37, 0.315)]:
        arr(ax, (0.18, ya), (0.18, yb), BLUE_D)

    # Semantic contract.
    frame(ax, 0.35, 0.18, 0.28, 0.62, "Compiled Contract", fc=PURPLE,
          dashed=False, title_y=0.765, title_fs=8.0)
    clauses = [
        (0.375, 0.62, "Authorization", "user confirmed"),
        (0.375, 0.50, "Hard predicates", "owned · active · same count"),
        (0.375, 0.38, "Dependencies", "owner · status · passengers"),
        (0.375, 0.26, "Bound write", "branch · snapshot · exact args"),
    ]
    for x, y, head, body in clauses:
        rounded(ax, x, y, 0.23, 0.075, f"{head}\n{body}", "white", PURPLE_D, fs=6.0)
    arr(ax, (0.28, 0.275), (0.375, 0.295), PURPLE_D)

    # Concurrent outcomes.
    frame(ax, 0.675, 0.18, 0.27, 0.62, "Concurrent Change", fc="none",
          dashed=True, title_y=0.765, title_fs=8.0)
    rounded(ax, 0.70, 0.59, 0.22, 0.10, "Phone number changes\nnot a task dependency",
            GREEN, GREEN_D, fs=6.5)
    rounded(ax, 0.70, 0.45, 0.22, 0.075, "REBASE + COMMIT", "white", GREEN_D,
            fs=6.8, weight="bold")
    arr(ax, (0.81, 0.59), (0.81, 0.53), GREEN_D)

    rounded(ax, 0.70, 0.29, 0.22, 0.10, "Order becomes cancelled\nhard predicate violated",
            RED, RED_D, fs=6.5)
    rounded(ax, 0.70, 0.205, 0.22, 0.055, "REJECT + REPLAN", "white", RED_D,
            fs=6.8, weight="bold")
    arr(ax, (0.81, 0.29), (0.81, 0.265), RED_D)

    arr(ax, (0.605, 0.56), (0.70, 0.64), GREEN_D)
    arr(ax, (0.605, 0.38), (0.70, 0.34), RED_D)
    line_label(ax, 0.655, 0.56, "validate", GREEN_D, 6.0)
    line_label(ax, 0.655, 0.365, "validate", RED_D, 6.0)

    ax.text(0.50, 0.105,
            "The commit decision depends on task predicates—not on whether any physical version changed.",
            ha="center", va="center", fontsize=7.0, weight="bold")

    save(fig, "fig-r4-passenger-update-example")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    overall_architecture()
    branch_execution()
    semantic_engine()
    end_to_end_example()
    print(f"Generated reference-style figures in {OUT}")
