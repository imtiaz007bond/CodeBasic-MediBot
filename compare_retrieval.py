"""Print dense-only versus hybrid retrieval results for screenshot/evaluation evidence.

Run inside the API container:
  docker compose exec api sh -lc 'PYTHONPATH=/app python /app/scripts/compare_retrieval.py --role nurse --query "How do I prevent ICU infections?"'
"""
import argparse
from qdrant_client import models
from app.retrieval import resources, _sparse, COLLECTION
from app.config import ROLE_COLLECTIONS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="nurse", choices=sorted(ROLE_COLLECTIONS))
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    qc, emb, reranker, sparse = resources()
    allowed = ROLE_COLLECTIONS[args.role]
    filt = models.Filter(must=[
        models.FieldCondition(key="access_roles", match=models.MatchAny(any=[args.role])),
        models.FieldCondition(key="collection", match=models.MatchAny(any=allowed)),
    ])
    dense = emb.encode(args.query, normalize_embeddings=True).tolist()
    dense_result = qc.query_points(collection_name=COLLECTION, query=dense, using="dense", query_filter=filt,
                                   limit=args.limit, with_payload=True)
    sp = _sparse(sparse, args.query)
    hybrid_result = qc.query_points(collection_name=COLLECTION, prefetch=[
        models.Prefetch(query=dense, using="dense", filter=filt, limit=args.limit),
        models.Prefetch(query=sp, using="bm25", filter=filt, limit=args.limit),
    ], query=models.FusionQuery(fusion=models.Fusion.RRF), limit=args.limit, with_payload=True)
    for label, result in (("DENSE ONLY", dense_result), ("HYBRID (DENSE + BM25 + RRF)", hybrid_result)):
        print(f"\\n=== {label} | role={args.role} | query={args.query!r} ===")
        for rank, point in enumerate(result.points, 1):
            payload = point.payload or {}
            # Defensive check also makes it obvious in evaluation output if payloads are malformed.
            if args.role not in payload.get("access_roles", []) or payload.get("collection") not in allowed:
                continue
            print(f"{rank}. score={point.score:.4f} | {payload.get('source_document')} | {payload.get('section_title')} | {payload.get('collection')}")

if __name__ == "__main__":
    main()
