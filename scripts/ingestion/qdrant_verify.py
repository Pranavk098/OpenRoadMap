from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)

print("\n=== Collections ===")
print(client.get_collections())

print("\n=== Count ===")
try:
    print(client.count(collection_name="educational_resources"))
except Exception as e:
    print("Error counting collection:", e)
