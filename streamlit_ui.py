import streamlit as st
import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd

# Configure Streamlit page
st.set_page_config(
    page_title="Prompt Management API",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration
API_BASE_URL = "http://localhost:8000"
API_V1_BASE = f"{API_BASE_URL}/api/v1"

# Session state initialization
if 'access_token' not in st.session_state:
    st.session_state.access_token = None
if 'user_info' not in st.session_state:
    st.session_state.user_info = None

def make_request(method: str, endpoint: str, data: Dict = None, params: Dict = None, auth_required: bool = True) -> Dict:
    """Make HTTP request to the API"""
    url = f"{API_V1_BASE}{endpoint}"
    headers = {"Content-Type": "application/json"}
    
    if auth_required and st.session_state.access_token:
        headers["Authorization"] = f"Bearer {st.session_state.access_token}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method.upper() == "POST":
            if endpoint.endswith("/login") or endpoint.endswith("/token"):
                # Form data for login
                response = requests.post(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            else:
                # Handle both string and dictionary data
                if isinstance(data, dict):
                    response = requests.post(url, json=data, headers=headers)
                else:
                    headers["Content-Type"] = "text/plain"
                    response = requests.post(url, data=data, headers=headers)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, headers=headers)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, params=params)
        else:
            return {"error": f"Unsupported method: {method}"}
        
        # Handle response data safely
        try:
            response_data = response.json() if response.content else {}
        except json.JSONDecodeError:
            response_data = {"raw_response": response.text}
        
        return {
            "status_code": response.status_code,
            "data": response_data,
            "success": response.status_code < 400
        }
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "success": False}

def display_response(response: Dict):
    """Display API response in a formatted way"""
    if "error" in response:
        st.error(f"Error: {response['error']}")
        return
    
    status_code = response.get("status_code", 0)
    if status_code >= 400:
        st.error(f"HTTP {status_code}: {response.get('data', {})}")
    elif status_code >= 200:
        st.success(f"HTTP {status_code}: Success")
        
    if response.get("data"):
        st.json(response["data"])

def authentication_section():
    """Authentication section"""
    st.header("🔐 Authentication")
    
    # Check if user is logged in
    if st.session_state.access_token:
        st.success(f"✅ Logged in as: {st.session_state.user_info.get('email', 'Unknown')}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Get Current User Info"):
                response = make_request("GET", "/auth/me")
                display_response(response)
        
        with col2:
            if st.button("Logout"):
                st.session_state.access_token = None
                st.session_state.user_info = None
                st.rerun()
    else:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            st.subheader("Login")
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login")
                
                if submitted and email and password:
                    response = make_request("POST", "/auth/token", 
                                          data={"username": email, "password": password}, 
                                          auth_required=False)
                    
                    if response.get("success") and isinstance(response.get("data"), dict) and response["data"].get("access_token"):
                        st.session_state.access_token = response["data"]["access_token"]
                        st.session_state.user_info = response["data"].get("user", {})
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        display_response(response)
        
        with tab2:
            st.subheader("Register")
            with st.form("register_form"):
                reg_email = st.text_input("Email", key="reg_email")
                reg_password = st.text_input("Password", type="password", key="reg_password")
                full_name = st.text_input("Full Name")
                submitted = st.form_submit_button("Register")
                
                if submitted and reg_email and reg_password and full_name:
                    response = make_request("POST", "/auth/register", 
                                          data={"email": reg_email, "password": reg_password, "full_name": full_name},
                                          auth_required=False)
                    display_response(response)

