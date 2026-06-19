"""
Module Clustering
Based on van Eck et al. (2016) - Segment 3-B

reads segments from segments,jsonl, clusters them with k-means algorithm on their numercial
features and saves the cluster centroids as well as derived thresholds in thresholds.json.

Sensortyp agnostic: features are recognized automatically from the segments (based on fields ending with _value).

Interpretation of Clusters has to be done manually in cluster_activity_mapping file #Link here

Usage:
    python cluster.py segments.jsonl thresholds.json 4

    thresholds.json being the output file and
    4 being the number of clusters for k means

"""

import argparse
import json
import sys

# ----------------------------------
# load
# --------------------------


def load_segments(filepath: str) -> list[dict]:
    """Load segments out of json"""
    segments = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line:
                segments.append(json.loads(line))
    print(f"loaded: {len(segments)} segments from {filepath}")
    return segments


# ---------------------------
#  Features
# ---------------------------


def detect_feature_keys(segments: list[dict]) -> list[str]:
    """
    if no segments are in the file an empty list will be returned
    detects feature keys like median_value_r, median_value_b so on
    """
    if not segments:
        return []

    keys = [
        k
        for k, v in segments[0].items()
        if k.startswith("median_value") and isinstance(v, (int, float))
    ]

    print(f"features: {keys}")
    return keys


def cluster_segments(
    segments: list[dict], feature_keys: list[str], n_clusters: int = 4
):

    # extract features
    features = []
    for seg in segments:
        features.append([seg[k] for k in feature_keys])

    centroids = _kmeans(features, n_clusters, max_iter=100)

    assignments = []
    for feat in features:
        distances = [_dist(feat, c) for c in centroids]
        assignments.append(distances.index(min(distances)))

    return centroids, assignments


def _dist(a, b):
    """eucledean distance"""
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _kmeans(data, k, max_iter=100):
    """simple k means implementation without external dependencies"""
    import random

    random.seed(42)
    centroids = random.sample(data, min(k, len(data)))
    centroids = [list(c) for c in centroids]

    for _ in range(max_iter):
        clusters = [[] for _ in range(k)]
        for point in data:
            distances = [_dist(point, c) for c in centroids]
            clusters[distances.index(min(distances))].append(point)

        # calculate new centroids
        new_centroids = []
        for i, cluster in enumerate(clusters):
            if cluster:
                new_centroids.append(
                    [
                        sum(p[j] for p in cluster) / len(cluster)
                        for j in range(len(cluster[0]))
                    ]
                )
            else:
                new_centroids.append(centroids[i])

        # check divergence
        if new_centroids == centroids:
            break
        centroids = new_centroids

    return centroids


# ----------
# Threshold calculation
# ----------


def derive_thresholds(centroids, assignments, feature_keys, delta) -> dict:
    """
    dervive thresholds from clusters
    values are calculated based on the ranges of the cluster centroids
    """

    n_clusters = len(centroids)
    if n_clusters < 2:
        raise ValueError("At least 2 cluster needed for threshold calculation")

    cluster_info = []

    for i, centroid in enumerate(centroids):
        cluster_info.append(
            {
                "cluster_id": i,
                "count": assignments.count(i),
                "centroid": {
                    feature_keys[j]: round(centroid[j], 4)
                    for j in range(len(feature_keys))
                },
            }
        )
    # thresholds: center between two cluster centroids
    # on the frist feature
    primary_feature = feature_keys[0]
    sorted_clusters = sorted(cluster_info, key=lambda c: c["centroid"][primary_feature])

    thresholds = []
    for i in range(len(sorted_clusters) - 1):
        if delta:
            delta_per_unit = round(
                sorted_clusters[i + 1]["centroid"][primary_feature]
                - sorted_clusters[i]["centroid"][primary_feature],
                4,
            )
            thresholds.append(
                {
                    "between_clusters": [
                        sorted_clusters[i]["cluster_id"],
                        sorted_clusters[i + 1]["cluster_id"],
                    ],
                    "feature": primary_feature,
                    "delta_per_unit": delta_per_unit,
                }
            )
        else:
            low = sorted_clusters[i]["centroid"][primary_feature]
            high = sorted_clusters[i + 1]["centroid"][primary_feature]
            thresholds.append(
                {
                    "between_clusters": [
                        sorted_clusters[i]["cluster_id"],
                        sorted_clusters[i + 1]["cluster_id"],
                    ],
                    "feature": primary_feature,
                    "threshold": round((low + high) / 2, 4),
                }
            )

    return {
        "feature_keys": feature_keys,
        "clusters": cluster_info,
        "thresholds": thresholds,
    }


def save_thresholds(thresholds: dict, filepath: str = "thresholds.json"):
    """Save thresholds into JSON."""
    with open(filepath, "w") as f:
        json.dump(thresholds, f, indent=2)
    print(f"\n Thresholds saved to: {filepath}")
    print(f"  {len(thresholds['clusters'])} Cluster")
    print(f"  {len(thresholds['thresholds'])} Thresholds")
    print(f"  Features: {thresholds['feature_keys']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # ----------------------------------
    # Initialise parser for command line input
    # --------------------------

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--delta",
        action="store_true",
        help="For using Sensors with specific deltas. eg. consistent weights",
    )
    parser.add_argument(
        "n_cluster", type=int, help="sets number of clusters/ activities for a sensor"
    )
    parser.add_argument(
        "input", help="which input file should be used for calibration?"
    )
    parser.add_argument("output", help="where should the output go?")
    args = parser.parse_args()

    segments_file = args.input
    output_file = args.output
    n_clusters = args.n_cluster
    delta = args.delta

    # 1. load segments
    segments = load_segments(segments_file)
    feature_keys = detect_feature_keys(segments)

    if not feature_keys:
        print("Error: no numerical features found in Segments.")
        sys.exit(1)

    # 2. clustering
    print(f"\nClustering with k = {n_clusters} ...")
    centroids, assignments = cluster_segments(segments, feature_keys, n_clusters)

    thresholds = derive_thresholds(centroids, assignments, feature_keys, delta)
    save_thresholds(thresholds, output_file)
