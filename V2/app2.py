import streamlit as st
import json
from groq import Groq
import os
from io import BytesIO
from dotenv import load_dotenv
import base64
from pymongo import MongoClient
from openai import OpenAI
from PIL import Image

# Initialize ToolHouse client
def init_tool_house():
    api_key = st.secrets['api_keys']['toolhouse']
    return Toolhouse(api_key=api_key, provider="openai")

# Initialize Groq client
def init_groq():
    api_key = st.secrets['api_keys']['groq']
    if not api_key:
        st.error("Please set your Groq API key")
        return None
    return Groq(api_key=api_key)

# Initialize OpenAI client
def init_openai():
    api_key = st.secrets['api_keys']['openai']
    if not api_key:
        st.error("Please set your OpenAI API key")
        return None
    return OpenAI(api_key=api_key)

# MongoDB initialization
@st.cache_resource
def get_mongo_client():
    """Initialize MongoDB client using the connection URI from secrets.toml"""
    uri = st.secrets["mongodb"]["uri"]
    return MongoClient(uri)

# Fetch the latest image from MongoDB
def fetch_latest_image_from_mongodb(client):
    db = client["plant_disease_db"]  # Replace with your database name
    collection = db["images"]  # Replace with your collection name
    latest_image = collection.find_one(sort=[("_id", -1)])  # Get the latest document
    return latest_image

# Save the comparison results to MongoDB
def save_comparison_to_mongodb(image2, comparison_results):
    client = get_mongo_client()
    db = client["plant_disease_db"]
    collection = db["comparisons"]

    document = {
        "filename_image2": image2.name,
        "comparison_results": comparison_results,
    }

    result = collection.insert_one(document)
    return result.inserted_id

# Analyze an image using OpenAI
def analyze_image(client, image_data):
    if not client:
        return "Error: OpenAI client not initialized"

    try:
        base64_image = base64.b64encode(image_data.getvalue()).decode('utf-8')

        prompt = """Analyze this image and detect visible symptoms of plant disease.
Guidelines for detection:
Identify symptoms using clear, descriptive terms (e.g., "yellowing leaves," "dark spots," "wilting stems")
Specify the affected plant parts (e.g., "leaf edges," "fruit surface")
Focus only on disease-related signs, ignoring healthy areas and unrelated elements
Use a comma-separated format. Example:
"yellowing leaf edges, black spots on fruits, white fungal growth on stems"
Provide your analysis in the specified format.
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a plant disease detection assistant that identifies visible symptoms of plant diseases in images."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1200
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"Error analyzing image: {str(e)}"

# Streamlit UI
def main():
    st.title("🌍 Plant Disease Image Comparison")
    

    # Initialize MongoDB client
    client = get_mongo_client()

    # Fetch the latest uploaded image from MongoDB
    latest_image = fetch_latest_image_from_mongodb(client)
    if not latest_image:
        st.error("No previous image found in the database.")
        return

    # Decode and display the latest image
    latest_image_data = latest_image["image_data"]
    image1 = Image.open(BytesIO(latest_image_data))
    st.image(image1, caption="Image 1 (Previous Upload)", use_container_width=True)

    # File uploader for the second image
    img_file2 = st.file_uploader("Upload the second image for comparison", type=["jpg", "jpeg", "png"])

    if img_file2:
        with st.spinner("Analyzing and comparing images..."):
            base64_image1 = base64.b64encode(latest_image_data).decode('utf-8')
            base64_image2 = base64.b64encode(img_file2.getvalue()).decode('utf-8')

            comparison_prompt = """
            You are a specialized plant health assistant tasked with analyzing two images of a plant to compare their health states. For each detected symptom, provide:
            
            1. Symptom: [Describe the symptom]
            2. Image 1 Observation: [Observation from the first image]
            3. Image 2 Observation: [Observation from the second image]
            4. Evaluation: [Improved/Worsened/Unchanged/New Symptom]
            
            Provide a clear and concise report.
            """

            try:
                th = init_tool_house()
                groq_client = init_groq()
                openai_client = init_openai()

                if not groq_client or not openai_client or not th:
                    st.stop()
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a plant health analysis assistant."
                        },
                        {
                            "role": "user",
                            "content": comparison_prompt + \
                                       f"\nImage 1 (Previous Upload): data:image/jpeg;base64,{base64_image1}" + \
                                       f"\nImage 2 (Uploaded Image): data:image/jpeg;base64,{base64_image2}"
                        }
                    ],
                    max_tokens=1000
                )

                comparison_results = response.choices[0].message.content
                st.write("Comparison Results:")
                st.write(comparison_results)

                # Save the comparison results to MongoDB
                try:
                    document_id = save_comparison_to_mongodb(img_file2, comparison_results)
                    st.success(f"Comparison results saved to MongoDB with ID: {document_id}")
                except Exception as e:
                    st.error(f"Failed to save comparison results to MongoDB: {str(e)}")

            except Exception as e:
                st.error(f"Error comparing images: {str(e)}")

if __name__ == "__main__":
    main()
