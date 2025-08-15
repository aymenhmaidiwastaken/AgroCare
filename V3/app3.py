import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId  # Required for querying MongoDB's ObjectId
from PIL import Image
from io import BytesIO
import base64
from openai import OpenAI

# MongoDB initialization
@st.cache_resource
def get_mongo_client():
    """Initialize MongoDB client using the connection URI from secrets.toml"""
    uri = st.secrets["mongodb"]["uri"]
    return MongoClient(uri)

# MongoDB collections
client = get_mongo_client()
db = client["plant_disease_db"]  # Replace with your database name
images_collection = db["images"]  # Replace with your collection name
users_collection = client["user_auth_db"]["users"]  # Users collection

# Initialize OpenAI client
def init_openai():
    api_key = st.secrets['api_keys']['openai']
    if not api_key:
        st.error("Please set your OpenAI API key")
        return None
    return OpenAI(api_key=api_key)

# Fetch username by email
def fetch_username(email):
    user = users_collection.find_one({"email": email})
    if user:
        return user.get("username", "User")
    return "User"

# Navigation menu
def navigation_menu():
    pass  
# Display a single plant's page
def display_plant_page(plant_id):
    try:
        plant = images_collection.find_one({"_id": ObjectId(plant_id)})
    except Exception as e:
        st.error(f"Error fetching plant: {str(e)}")
        return

    if not plant:
        st.error("Plant not found!")
        return

    st.title(f"Details for {plant['filename']}")
    if "image_data" in plant:
        main_image = Image.open(BytesIO(plant["image_data"]))
        st.image(main_image, caption="Main Image", use_container_width=True)

    st.subheader("Analysis Result")
    st.write(plant["analysis_result"])  # Display analysis result as plain text

    # Display additional images and their comparison results
    additional_images = plant.get("additional_images", [])
    comparison_results = plant.get("comparison_results", [])

    for idx, image_data in enumerate(additional_images):
        st.image(Image.open(BytesIO(image_data)), caption=f"Additional Image {idx + 1}", use_container_width=True)
        if len(comparison_results) > idx:
            st.write(f"Comparison Result {idx + 1}:", comparison_results[idx])

    # File uploader for the second image
    img_file2 = st.file_uploader("Upload a new image for comparison", type=["jpg", "jpeg", "png"], key="file_uploader")

    if img_file2:
        with st.spinner("Analyzing and comparing images..."):
            try:
                openai_client = init_openai()
                base64_image1 = base64.b64encode(plant["image_data"]).decode('utf-8')
                base64_image2 = base64.b64encode(img_file2.getvalue()).decode('utf-8')

                comparison_prompt = """
                You are a specialized plant health assistant tasked with analyzing two images of a plant to compare their health states. For each detected symptom, provide:
                1. Symptom: [Describe the symptom]
                2. Image 1 Observation: [Observation from the first image]
                3. Image 2 Observation: [Observation from the second image]
                4. Evaluation: [Improved/Worsened/Unchanged/New Symptom]
                Provide a clear and concise report.
                """

                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a plant health analysis assistant."},
                        {"role": "user", "content": comparison_prompt + \
                         f"\nImage 1: data:image/jpeg;base64,{base64_image1}" + \
                         f"\nImage 2: data:image/jpeg;base64,{base64_image2}"}
                    ],
                    max_tokens=1000
                )

                comparison_result = response.choices[0].message.content

                # Save the new image and comparison results back to the database
                images_collection.update_one(
                    {"_id": ObjectId(plant_id)},
                    {"$push": {
                        "additional_images": img_file2.getvalue(),
                        "comparison_results": comparison_result
                    }}
                )

                st.success("New image and comparison saved successfully!")
                st.session_state["current_plant_id"] = None  # Redirect to plant list
                st.session_state["redirect"] = True
            except Exception as e:
                st.error(f"Error analyzing or comparing images: {str(e)}")

    # Back to Scanned Plants button
    if st.button("Back to Scanned Plants List", key="back_button"):
        st.session_state["current_plant_id"] = None
        st.session_state["redirect"] = True

# Display grid of plants
def display_plants_grid(plants, username):
    st.title("🌱 Scanned Plants List")  # Ensure this line is indented
    if not plants:
        st.info("No plants have been scanned yet.")
        return

    for i in range(0, len(plants), 4):
        row = plants[i:i + 4]
        cols = st.columns(4)
        for col, plant in zip(cols, row):
            with col:
                if "image_data" in plant:
                    image = Image.open(BytesIO(plant["image_data"]))
                    st.image(image, caption=plant["filename"], use_container_width=True)
                if st.button("View Details", key=f"view_{plant['_id']}"):
                    st.session_state["current_plant_id"] = str(plant["_id"])

# Main app logic
def main(username=None):
    navigation_menu()

    # Redirect logic
    if st.session_state.get("redirect"):
        st.session_state["redirect"] = False
        st.query_params.clear()  # Reset the page state
        st.session_state["current_plant_id"] = None

    plant_id = st.session_state.get("current_plant_id", None)

    if plant_id:
        display_plant_page(plant_id)
    else:
        try:
            plants = list(images_collection.find())
        except Exception as e:
            st.error(f"Error fetching plants: {str(e)}")
            return

        display_plants_grid(plants, username)

if __name__ == "__main__":
    if "current_plant_id" not in st.session_state:
        st.session_state["current_plant_id"] = None
    if "redirect" not in st.session_state:
        st.session_state["redirect"] = False
    if "email" not in st.session_state:
        st.session_state["email"] = "email@gmail.com"  # Replace with the logged-in user's email
    main()