def prompts_section():
    """Prompts management section"""
    st.header("📝 Prompt Management")
    
    if not st.session_state.access_token:
        st.warning("Please login first to access prompt management features.")
        return
    
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Create Prompt", "List Prompts", "Search Prompts", 
        "Get Prompt", "Update Prompt", "Delete Prompt", "Test Persona"
    ])
    
    with tab1:
        st.subheader("Create New Prompt")
        with st.form("create_prompt_form"):
            name = st.text_input("Prompt Name*")
            content = st.text_area("Content*", height=150)
            description = st.text_area("Description")
            tags = st.text_input("Tags (comma-separated)")
            
            # Metadata section
            col1, col2 = st.columns(2)
            with col1:
                metadata_key = st.text_input("Metadata Key (optional)")
            with col2:
                metadata_value = st.text_input("Metadata Value (optional)")
            
            st.info("ℹ️ All new prompts start as 'draft' status. Use 'Set Live Version' to activate.")
            
            submitted = st.form_submit_button("Create Prompt")
            
            if submitted and name and content:
                data = {
                    "name": name,
                    "content": content,
                    "tags": [tag.strip() for tag in tags.split(",") if tag.strip()]
                }
                
                if description:
                    data["description"] = description
                if metadata_key and metadata_value:
                    data["metadata_"] = {metadata_key: metadata_value}
                
                response = make_request("POST", "/prompts/", data=data)
                display_response(response)
    
    with tab2:
        st.subheader("List All Prompts")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            skip = st.number_input("Skip", min_value=0, value=0)
        with col2:
            limit = st.number_input("Limit", min_value=1, max_value=1000, value=10)
        with col3:
            status_filter = st.selectbox("Status Filter", ["all", "draft", "active", "archived"])
        
        if st.button("List Prompts"):
            params = {"skip": skip, "limit": limit}
            if status_filter != "all":
                params["status"] = status_filter
            
            response = make_request("GET", "/prompts/", params=params)
            if response.get("success") and isinstance(response.get("data"), dict) and response["data"].get("items"):
                items = response["data"]["items"]
                if items:
                    df = pd.DataFrame(items)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No results found.")
            else:
                display_response(response)
    
    with tab3:
        st.subheader("Search Prompts")
        col1, col2 = st.columns(2)
        
        with col1:
            search_query = st.text_input("Search Query")
            search_tag = st.text_input("Tag Filter")
        with col2:
            search_status = st.selectbox("Status Filter", ["all", "draft", "active", "archived"], key="search_status")
            created_by = st.text_input("Created By")
        
        if st.button("Search Prompts"):
            params = {}
            if search_query:
                params["query"] = search_query
            if search_tag:
                params["tag"] = search_tag
            if search_status != "all":
                params["status"] = search_status
            if created_by:
                params["created_by"] = created_by
            
            response = make_request("GET", "/prompts/", params=params)
            if response.get("success") and isinstance(response.get("data"), dict) and response["data"].get("items"):
                items = response["data"]["items"]
                if items:
                    df = pd.DataFrame(items)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No results found.")
            else:
                display_response(response)
    
    with tab4:
        st.subheader("Get Prompt")
        
        get_method = st.selectbox(
            "Select Method",
            ["By ID", "By Name/Version", "Live Version by Name", "Latest by Criteria"],
            key="get_method_select"
        )    
        if get_method == "By ID":
            prompt_id = st.number_input("Prompt ID", min_value=1)
            if st.button("Get Prompt by ID"):
                response = make_request("GET", f"/prompts/{prompt_id}")
                display_response(response)
        
        elif get_method == "By Name/Version":
            col1, col2 = st.columns(2)
            with col1:
                prompt_name = st.text_input("Prompt Name", key="get_name_version")
            with col2:
                version = st.text_input("Version (e.g., 1.0.0)", key="get_version")
            
            if st.button("Get Prompt by Name/Version") and prompt_name and version:
                response = make_request("GET", f"/prompts/name/{prompt_name}/version/{version}")
                display_response(response)
        
        elif get_method == "Live Version by Name":
            prompt_name = st.text_input("Prompt Name", key="live_name")
            if st.button("Get Live Version") and prompt_name:
                response = make_request("GET", f"/prompts/name/{prompt_name}/live")
                if response and response.get("status_code") == 200:
                    live_prompt = response["data"]
                    st.success(f"Live Version: {live_prompt['version']}")
                    st.json(live_prompt)
                else:
                    st.error("No live version found")
        
        elif get_method == "Latest by Criteria":
            col1, col2 = st.columns(2)
            with col1:
                criteria_name = st.text_input("Name Filter (partial)", key="criteria_name")
                tags = st.text_input("Tags (comma-separated)", key="create_tags")
            with col2:
                metadata_key = st.text_input("Metadata Key (optional)", key="create_meta_key")
                metadata_value = st.text_input("Metadata Value (optional)", key="create_meta_value")
            
            if st.button("Get Latest by Criteria"):
                params = {}
                if criteria_name:
                    params["name"] = criteria_name
                if tags:
                    params["tags"] = tags
                if metadata_key and metadata_value:
                    params["metadata_key"] = metadata_key
                    params["metadata_value"] = metadata_value
                
                response = make_request("GET", "/prompts/search/latest", params=params)
                display_response(response)
        
        elif get_method == "Active by Name":
            prompt_name = st.text_input("Prompt Name", key="get_active_name")
            if st.button("Get Active Version") and prompt_name:
                response = make_request("GET", f"/prompts/name/{prompt_name}/active")
                display_response(response)
    
    with tab5:
        st.subheader("Update Prompt")
        prompt_id = st.number_input("Prompt ID to Update", min_value=1, key="update_id")
        
        # Auto-populate existing content when prompt ID is selected
        if prompt_id and prompt_id > 0:
            if st.button("Load Existing Content", key="load_content_btn"):
                response = make_request("GET", f"/prompts/{prompt_id}")
                if response.get("success"):
                    prompt_data = response["data"]
                    st.session_state.update_content = prompt_data.get("content", "")
                    st.session_state.update_description = prompt_data.get("description", "")
                    st.session_state.update_tags = ", ".join(prompt_data.get("tags", []))
                    metadata = prompt_data.get("metadata_", {})
                    if metadata:
                        first_key = list(metadata.keys())[0] if metadata else ""
                        first_value = metadata.get(first_key, "") if first_key else ""
                        st.session_state.update_meta_key = first_key
                        st.session_state.update_meta_value = first_value
                    st.success(f"Loaded content for prompt: {prompt_data.get('name', 'Unknown')}")
                else:
                    st.error("Failed to load prompt content")
        
        # Update fields with auto-populated values
        new_content = st.text_area("Content", 
                                 value=st.session_state.get("update_content", ""),
                                 key="update_content_field")
        new_description = st.text_area("Description", 
                                     value=st.session_state.get("update_description", ""),
                                     key="update_description_field")
        new_tags = st.text_input("Tags (comma-separated)", 
                                value=st.session_state.get("update_tags", ""),
                                key="update_tags_field")
        
        # Metadata
        col3, col4 = st.columns(2)
        with col3:
            update_meta_key = st.text_input("Metadata Key", 
                                          value=st.session_state.get("update_meta_key", ""),
                                          key="update_meta_key_field")
        with col4:
            update_meta_value = st.text_input("Metadata Value", 
                                            value=st.session_state.get("update_meta_value", ""),
                                            key="update_meta_value_field")
        
        st.info("ℹ️ Updates will create a new version with auto-incremented version number.")
        
        if st.button("Save Changes", key="update_btn"):
            if prompt_id and (new_content or new_description or new_tags or (update_meta_key and update_meta_value)):
                # Create new version with auto-incremented version
                version_data = {
                    "content": new_content if new_content else None,
                    "description": new_description if new_description else None,
                    "tags": [tag.strip() for tag in new_tags.split(",") if tag.strip()] if new_tags else None,
                    "metadata_": {update_meta_key: update_meta_value} if update_meta_key and update_meta_value else None
                }
                
                # Remove None values
                version_data = {k: v for k, v in version_data.items() if v is not None}
                
                response = make_request("POST", f"/prompts/{prompt_id}/update-version", data=version_data)
                if response.get("success"):
                    st.success(f"Created new version: {response['data'].get('version', 'Unknown')}")
                    # Clear session state
                    for key in ["update_content", "update_description", "update_tags", "update_meta_key", "update_meta_value"]:
                        if key in st.session_state:
                            del st.session_state[key]
                display_response(response)
            else:
                st.warning("Please provide a Prompt ID and at least one field to update")
    
    with tab6:
        st.subheader("Delete Prompt")
        delete_id = st.number_input("Prompt ID to Delete", min_value=1, key="delete_id")
        force_delete = st.checkbox("Force Delete (permanent)", help="If unchecked, performs soft delete")
        
        if st.button("Delete Prompt", type="secondary"):
            params = {"force": force_delete}
            response = make_request("DELETE", f"/prompts/{delete_id}", params=params)
            display_response(response)
    
    with tab7:
        st.subheader("🤖 Test Persona")
        st.info("The system will automatically select the most appropriate prompt based on your input.")
        
        # User input section
        user_input = st.text_area(
            "Enter your message:", 
            placeholder="Type your message here to test the persona response...",
            height=100,
            key="persona_test_input"
        )
        
        if st.button("🚀 Test Persona", key="test_persona_btn") and user_input:
            with st.spinner("Finding the best prompt and generating response..."):
                # Use the automatic prompt selection endpoint
                response = make_request("POST", "/prompts/test-persona", data=user_input)
                
                if response.get("success"):
                    result = response["data"]
                    st.success("✅ Persona Response Generated!")
                    
                    # Display the full JSON response
                    st.json(result)
                else:
                    st.error("Failed to generate persona response")
                    display_response(response)

