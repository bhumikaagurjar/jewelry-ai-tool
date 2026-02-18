import streamlit as st
import pandas as pd
import numpy as np
import pickle
import os
from PIL import Image
import torch
from transformers import AutoImageProcessor, AutoModel
import io
import base64
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity
import glob

# Page config
st.set_page_config(page_title="Jewelry Design Similarity Search", layout="wide")

# Title
st.title("💎 Jewelry Design Similarity Search")

# Initialize session state
if 'designs_df' not in st.session_state:
    # Create sample data for demonstration
    sample_data = {
        'Design_No': ['R001', 'R002', 'R003', 'R004', 'R005', 'N001', 'N002', 'E001', 'E002', 'B001'],
        'Category': ['Ring', 'Ring', 'Ring', 'Ring', 'Ring', 'Necklace', 'Necklace', 'Earring', 'Earring', 'Bracelet'],
        'Image_File': ['ring_001.jpg', 'ring_002.jpg', 'ring_003.jpg', 'ring_004.jpg', 'ring_005.jpg', 
                       'necklace_001.jpg', 'necklace_002.jpg', 'earring_001.jpg', 'earring_002.jpg', 'bracelet_001.jpg'],
        'Date_Added': [datetime.now().strftime("%Y-%m-%d") for _ in range(10)]
    }
    st.session_state.designs_df = pd.DataFrame(sample_data)
    st.session_state.embeddings = None
    st.session_state.model_loaded = False
    st.session_state.categories = ['Ring', 'Necklace', 'Earring', 'Bracelet', 'Pendant', 'Brooch', 'Cufflink', 'Other']
    st.session_state.similarity_results = None
    st.session_state.search_image = None

# Load AI model
@st.cache_resource
def load_model():
    try:
        processor = AutoImageProcessor.from_pretrained('facebook/dino-vitb16')
        model = AutoModel.from_pretrained('facebook/dino-vitb16')
        return processor, model
    except:
        return None, None

# Load embeddings
@st.cache_data
def load_embeddings():
    embedding_file = "embeddings/design_embeddings.pkl"
    if os.path.exists(embedding_file):
        with open(embedding_file, 'rb') as f:
            return pickle.load(f)
    return None

# Function to generate embedding for a new image
def generate_image_embedding(image, processor, model):
    try:
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Prepare image
        inputs = processor(images=image, return_tensors="pt")
        
        # Generate embedding
        with torch.no_grad():
            outputs = model(**inputs)
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
        
        return embedding
    except Exception as e:
        st.error(f"Error generating embedding: {e}")
        return None

# Function to find similar designs
def find_similar_designs(query_embedding, embeddings_dict, top_k=5):
    if query_embedding is None or embeddings_dict is None:
        return []
    
    similarities = []
    for design_name, emb in embeddings_dict.items():
        # Calculate cosine similarity
        sim = cosine_similarity([query_embedding], [emb])[0][0]
        similarities.append((design_name, sim))
    
    # Sort by similarity (highest first)
    similarities.sort(key=lambda x: x[1], reverse=True)
    
    # Return top k
    return similarities[:top_k]

# Create layout with columns
col1, col2 = st.columns([1, 2])

