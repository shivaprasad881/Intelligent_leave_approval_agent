import chromadb

client = chromadb.PersistentClient(path="./storage/chroma")
collection = client.get_collection("intellidesk_kb")

result = collection.get(include=["embeddings"])
print(len(result["embeddings"][0]))  # should print 384
print(result["embeddings"][0][:5])   # first 5 numbers of one vector

