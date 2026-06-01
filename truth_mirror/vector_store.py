"""Vector store implementations using ChromaDB and FAISS."""

import os
import faiss
import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer

class VectorStore:
    def __init__(self, backend: str = "chroma", collection_name: str = "truth_mirror", persist_dir: str = "./.chroma"):
        self.backend = backend
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        
        if self.backend == "chroma":
            self.client = chromadb.PersistentClient(path=persist_dir)
            self.collection = self.client.get_or_create_collection(name=collection_name)
        elif self.backend == "faiss":
            self.dimension = self.encoder.get_sentence_embedding_dimension()
            self.index = faiss.IndexFlatL2(self.dimension)
            self.docs = []
            self.ids = []
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def store(self, doc_id: str, text: str, metadata: dict = None):
        if metadata is None:
            metadata = {}
            
        if self.backend == "chroma":
            self.collection.add(
                documents=[text],
                metadatas=[metadata],
                ids=[doc_id]
            )
        elif self.backend == "faiss":
            if self.exists(doc_id):
                return
            embedding = self.encoder.encode([text])
            self.index.add(np.array(embedding).astype("float32"))
            self.docs.append({"text": text, "metadata": metadata})
            self.ids.append(doc_id)

    def search(self, query: str, top_k: int = 5):
        if self.backend == "chroma":
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )
            return results
        elif self.backend == "faiss":
            if self.index.ntotal == 0:
                return []
            embedding = self.encoder.encode([query])
            distances, indices = self.index.search(np.array(embedding).astype("float32"), top_k)
            
            results = []
            for j, i in enumerate(indices[0]):
                if i != -1 and i < len(self.docs):
                    res = {
                        "id": self.ids[i],
                        "text": self.docs[i]["text"],
                        "metadata": self.docs[i]["metadata"],
                        "distance": float(distances[0][j])
                    }
                    results.append(res)
            return results

    def exists(self, doc_id: str) -> bool:
        if self.backend == "chroma":
            res = self.collection.get(ids=[doc_id])
            return len(res["ids"]) > 0
        elif self.backend == "faiss":
            return doc_id in self.ids
