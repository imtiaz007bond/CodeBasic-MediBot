"""Qdrant hybrid retrieval: dense + BM25 sparse vectors fused server-side with RRF.
The access_roles filter is applied to both prefetch branches before fusion."""
import os, uuid, re
from functools import lru_cache
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer, CrossEncoder
from .config import ROLE_COLLECTIONS
from .ingest import load_chunks

COLLECTION = os.getenv("QDRANT_COLLECTION", "medibot_chunks")
@lru_cache(maxsize=1)
def resources():
    url=os.getenv("QDRANT_URL", "http://localhost:6333")
    key=os.getenv("QDRANT_API_KEY") or None
    qc=QdrantClient(url=url, api_key=key)
    emb=SentenceTransformer(os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    rerank=CrossEncoder(os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"))
    try:
        from fastembed import SparseTextEmbedding
        sparse=SparseTextEmbedding(model_name="Qdrant/bm25")
    except Exception as e:
        raise RuntimeError("Install fastembed to create/query BM25 sparse vectors: pip install fastembed") from e
    return qc,emb,rerank,sparse

def _sparse(sparse, text):
    v=next(iter(sparse.query_embed(text)))
    return models.SparseVector(indices=list(v.indices), values=list(v.values))

def ensure_collection(recreate=False):
    qc,emb,_,sparse=resources(); dim=emb.get_sentence_embedding_dimension()
    exists=qc.collection_exists(COLLECTION)
    if exists and recreate: qc.delete_collection(COLLECTION); exists=False
    if not exists:
        qc.create_collection(collection_name=COLLECTION, vectors_config={"dense":models.VectorParams(size=dim,distance=models.Distance.COSINE)}, sparse_vectors_config={"bm25":models.SparseVectorParams(index=models.SparseIndexParams(on_disk=False), modifier=models.Modifier.IDF)})
        for field in ("access_roles","collection","source_document"):
            try: qc.create_payload_index(COLLECTION, field, models.PayloadSchemaType.KEYWORD)
            except Exception: pass
    return qc,emb,sparse

def index_documents(recreate=False):
    # Validate corpus before deleting/recreating any existing collection.
    chunks=load_chunks()
    if not chunks:
        raise RuntimeError("Document ingestion found zero chunks; refusing to create an empty Qdrant collection")
    qc,emb,sparse=ensure_collection(recreate)
    batch=32
    for start in range(0,len(chunks),batch):
        group=chunks[start:start+batch]
        dense=emb.encode([x["text"] for x in group], normalize_embeddings=True).tolist()
        points=[]
        for x,d in zip(group,dense):
            points.append(models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL,x["id"])), vector={"dense":d,"bm25":_sparse(sparse,x["text"])}, payload={**x["payload"],"text":x["text"],"chunk_id":x["id"]}))
        qc.upsert(collection_name=COLLECTION,points=points,wait=True)
    return len(chunks)

def retrieve(question: str, role: str, limit=10, rerank_limit=3):
    if role not in ROLE_COLLECTIONS: raise ValueError("Unknown role")
    qc,emb,reranker,sparse=resources()
    allowed=ROLE_COLLECTIONS[role]
    # Filter is enforced by Qdrant for BOTH dense and sparse prefetches, before RRF/LLM.
    filt=models.Filter(must=[models.FieldCondition(key="access_roles", match=models.MatchAny(any=[role])), models.FieldCondition(key="collection", match=models.MatchAny(any=allowed))])
    dense=emb.encode(question,normalize_embeddings=True).tolist()
    sp=_sparse(sparse,question)
    result=qc.query_points(collection_name=COLLECTION, prefetch=[
        models.Prefetch(query=dense,using="dense",filter=filt,limit=limit),
        models.Prefetch(query=sp,using="bm25",filter=filt,limit=limit),
    ], query=models.FusionQuery(fusion=models.Fusion.RRF), limit=limit, with_payload=True)
    candidates=[]
    for p in result.points:
        pl=p.payload or {}
        # Defense-in-depth: reject malformed or unauthorized payloads, never as a substitute for DB filter.
        if role not in pl.get("access_roles",[]) or pl.get("collection") not in allowed: continue
        candidates.append({"text":pl.get("text",""),"payload":pl,"score":p.score})
    if not candidates: return []
    scores=reranker.predict([(question,c["text"]) for c in candidates])
    ranked=sorted(zip(candidates,scores),key=lambda x:float(x[1]),reverse=True)[:rerank_limit]
    return [{**c,"rerank_score":float(s)} for c,s in ranked]
