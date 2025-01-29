
from tinydb import TinyDB, Query
import faiss
import numpy as np
from typing import List

from llm_utils import get_text_embedding
from agent import Episode

class MemoryController:
    def __init__(self):
        self.memory_index = MemoryIndex()
        self.embeddings_store = EmbeddingsStore()
        self.current_episode_store = TinyDB('current_episode_store.json')  # Separate store for incomplete episodes

    def save_current_episode(self, episode):
        """Save the current (incomplete) episode to the current_episode_store."""
        episode_dict = episode.to_dict()
        self.current_episode_store.insert(episode_dict)

    def finalize_current_episode(self, episode):
        """Finalize the current episode by moving it to the main memory index and generating an embedding."""
        # Save the finalized episode to the main memory index
        episode_dict = episode.to_dict()
        episode_id = self.memory_index.save_episode(episode_dict)
        
        # Generate an embedding for the finalized episode
        episode_str = str(episode)  # Use string representation for embedding
        embedding = get_text_embedding(episode_str)
        
        # Save the embedding to the embeddings store
        self.embeddings_store.save_embedding(embedding, episode_id)
        
        # Remove the episode from the current_episode_store using its unique_id
        self.current_episode_store.remove(Query().unique_id == episode.unique_id)

    def get_current_episode(self):
        """Retrieve the current (incomplete) episode."""
        current_episode_dict = self.current_episode_store.all()
        if current_episode_dict:
            return Episode(**current_episode_dict[0])  # Deserialize the dictionary back into an Episode object
        return None
    
    

class MemoryIndex:
    def __init__(self, db_path='memory_index.json'):
        self.db = TinyDB(db_path)
        self.EpisodeQuery = Query()

    def save_episode(self, episode_dict):
        """Save the episode dictionary to the database."""
        return self.db.insert(episode_dict)

    def get_episode(self, episode_id):
        """Retrieve an episode by its ID and return it as a dictionary."""
        return self.db.get(doc_id=episode_id)

    def search_episodes(self, query):
        """Search for episodes based on a query."""
        return self.db.search(self.EpisodeQuery.episode.search(query))

    def get_all_episodes(self):
        """Retrieve all episodes from the database."""
        return self.db.all()
    


class EmbeddingsStore:
    def __init__(self, index_path='faiss_index.bin', dimension=768):
        self.dimension = dimension
        self.index_path = index_path
        try:
            self.index = faiss.read_index(index_path)
        except:
            self.index = faiss.IndexFlatL2(dimension)

    def save_embedding(self, embedding, episode_id):
        """Save an embedding to the FAISS index."""
        embedding_array = np.array([embedding]).astype('float32')
        self.index.add(embedding_array)
        faiss.write_index(self.index, self.index_path)

    def get_similar_episodes(self, embedding, best_k=5):
        """Retrieve the most similar episodes based on the embedding."""
        embedding_array = np.array([embedding]).astype('float32')
        distances, indices = self.index.search(embedding_array, best_k)
        return indices[0]