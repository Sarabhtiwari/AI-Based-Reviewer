import numpy as np
from app.embeddings.paper_embedder import embed_paper
from app.embeddings.specter2_local import embed_text

def cos(a, b):
    a, b = np.array(a), np.array(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))

t = "Density-weighted support vector machines for binary class imbalance learning"
a = "We propose a density weighted SVM to handle class imbalance."

print("same text, both paths:", cos(embed_paper(t, a), embed_text(t, a)))   # expect ~1.0
print("related paper:", cos(embed_text(t, a), embed_paper("Fuzzy twin SVM for imbalanced classification")))
print("unrelated paper:", cos(embed_text(t, a), embed_paper("Leaf disease detection with deep learning")))