from app.retrieval import index_documents
if __name__ == "__main__":
    n=index_documents(recreate=True)
    print(f"Indexed {n} structurally chunked passages in Qdrant")
