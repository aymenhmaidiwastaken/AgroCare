import streamlit as st
import json
from groq import Groq
import os
from dotenv import load_dotenv
import base64
from openai import OpenAI
from io import BytesIO
from PIL import Image
import toml
from toolhouse import Toolhouse
from pymongo import MongoClient



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

def init_openai():
    api_key = st.secrets['api_keys']['openai']
    if not api_key:
        st.error("Please set your OpenAI API key")
        return None
    return OpenAI(api_key=api_key)

def analyze_image(client, image_data):
    if not client:
        return "Error: OpenAI client not initialized"
    
    try:
        # Encode image to base64
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
                    "content": "You are a plant disease detection assistant that identifies visible symptoms of plant diseases in images. Provide detailed descriptions of symptoms to help users diagnose potential issues."
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
            max_tokens=500
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"Error analyzing image: {str(e)}"

def get_groq_response(client, content, prompt, th=None):
    if not client:
        return "Error: Groq client not initialized"
    
    try:
        MODEL = "llama3-groq-70b-8192-tool-use-preview"
        messages = [
            {
                "role": "system",
                "content": content
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        if th is None: 
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.0,
                max_tokens=2000,
            )
            return response.choices[0].message.content
    
        # Add tools if th is provided
        messages = [{
            "role": "user",
            "content": "Search on web for recycling facilities near Binario F, Rome, Via Marsala, 29H, 00185 Roma RM and give me the results."
        }]

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=th.get_tools()
        )

        th_response = th.run_tools(response)
        messages += th_response
       
        messages.append({
            "role": "system", 
            "content": "return the result to the user you must NEVER use thesearch tool again"
        })

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
        )
                
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating response: {str(e)}"
# Function to save image and analysis result to MongoDB
def save_to_mongodb(image_file, analysis_result):
    uri = st.secrets["mongodb"]["uri"]  # MongoDB Atlas connection URI from secrets.toml
    client = MongoClient(uri)
    db = client["plant_disease_db"]  # Replace with your database name
    collection = db["images"]  # Replace with your collection name

    document = {
        "filename": image_file.name,
        "content_type": image_file.type,
        "image_data": image_file.getvalue(),
        "analysis_result": analysis_result
    }

    result = collection.insert_one(document)
    return result.inserted_id

# Streamlit UI
def main():
    st.title("🌍 Plant Disease Detection")    
    th = init_tool_house()
    groq_client = init_groq()
    openai_client = init_openai()

    if not groq_client or not openai_client or not th:
        st.stop()

    img_file = st.file_uploader("Upload a picture of the plant", type=["jpg", "jpeg", "png"])
    if img_file is not None:
        with st.spinner("Analyzing image..."):
            identified_items = analyze_image(openai_client, img_file)
            
            if not isinstance(identified_items, str) or identified_items.startswith("Error"):
                st.error(identified_items)
            else:
                st.write("Detected Items:", identified_items)
                try:
                    document_id = save_to_mongodb(img_file, identified_items)
                    st.success(f"Image and analysis result saved to MongoDB with ID: {document_id}")
                except Exception as e:
                    st.error(f"Failed to save to MongoDB: {str(e)}")

if __name__ == "__main__":
    main()