with col1:
    st.header("🔍 Search & Add Panel")
    
    # ===== ADD CATEGORY SECTION =====
    with st.expander("➕ ADD NEW CATEGORY", expanded=False):
        st.subheader("Add New Category")
        new_category = st.text_input("Category Name")
        if st.button("Add Category"):
            if new_category and new_category not in st.session_state.categories:
                st.session_state.categories.append(new_category)
                st.success(f"Category '{new_category}' added!")
                st.rerun()
            elif new_category in st.session_state.categories:
                st.warning("Category already exists")
            else:
                st.error("Please enter a category name")
    
    # ===== ADD DESIGN SECTION =====
    with st.expander("➕ ADD NEW DESIGN", expanded=False):
        st.subheader("Add New Design")
        new_design_no = st.text_input("Design Number")
        new_category_select = st.selectbox("Select Category", st.session_state.categories)
        new_image = st.file_uploader("Upload Design Image", type=['jpg', 'jpeg', 'png'], key="new_design_uploader")
        
        if st.button("Add Design"):
            if new_design_no and new_image:
                # Check if design number already exists
                if new_design_no not in st.session_state.designs_df['Design_No'].values:
                    # Save image to images folder (when available)
                    new_row = pd.DataFrame({
                        'Design_No': [new_design_no],
                        'Category': [new_category_select],
                        'Image_File': [new_image.name],
                        'Date_Added': [datetime.now().strftime("%Y-%m-%d")]
                    })
                    st.session_state.designs_df = pd.concat([st.session_state.designs_df, new_row], ignore_index=True)
                    st.success(f"Design {new_design_no} added successfully!")
                    st.rerun()
                else:
                    st.error("Design number already exists")
            else:
                st.error("Please enter design number and upload image")
    
    st.divider()
    
    # ===== UPLOAD IMAGE SECTION =====
    st.subheader("📤 Upload Design Image")
    uploaded_file = st.file_uploader("Choose an image...", type=['jpg', 'jpeg', 'png'], key="search_uploader")
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Design", use_container_width=True)
        st.session_state.search_image = image
        
        # Load model and embeddings
        processor, model = load_model()
        embeddings_dict = load_embeddings()
        
        if st.button("🔍 Find Similar Designs", key="find_similar_upload"):
            if processor is not None and model is not None:
                with st.spinner("Analyzing design shape..."):
                    # Generate embedding for query image
                    query_emb = generate_image_embedding(image, processor, model)
                    
                    if query_emb is not None and embeddings_dict is not None:
                        # Find similar designs
                        results = find_similar_designs(query_emb, embeddings_dict, top_k=5)
                        st.session_state.similarity_results = results
                        st.success("Search complete! Check results below.")
                    else:
                        st.error("Could not generate embedding or load database")
            else:
                st.error("AI model not loaded. Please check installation.")
    
    # ===== PASTE IMAGE SECTION =====
    st.subheader("📋 OR Paste Image")
    st.markdown("Copy an image to clipboard and paste below:")
    
    pasted_file = st.file_uploader("Press Ctrl+V to paste image", type=['jpg', 'jpeg', 'png'], key="paste_uploader")
    
    if pasted_file is not None:
        pasted_image = Image.open(pasted_file)
        st.image(pasted_image, caption="Pasted Image", use_container_width=True)
        st.session_state.search_image = pasted_image
        
        if st.button("🔍 Search with Pasted Image", key="find_similar_paste"):
            processor, model = load_model()
            embeddings_dict = load_embeddings()
            
            if processor is not None and model is not None:
                with st.spinner("Analyzing pasted design shape..."):
                    query_emb = generate_image_embedding(pasted_image, processor, model)
                    
                    if query_emb is not None and embeddings_dict is not None:
                        results = find_similar_designs(query_emb, embeddings_dict, top_k=5)
                        st.session_state.similarity_results = results
                        st.success("Search complete! Check results below.")
                    else:
                        st.error("Could not generate embedding or load database")
            else:
                st.error("AI model not loaded. Please check installation.")
    
    # URL option
    st.markdown("**OR**")
    image_url = st.text_input("Enter image URL")
    
    st.divider()
    
    # ===== SEARCH BY DESIGN NUMBER =====
    st.subheader("🔢 Search by Design No.")
    design_search = st.text_input("Enter Design Number")
    if design_search:
        filtered = st.session_state.designs_df[st.session_state.designs_df['Design_No'].str.contains(design_search, case=False)]
        if not filtered.empty:
            st.success(f"Found {len(filtered)} designs")
        else:
            st.warning("No designs found")
    
    # ===== FILTER BY CATEGORY =====
    st.subheader("🏷️ Filter by Category")
    categories_filter = ['All'] + st.session_state.categories
    selected_category = st.selectbox("Select Category", categories_filter, key="category_filter")