def versions_and_history_section():
    """Versions and history section"""
    st.header("📚 Versions & History")
    
    if not st.session_state.access_token:
        st.warning("Please login first to access versions and history.")
        return
    
    tab1, tab2, tab3 = st.tabs(["List Versions", "Set Live Version", "View History"])
    
    with tab1:
        st.subheader("List Prompt Versions")
        prompt_name = st.text_input("Prompt Name", key="list_versions_name")
        col1, col2 = st.columns(2)
        
        with col1:
            skip = st.number_input("Skip", min_value=0, value=0, key="versions_skip")
        with col2:
            limit = st.number_input("Limit", min_value=1, max_value=1000, value=10, key="versions_limit")
        
        if st.button("Get Versions") and prompt_name:
            params = {"skip": skip, "limit": limit}
            response = make_request("GET", f"/prompts/name/{prompt_name}/versions", params=params)
            
            if response.get("success") and isinstance(response.get("data"), dict) and response["data"].get("items"):
                items = response["data"]["items"]
                if items:
                    df = pd.DataFrame(items)
                    # Add action buttons for each version
                    st.dataframe(df, use_container_width=True)
                    
                    # Show version management options
                    st.subheader("Quick Actions")
                    for item in items:
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.write(f"**{item['name']}** v{item['version']} - {item['status']}")
                        with col2:
                            st.subheader("🔄 Version Management")
                        with col3:
                            if st.button(f"View", key=f"view_{item['id']}"):
                                view_response = make_request("GET", f"/prompts/{item['id']}")
                                display_response(view_response)
                else:
                    st.info("No results found.")
            else:
                display_response(response)
    
    with tab2:
        st.subheader("Set Live Version")
        
        # Get list of all prompts
        prompts_response = make_request("GET", "/prompts")
        
        if prompts_response and "data" in prompts_response and "items" in prompts_response["data"]:
            prompts = prompts_response["data"]["items"]
            prompt_names = sorted(list({p["name"] for p in prompts}))
            
            if not prompt_names:
                st.warning("No prompts found. Please create a prompt first.")
            else:
                # Let user select a prompt
                selected_prompt = st.selectbox("Select Prompt", prompt_names, key="select_prompt_live")
                
                # Get versions for the selected prompt
                versions = [p for p in prompts if p["name"] == selected_prompt]
                version_choices = {f"{p['version']} (Active)" if p.get('is_active') else p['version']: p['version'] for p in versions}
                
                if not versions:
                    st.warning(f"No versions found for prompt: {selected_prompt}")
                else:
                    # Let user select a version
                    selected_version = st.selectbox(
                        "Select Version to Activate",
                        options=list(version_choices.keys()),
                        format_func=lambda x: x,
                        key="select_version_live"
                    )
                    
                    version_to_activate = version_choices[selected_version]
                    
                    if st.button("Set as Live Version", key="set_live_version_btn"):
                        current_user = st.session_state.get("user_email", "system@example.com")
                        try:
                            response = make_request(
                                "POST", 
                                f"/prompts/name/{selected_prompt}/version/{version_to_activate}/activate?updated_by={current_user}"
                            )
                            
                            if response and response.get("status_code") == 200:
                                st.success(f"Version {version_to_activate} of '{selected_prompt}' is now live!")
                                st.rerun()  # Refresh the UI to show updated active status
                            else:
                                error_msg = response.get("detail", response.get("message", str(response)))
                                st.error(f"Failed to set version as live: {error_msg}")
                                
                        except Exception as e:
                            st.error(f"Error making request: {str(e)}")
        else:
            st.error("Failed to load prompts. Please try again later.")
    
    with tab3:
        st.subheader("View History")
        history_id = st.number_input("Prompt ID", min_value=1, key="history_id")
        col1, col2 = st.columns(2)
        
        with col1:
            skip = st.number_input("Skip", min_value=0, value=0, key="history_skip")
        with col2:
            limit = st.number_input("Limit", min_value=1, max_value=1000, value=10, key="history_limit")
        
        if st.button("Get History"):
            params = {"skip": skip, "limit": limit}
            response = make_request("GET", f"/prompts/{history_id}/history", params=params)
            
            if response.get("success") and isinstance(response.get("data"), dict) and response["data"].get("items"):
                items = response["data"]["items"]
                if items:
                    df = pd.DataFrame(items)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No results found.")
            else:
                display_response(response)

