from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
idx = pc.Index("myhr-interviews")

namespaces = list(idx.describe_index_stats()["namespaces"].keys())
print(f"Found {len(namespaces)} namespaces total.")

to_delete = namespaces[:50]  # delete the oldest 50, keep the newest 50
print(f"Deleting {len(to_delete)} namespaces...")

for ns in to_delete:
    idx.delete(delete_all=True, namespace=ns)
    print(f"  deleted: {ns}")

print(f"Done. {len(namespaces) - len(to_delete)} namespaces remaining.")