with col2:
    st.header("📋 Design Gallery")
    
    # Show similarity results if available
    if st.session_state.similarity_results is not None:
        st.subheader("🎯 Similarity Search Results")
        
        # Create columns for results
        res_cols = st.columns(2)
        
        for idx, (design_name, similarity) in enumerate(st.session_state.similarity_results):
            with res_cols[idx % 2]:
                # Get design details from dataframe
                design_row = st.session_state.designs_df[st.session_state.designs_df['Design_No'] == design_name]
                
                if not design_row.empty:
                    category = design_row.iloc[0]['Category']
                    similarity_pct = f"{similarity * 100:.1f}%"
                    
                    # Color code based on similarity
                    if similarity >= 0.8:
                        color = "🟢"  # High similarity
                    elif similarity >= 0.6:
                        color = "🟡"  # Medium similarity
                    else:
                        color = "🟠"  # Low similarity
                    
                    st.markdown(f"""
                    **{color} {design_name}**  
                    *Category:* {category}  
                    *Similarity:* **{similarity_pct}**  
                    """)
                    
                    # Placeholder for CAD image
                    st.markdown("🖼️ [CAD Image]")
                    
                    if st.button(f"View Details", key=f"view_{design_name}"):
                        st.info(f"Showing details for {design_name}")
                    
                    st.divider()
        
        if st.button("Clear Results"):
            st.session_state.similarity_results = None
            st.rerun()
        
        st.divider()
    
    # Filter designs based on category
    if selected_category and selected_category != 'All':
        filtered_designs = st.session_state.designs_df[st.session_state.designs_df['Category'] == selected_category]
    else:
        filtered_designs = st.session_state.designs_df
    
    # Display count
    st.caption(f"Showing {len(filtered_designs)} designs")
    
    # Display designs in a grid
    if len(filtered_designs) > 0:
        cols = st.columns(3)
        for idx, (_, row) in enumerate(filtered_designs.iterrows()):
            with cols[idx % 3]:
                st.markdown(f"**{row['Design_No']}**")
                st.markdown(f"*{row['Category']}*")
                st.caption(f"Added: {row['Date_Added']}")
                
                # Placeholder for image
                st.markdown("🖼️ [CAD Image]")
                
                # Find Similar button for each design
                if st.button(f"🔍 Find Similar", key=f"btn_{row['Design_No']}"):
                    # Load embeddings and find similar
                    embeddings_dict = load_embeddings()
                    if embeddings_dict and row['Design_No'] in embeddings_dict:
                        # This will be implemented when we have full embeddings
                        st.info(f"Searching for designs similar to {row['Design_No']}...")
                    else:
                        st.warning("Embeddings not available for this design")
                
                st.divider()
    else:
        st.info("No designs found in this category")

# Sidebar for additional info
with st.sidebar:
    st.header("ℹ️ About")
    st.markdown("""
    This tool helps you find visually similar jewelry designs based on shape and proportions.
    
    **Features:**
    - ✅ Upload or paste design images
    - ✅ Add new categories
    - ✅ Add new designs
    - ✅ Search by design number
    - ✅ Filter by category
    - ✅ Find similar designs with similarity percentage
    
    **How similarity works:**
    - 🟢 **80-100%**: Very similar shape
    - 🟡 **60-79%**: Moderately similar  
    - 🟠 **Below 60%**: Some similarity
    
    **How to paste an image:**
    1. Copy an image (Ctrl+C)
    2. Click on the paste uploader
    3. Press Ctrl+V
    """)
    
    # Check if embeddings exist
    embeddings_dict = load_embeddings()
    if embeddings_dict:
        st.success(f"✅ Database ready: {len(embeddings_dict)} designs embedded")
    else:
        st.warning("⚠️ Run generate_embeddings.py first to create design database")
    
    # Display stats
    st.divider()
    st.subheader("📊 Statistics")
    st.metric("Total Designs", len(st.session_state.designs_df))
    st.metric("Categories", len(st.session_state.categories))
    
    # Category breakdown
    st.subheader("📈 Category Breakdown")
    for cat in st.session_state.categories:
        count = len(st.session_state.designs_df[st.session_state.designs_df['Category'] == cat])
        if count > 0:
            st.text(f"{cat}: {count}")

# Footer
st.divider()
st.caption("Jewelry Design AI Tool - Shape-Based Similarity Search | Version 3.0 with Similarity Percentages")