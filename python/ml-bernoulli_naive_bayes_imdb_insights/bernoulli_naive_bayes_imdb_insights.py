#!/usr/bin/env python3
"""
imdb_nb_insights.py

Train an interpretable Naive Bayes model on your IMDb ratings export to surface
"what features correlate with my 9–10s".

Works with the labeled CSV created by this assistant:
  imdb-ratings-021626-labeled.csv

Usage:
  python imdb_nb_insights.py --csv imdb-ratings-021626-labeled.csv --label label_9_10_vs_all
  python imdb_nb_insights.py --csv imdb-ratings-021626-labeled.csv --label label_strict_9_10_vs_1_6 --drop-na

Notes:
- BernoulliNB expects binary features; this script uses one-hot/binary buckets for everything.
- The "strict" label (9–10 vs 1–6, dropping 7–8) can be very imbalanced if you rarely rate <=6.
  For modeling, label_9_10_vs_all is usually more stable.
"""

from __future__ import annotations
import argparse
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np, inspect
"""
Use Python introspection to find where a function comes from
print(np.dot)
print(inspect.getsourcefile(np.dot))
or
print(inspect.getsource(np.linalg.lstsq))
"""
import pandas as pd
from sklearn.naive_bayes import BernoulliNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score, classification_report
from sklearn.preprocessing import MultiLabelBinarizer

# ----------------------------
# Feature engineering helpers
# ----------------------------

def _clean_str(x: object) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()

def make_runtime_bucket(runtime_mins: float) -> str:
    if pd.isna(runtime_mins):
        return "runtime_unknown"
    r = float(runtime_mins)
    if r < 85:
        return "runtime_<85"
    if r < 100:
        return "runtime_85_99"
    if r < 121:
        return "runtime_100_120"
    if r < 151:
        return "runtime_121_150"
    return "runtime_151_plus"

