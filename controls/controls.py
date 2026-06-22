from sentence_transformers import SentenceTransformer
import chromadb, json

_model = SentenceTransformer("all-MiniLM-L6-v2")   # local, free, 384-dim
_col = chromadb.PersistentClient(path="./chroma").get_or_create_collection("controls")

def index_controls(path="controls/controls.json"):
    controls = json.load(open(path))
    _col.upsert(
        ids=[c["id"] for c in controls],
        embeddings=_model.encode([c["text"] for c in controls]).tolist(),
        documents=[c["text"] for c in controls],
        metadatas=[{"title": c["title"], "source": c["source"]} for c in controls],
    )

if __name__ == "__main__":
    index_controls()