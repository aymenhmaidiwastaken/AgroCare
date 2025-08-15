import streamlit as st
from pymongo import MongoClient
import bcrypt
import importlib.util
from streamlit_cookies_manager import CookieManager
import json
import os

# Central Cookie Manager Initialization
cookies = CookieManager(
    prefix="my_app_"  # Shared prefix for all apps
)
if not cookies.ready():
    st.stop()  # Wait for the cookies manager to initialize

# MongoDB initialization
@st.cache_resource
def get_mongo_client():
    """Initialize MongoDB client using the connection URI from secrets.toml"""
    uri = st.secrets["mongodb"]["uri"]
    return MongoClient(uri)

# MongoDB collections
client = get_mongo_client()
db = client["user_auth_db"]  # Replace with your database name
users_collection = db["users"]

# Utility functions
def hash_password(password):
    """Hash a plaintext password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def verify_password(plaintext_password, hashed_password):
    """Verify a plaintext password against a hashed password"""
    return bcrypt.checkpw(plaintext_password.encode('utf-8'), hashed_password)

def signup(username, email, password):
    """Save a new user to the database"""
    if users_collection.find_one({"email": email}):
        st.error("Email already registered. Please log in.")
        return False

    hashed_pw = hash_password(password)
    user = {
        "username": username,
        "email": email,
        "password": hashed_pw
    }
    users_collection.insert_one(user)
    st.success("Signup successful! You can now log in.")
    return True

def login(email, password):
    """Authenticate a user"""
    user = users_collection.find_one({"email": email})
    if user and verify_password(password, user["password"]):
        cookies["logged_in"] = "true"  # Store boolean as a string
        cookies["user"] = json.dumps({"id": str(user["_id"]), "username": user["username"], "email": user["email"]})
        cookies.save()  # Save the session to cookies
        st.session_state["logged_in"] = True
        st.session_state["user"] = user
        st.session_state["current_app"] = None  # Redirect to dashboard after login
        st.rerun()
    else:
        st.error("Invalid email or password.")

def logout():
    """Log out the user"""
    cookies["logged_in"] = "false"  # Store boolean as a string
    cookies["user"] = None
    cookies.save()  # Clear cookies
    st.session_state["logged_in"] = False
    st.session_state["user"] = None
    st.session_state["current_app"] = None
    st.rerun()

def load_app_from_folder(folder_path, module_name):
    """Dynamically load a Streamlit app from a folder"""
    spec = importlib.util.spec_from_file_location(module_name, os.path.join(folder_path, f"{module_name}.py"))
    app_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_module)
    return app_module

# Dashboard View
def dashboard():
    if not st.session_state.get("user"):
        st.error("No user session found. Please log in again.")
        logout()  # Redirect to the login page
        return

    st.sidebar.subheader("Navigation")
    if st.sidebar.button("Plant Disease Detection"):
        st.session_state["current_app"] = "App 1"
        st.rerun()
    if st.sidebar.button("Scanned Plants"):
        st.session_state["current_app"] = "App 3"
        st.rerun()
    if st.sidebar.button("User Info"):
        st.session_state["current_app"] = "User Info"
        st.rerun()
    if st.sidebar.button("Logout"):
        logout()

# User Info Page
def user_info_page():
    st.title("User Info")
    if st.session_state["user"]:
        user = st.session_state["user"]
        st.write(f"**Username:** {user['username']}")
        st.write(f"**Email:** {user['email']}")
    else:
        st.error("No user data found.")

# Main App
def main():
    # Restore session from cookies
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = cookies.get("logged_in", "false") == "true"
        user_cookie = cookies.get("user", None)
        if user_cookie and user_cookie != "null":
            try:
                st.session_state["user"] = json.loads(user_cookie)
            except json.JSONDecodeError:
                st.session_state["user"] = None
        else:
            st.session_state["user"] = None
        st.session_state["current_app"] = None

    # Show sidebar if logged in
    if st.session_state["logged_in"]:
        dashboard()
        current_app = st.session_state.get("current_app", None)
        if current_app == "App 1":
            app1 = load_app_from_folder("V1", "app1")
            app1.main()
        elif current_app == "App 2":
            app2 = load_app_from_folder("V2", "app2")
            app2.main()
        elif current_app == "App 3":
            app3 = load_app_from_folder("V3", "app3")
            app3.main(username=st.session_state['user']['username'])
        elif current_app == "User Info":
            user_info_page()
        else:
            st.write("Welcome to the dashboard. Use the navigation menu.")
    else:
        st.title("🔐 Login/Signup System")
        option = st.selectbox("Choose an option", ["Login", "Signup"])
        if option == "Signup":
            st.subheader("Signup Form")
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.button("Signup"):
                if username and email and password:
                    signup(username, email, password)
                else:
                    st.error("Please fill all fields.")
        elif option == "Login":
            st.subheader("Login Form")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                if email and password:
                    login(email, password)
                else:
                    st.error("Please fill all fields.")

if __name__ == "__main__":
    main()
