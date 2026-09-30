from pathlib import Path

import pandas as pd

JUDGED_PATH = Path("dataset/judged_variants.csv")

HUMAN_LABEL_PATHS = {
    "Velara": Path("human_labels/results_velara_human_judge.csv"),
    "Verdan": Path("human_labels/results_verdan_human_judge.csv"),
    "Riverbend Brewing Co.": Path("human_labels/results_riverbend_human_judge.csv"),
}

# Maps each human CSV column to its counterpart in judged_variants.csv.
CRITERION_MAP = {
    "Criterion 1 - Tone": "tone_pass",
    "Criterion 2 - Claims": "claims_pass",
    "Criterion 3 - CTA": "cta_pass",
    "Criterion 4 - Length": "length_pass",
    "Criterion 5 - Visual Fit": "visual_fit_pass",
}


def load_human_labels() -> pd.DataFrame:
    frames = []
    for brand, path in HUMAN_LABEL_PATHS.items():
        df = pd.read_csv(path)
        df["brand"] = brand
        frames.append(df)
    human = pd.concat(frames, ignore_index=True)

    # Human labels are "Pass"/"Fail" strings; judge labels are Python bools.
    # Convert here so every downstream comparison is bool == bool.
    for human_col in CRITERION_MAP:
        human[human_col] = human[human_col] == "Pass"

    return human


def compute_agreement() -> pd.DataFrame:
    judged = pd.read_csv(JUDGED_PATH)
    human = load_human_labels()

    merged = judged.merge(
        human[["brand", "variant_number", *CRITERION_MAP.keys()]],
        on=["brand", "variant_number"],
        how="inner",
    )
    assert len(merged) == len(judged), (
        f"expected all {len(judged)} judged rows to find a human-labeled match, "
        f"got {len(merged)} — check for brand-name or variant_number mismatches"
    )

    # ---- True per-criterion agreement, both directions, now that human
    # labels are structured the same way the judge's are. ----
    print(f"Per-criterion agreement across all {len(merged)} variants:\n")
    rows = []
    for human_col, judge_col in CRITERION_MAP.items():
        agree = (merged[human_col] == merged[judge_col]).mean()
        # judge said Fail, human said Pass -> judge is too strict on this row
        false_fail = ((merged[human_col]) & (~merged[judge_col])).sum()
        # judge said Pass, human said Fail -> judge is too lenient on this row
        false_pass = ((~merged[human_col]) & (merged[judge_col])).sum()
        rows.append(
            {
                "criterion": judge_col,
                "agreement": agree,
                "judge_too_strict": false_fail,
                "judge_too_lenient": false_pass,
            }
        )
        print(
            f"  {judge_col:18s} {agree:6.1%}   "
            f"judge-too-strict: {false_fail:2d}   judge-too-lenient: {false_pass:2d}"
        )
    print()

    summary = pd.DataFrame(rows).sort_values("agreement")
    print("Weakest criterion first:")
    print(summary.to_string(index=False))
    print()

    return merged


def show_disagreements(merged: pd.DataFrame) -> None:
    for human_col, judge_col in CRITERION_MAP.items():
        disagreements = merged[merged[human_col] != merged[judge_col]]
        if disagreements.empty:
            continue
        print(f"\n=== {judge_col}: {len(disagreements)} disagreeing variants ===")
        for _, row in disagreements.iterrows():
            verdict = (
                "human Pass, judge Fail (judge too strict)"
                if row[human_col]
                else "human Fail, judge Pass (judge too lenient)"
            )
            print(f"\n{row['brand']} v{row['variant_number']} — {verdict}")
            print(f"  Headline: {row['headline']}")
            if row["critique"]:
                print(f"  Judge critique: {row['critique']}")


if __name__ == "__main__":
    merged_df = compute_agreement()
    show_disagreements(merged_df)
