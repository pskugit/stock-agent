
from tinydb import TinyDB, Query
import faiss
import numpy as np
from pathlib import Path
import os
import json
from llm_utils import get_text_embedding
from memory.memorymodel import Episode

class MemoryController:
    def __init__(self, agent_name: str):
        self.local_path = Path("agents") / agent_name
        os.makedirs(self.local_path, exist_ok = True)
        self.memory_index = MemoryIndex(db_path= self.local_path / "memory_index.json")
        self.embeddings_store = EmbeddingsStore(index_path= self.local_path / "faiss_index.bin")
        self.current_episode_store = TinyDB(self.local_path  / 'current_episode_store.json')  # Separate store for incomplete episodes

    def save_current_episode(self, episode):
        """Save the current (incomplete) episode to the current_episode_store."""
        episode_dict = json.loads(episode.model_dump_json())
        self.current_episode_store.insert(episode_dict)

    def save_finished_episode(self, episode, remove_current=True):
        """Finalize the current episode by moving it to the main memory index and generating an embedding."""
        # Save the finalized episode to the main memory index
        episode_id = self.memory_index.save_episode(episode)
        
        # Generate an embedding for the finalized episode
        episode_str = str(episode)  # Use string representation for embedding
        embedding = get_text_embedding(episode_str)
        
        # Save the embedding to the embeddings store
        self.embeddings_store.save_embedding(embedding, episode_id)
        
        # Remove all episodes from the current_episode_store using truncate
        if remove_current:
            self.current_episode_store.truncate() #remove(Query().unique_id == episode.unique_id)

    def get_current_episode(self):
        """Retrieve the current (incomplete) episode."""
        current_episode_dict = self.current_episode_store.all()
        if current_episode_dict:
            return Episode.model_validate(current_episode_dict[-1])  # Deserialize the dictionary back into an Episode object
        return None
    
    def get_similar_episodes(self, episode, best_k = 5):
        if not self.get_memory_count():
            return None
        embedding = get_text_embedding(str(episode))
        episode_ids, distances = self.embeddings_store.get_similar_embeddings(embedding, best_k)
        episodes = [Episode.model_validate(self.memory_index.get_episode(episode_id)) for episode_id in episode_ids]
        return episodes
    
    def get_memory_count(self):
        return len(self.memory_index.db)


class MemoryIndex:
    def __init__(self, db_path='memory_index.json'):
        self.db = TinyDB(db_path)
        self.EpisodeQuery = Query()

    def save_episode(self, episode):
        """Save the episode dictionary to the database."""
        episode_dict = json.loads(episode.model_dump_json())
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
    
    def truncate(self):
        return self.db.truncate()
    

class EmbeddingsStore:
    def __init__(self, index_path='faiss_index.bin', dimension=1536):
        self.dimension = dimension
        self.index_path = index_path
        try:
            self.index = faiss.read_index(str(index_path))
            print(f"EmbeddingsStore: loading existing faiss index from {index_path}")
        except:
            print(f"EmbeddingsStore: creating new faiss index")
            self.index = faiss.IndexFlatL2(dimension)
            self.index = faiss.IndexIDMap(self.index)            

    def save_embedding(self, embedding, episode_id):
        """Save an embedding to the FAISS index."""
        embedding_array = np.array([embedding])
        self.index.add_with_ids(embedding_array, episode_id)
        faiss.write_index(self.index, str(self.index_path))

    def get_similar_embeddings(self, embedding, best_k=5):
        """Retrieve the most similar episodes based on the embedding."""
        embedding_array = np.array([embedding]).astype('float32')
        distances, episode_id = self.index.search(embedding_array, best_k)
        return episode_id[0], distances[0]
    
