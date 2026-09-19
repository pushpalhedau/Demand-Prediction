from backend.core.request_context import tenant_context
from backend.ml.customer_segmentation import train_customer_segmentation
from backend.ml.lead_scoring import train_xgboost_pipeline


def train_tenant_models(tenant_id, log=print) -> dict:
    """(Re)train the per-tenant ML models from that tenant's own data."""
    results = {}
    with tenant_context(tenant_id):
        _, err = train_customer_segmentation(n_clusters=5)
        results["segmentation"] = err or "ok"
        _, err = train_xgboost_pipeline()
        results["lead_close"] = err or "ok"
    for k, v in results.items():
        log(f"  {k}: {v}")
    return results
