"""Vector store implementations using ChromaDB and FAISS."""

import os
import faiss
import chromadb
import numpy as np
from truth_mirror.embeddings import get_gemini_embedding

class VectorStore:
    def __init__(self, backend: str = "chroma", collection_name: str = "truth_mirror", persist_dir: str = "./.chroma"):
        self.backend = backend
        self.dimension = 768
        
        if self.backend == "chroma":
            self.client = chromadb.PersistentClient(path=persist_dir)
            self.collection = self.client.get_or_create_collection(name=collection_name)
        elif self.backend == "faiss":
            self.index = faiss.IndexFlatL2(self.dimension)
            self.docs = []
            self.ids = []
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def store(self, doc_id: str, text: str, metadata: dict = None):
        if metadata is None:
            metadata = {}
            
        if self.backend == "chroma":
            embedding = get_gemini_embedding(text)
            self.collection.add(
                documents=[text],
                embeddings=[embedding],
                metadatas=[metadata],
                ids=[doc_id]
            )
        elif self.backend == "faiss":
            if self.exists(doc_id):
                return
            embedding = get_gemini_embedding(text)
            self.index.add(np.array([embedding]).astype("float32"))
            self.docs.append({"text": text, "metadata": metadata})
            self.ids.append(doc_id)

    def search(self, query: str, top_k: int = 5):
        if self.backend == "chroma":
            embedding = get_gemini_embedding(query)
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=top_k
            )
            return results
        elif self.backend == "faiss":
            if self.index.ntotal == 0:
                return []
            embedding = get_gemini_embedding(query)
            distances, indices = self.index.search(np.array([embedding]).astype("float32"), top_k)
            
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
