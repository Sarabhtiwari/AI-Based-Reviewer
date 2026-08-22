from app.embeddings.specter2_local import embed_text

sample_text = "This paper proposes a novel federated learning approach for privacy-preserving distributed training."
vector = embed_text(sample_text)

print("Vector length:", len(vector))
print("First 5 values:", vector[:5])