"""Centipede dedupe + root-cause clustering (Slice 08).

Groups FailureHarvestReceipts that share a root cause into stable
``RootCauseCluster.v1`` records. Source disagreement (lane-by-lane severity
or actual_result variance) is preserved on the cluster as
``severity_distribution`` / ``actual_result_distribution`` rather than
collapsed away.
"""

from failureforge.clustering.centipede import (
    build_clusters,
    build_fix_cluster_report,
    cluster_fingerprint,
    logical_attack_id,
    render_fix_cluster_markdown,
)

__all__ = [
    "build_clusters",
    "build_fix_cluster_report",
    "cluster_fingerprint",
    "logical_attack_id",
    "render_fix_cluster_markdown",
]