def make_decade(year: float) -> str:
    if pd.isna(year):
        return "decade_unknown"
    y = int(year)
    d = (y // 10) * 10
    return f"decade_{d}s"

def bucket_imdb_rating(x: float) -> str:
    if pd.isna(x):
        return "imdb_unknown"
    r = float(x)
    if r < 6.0:
        return "imdb_<6.0"
    if r < 7.0:
        return "imdb_6.0_6.9"
    if r < 7.5:
        return "imdb_7.0_7.4"
    if r < 8.0:
        return "imdb_7.5_7.9"
    if r < 8.5:
        return "imdb_8.0_8.4"
    return "imdb_8.5_plus"

def bucket_votes(x: float) -> str:
    if pd.isna(x):
        return "votes_unknown"
    v = float(x)
    if v < 2_000:
        return "votes_<2k"
    if v < 10_000:
        return "votes_2k_9k"
    if v < 50_000:
        return "votes_10k_49k"
    if v < 200_000:
        return "votes_50k_199k"
    return "votes_200k_plus"

def split_genres(s: object) -> List[str]:
    txt = _clean_str(s)
    if not txt:
        return []
    # IMDb export is often "Drama, Crime"
    parts = [p.strip() for p in txt.split(",") if p.strip()]
    return parts

def top_k_by_log_odds(feature_names: List[str], log_prob_pos: np.ndarray, log_prob_neg: np.ndarray, k: int = 20):
    # Positive signal: higher P(feature|pos) than P(feature|neg)
    lift = (log_prob_pos - log_prob_neg)
    idx_pos = np.argsort(lift)[::-1][:k]
    idx_neg = np.argsort(lift)[:k]
    return idx_pos, idx_neg, lift

# ----------------------------
# Build X matrix (binary)
# ----------------------------

@dataclass
class DesignMatrix:
    X: np.ndarray
    y: np.ndarray
    feature_names: List[str]
    rows: pd.DataFrame  # aligned rows (after filtering)

def build_design_matrix(df: pd.DataFrame, label_col: str, drop_na_label: bool) -> DesignMatrix:
    if label_col not in df.columns:
        raise ValueError(f"Label column '{label_col}' not found. Available: {list(df.columns)}")

    work = df.copy()

    # Label handling
    y = work[label_col]
    if drop_na_label:
        mask = ~pd.isna(y)
        work = work.loc[mask].copy()
        y = work[label_col]

    # Ensure binary y
    y = y.astype(int).to_numpy()

    # Core categorical features
    title_type = work["Title Type"].map(_clean_str).replace("", "type_unknown")
    decade = work["Year"].apply(make_decade)
    runtime_bucket = work["Runtime (mins)"].apply(make_runtime_bucket)

    # Optional metadata buckets (still "not much metadata", but low-effort and helpful)
    imdb_bucket = work["IMDb Rating"].apply(bucket_imdb_rating)
    votes_bucket = work["Num Votes"].apply(bucket_votes)

    # Multi-label genres
    genre_lists = work["Genres"].apply(split_genres).tolist()
    mlb = MultiLabelBinarizer(sparse_output=False)
    G = mlb.fit_transform(genre_lists)
    genre_names = [f"genre={g}" for g in mlb.classes_]

    # One-hot the small categorical fields ourselves (binary)
    def one_hot(series: pd.Series, prefix: str) -> Tuple[np.ndarray, List[str]]:
        cats = series.fillna("").astype(str).tolist()
        uniq = sorted(set(cats))
        mapping = {c: i for i, c in enumerate(uniq)}
        X = np.zeros((len(cats), len(uniq)), dtype=np.int8)
        for r, c in enumerate(cats):
            X[r, mapping[c]] = 1
        names = [f"{prefix}={c}" for c in uniq]
        return X, names

    X_type, names_type = one_hot(title_type, "type")
    X_dec, names_dec = one_hot(decade, "decade")
    X_run, names_run = one_hot(runtime_bucket, "runtime")
    X_imdb, names_imdb = one_hot(imdb_bucket, "imdb_bucket")
    X_votes, names_votes = one_hot(votes_bucket, "votes_bucket")

    # Combine
    X = np.concatenate([X_type, X_dec, X_run, X_imdb, X_votes, G], axis=1).astype(np.int8)
    feature_names = names_type + names_dec + names_run + names_imdb + names_votes + genre_names

    return DesignMatrix(X=X, y=y, feature_names=feature_names, rows=work)

# ----------------------------
# Explain a single title
# ----------------------------

def explain_title(model: BernoulliNB, dm: DesignMatrix, title_query: str, top_n: int = 12) -> None:
    q = title_query.strip().lower()
    candidates = dm.rows[dm.rows["Title"].astype(str).str.lower().str.contains(re.escape(q), na=False)]

    if candidates.empty:
        print(f"\nNo titles matched '{title_query}'. Try a shorter substring.")
        return

    # Pick the first match
    row = candidates.iloc[0]
    idx = candidates.index[0]
    # Index in dm.rows aligns with dm.X rows position
    pos = dm.rows.index.get_loc(idx)
    x = dm.X[pos:pos+1]

    proba = model.predict_proba(x)[0, 1]
    print(f"\nMatch: {row['Title']} ({row.get('Year', '')}) | Your Rating: {row.get('Your Rating', '')} | P(9–10)≈{proba:.3f}")

    # Contribution approximation via log odds lift
    # For BernoulliNB: log P(x|y) sums log_prob for present features and log(1-p) for absent features.
    # We'll show present features with largest (log_prob_pos - log_prob_neg).
    log_prob = model.feature_log_prob_  # shape (2, n_features)
    lift = log_prob[1] - log_prob[0]

    present = np.where(x[0] == 1)[0]
    present_sorted = present[np.argsort(lift[present])[::-1]]
    print("\nTop contributing present features:")
    for j in present_sorted[:top_n]:
        print(f"  + {dm.feature_names[j]:<28} lift={lift[j]:+.3f}")

# ----------------------------
# Main
# ----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to labeled IMDb CSV")
    ap.add_argument("--label", default="label_9_10_vs_all", help="Label column to use")
    ap.add_argument("--drop-na", action="store_true", help="Drop rows where label is NA (useful for strict label)")
    ap.add_argument("--test-size", type=float, default=0.20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--explain", type=str, default="", help="Substring of a title to explain after training")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    dm = build_design_matrix(df, label_col=args.label, drop_na_label=args.drop_na)

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        dm.X, dm.y, test_size=args.test_size, random_state=args.seed, stratify=dm.y
    )

    model = BernoulliNB(alpha=1.0)
    model.fit(X_train, y_train)

    # Evaluate
    p = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, p)
    ap_score = average_precision_score(y_test, p)
    print(f"\nRows used: {len(dm.y)} | Positive rate: {dm.y.mean():.3f}")
    print(f"AUC: {auc:.3f} | Avg Precision (PR-AUC): {ap_score:.3f}\n")
    print(classification_report(y_test, (p >= 0.5).astype(int), digits=3))

    # Top feature lifts
    log_prob = model.feature_log_prob_
    idx_pos, idx_neg, lift = top_k_by_log_odds(dm.feature_names, log_prob[1], log_prob[0], k=20)

    print("\nTop positive signals (more common in your 9–10s):")
    for i in idx_pos:
        print(f"  + {dm.feature_names[i]:<28} lift={lift[i]:+.3f}")

    print("\nTop negative signals (more common in your non-9–10s):")
    for i in idx_neg:
        print(f"  - {dm.feature_names[i]:<28} lift={lift[i]:+.3f}")

    if args.explain:
        explain_title(model, dm, args.explain)

if __name__ == "__main__":
    main()
