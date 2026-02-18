import os
import torch
import numpy as np
from PIL import Image
from transformers import AutoImageProcessor, AutoModel
import pickle
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Step 1: Load Facebook's DINO model (best for shape detection)
print("Loading AI model...")
processor = AutoImageProcessor.from_pretrained('facebook/dino-vitb16')
model = AutoModel.from_pretrained('facebook/dino-vitb16')
print("Model loaded successfully!")

# Step 2: Define folders
image_folder = "images"
embedding_folder = "embeddings"
os.makedirs(embedding_folder, exist_ok=True)

# Step 3: Get all image files
image_files = [f for f in os.listdir(image_folder) 
               if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp'))]
print(f"Found {len(image_files)} images to process")

# Step 4: Process each image
embeddings_dict = {}

for image_file in tqdm(image_files, desc="Processing images"):
    try:
        # Load image
        image_path = os.path.join(image_folder, image_file)
        image = Image.open(image_path).convert('RGB')
        
        # Prepare image for AI
        inputs = processor(images=image, return_tensors="pt")
        
        # Generate embedding (the "fingerprint")
        with torch.no_grad():
            outputs = model(**inputs)
            # Take the last hidden state and pool it
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
        
        # Store embedding
        design_name = os.path.splitext(image_file)[0]
        embeddings_dict[design_name] = embedding
        
    except Exception as e:
        print(f"Error processing {image_file}: {e}")

# Step 5: Save all embeddings
output_file = os.path.join(embedding_folder, "design_embeddings.pkl")
with open(output_file, 'wb') as f:
    pickle.dump(embeddings_dict, f)

print(f"\n✅ Successfully processed {len(embeddings_dict)} images")
print(f"✅ Embeddings saved to: {output_file}")