def system_section():
    """System information section"""
    st.header("⚙️ System Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Health Check"):
            try:
                response = requests.get(f"{API_BASE_URL}/health")
                st.json(response.json())
            except Exception as e:
                st.error(f"Error: {e}")
    
    with col2:
        if st.button("API Info"):
            try:
                response = requests.get(f"{API_BASE_URL}/api")
                st.json(response.json())
            except Exception as e:
                st.error(f"Error: {e}")

def main():
    """Main Streamlit application"""
    st.title("🚀 Prompt Management API Interface")
    st.markdown("---")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    section = st.sidebar.radio(
        "Choose Section:",
        ["Authentication", "Prompt Management", "Versions & History", "System Info"]
    )
    
    # Display API status in sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("API Status")
    try:
        health_response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if health_response.status_code == 200:
            st.sidebar.success("🟢 API Online")
        else:
            st.sidebar.error("🔴 API Error")
    except:
        st.sidebar.error("🔴 API Offline")
    
    # Display current user in sidebar
    if st.session_state.access_token and st.session_state.user_info:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Current User")
        st.sidebar.info(f"📧 {st.session_state.user_info.get('email', 'Unknown')}")
        st.sidebar.info(f"👤 {st.session_state.user_info.get('full_name', 'Unknown')}")
    
    # Main content based on selected section
    if section == "Authentication":
        authentication_section()
    elif section == "Prompt Management":
        prompts_section()
    elif section == "Versions & History":
        versions_and_history_section()
    elif section == "System Info":
        system_section()

if __name__ == "__main__":
    main()
