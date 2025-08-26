from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from supabase import create_client, Client
import os
from functools import wraps

# Initialize Flask application
application = Flask(__name__)
application.secret_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmbHliYnZ5d3Z1a3lscW5oanF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3NTgwNzYsImV4cCI6MjA3MTMzNDA3Nn0.WjnYqvIDNH353TlfJD9IwxU2oEniP3XZXR1I7dWVhT8"

# Supabase Configuration
SUPABASE_URL = "https://pflybbvywvukylqnhjqw.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmbHliYnZ5d3Z1a3lscW5oanF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU3NTgwNzYsImV4cCI6MjA3MTMzNDA3Nn0.WjnYqvIDNH353TlfJD9IwxU2oEniP3XZXR1I7dWVhT8"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmbHliYnZ5d3Z1a3lscW5oanF3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTc1ODA3NiwiZXhwIjoyMDcxMzM0MDc2fQ.qUraO4YsMUl3sfUf6x5jzojCrWqLR3-lW_7QpfTkny4"

# Initialize Supabase clients
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

class FileManagerHelper:
    @staticmethod
    def clean_path(path_string):
        """Clean and normalize file paths"""
        if path_string is None:
            return ""
        return path_string.strip().strip("/")
    
    @staticmethod
    def build_navigation_trail(folder_path):
        """Create navigation breadcrumb trail"""
        trail = [{"title": "Home", "url": ""}]
        
        if not folder_path:
            return trail
            
        path_segments = folder_path.split("/")
        accumulated_path = ""
        
        for segment in path_segments:
            if segment.strip():
                accumulated_path = f"{accumulated_path}/{segment}" if accumulated_path else segment
                trail.append({"title": segment, "url": accumulated_path})
        
        return trail
    
    @staticmethod
    def fetch_all_buckets():
        """Retrieve all available storage buckets"""
        try:
            bucket_list = supabase_admin.storage.list_buckets()
            if isinstance(bucket_list, list):
                return bucket_list
            elif isinstance(bucket_list, dict):
                return bucket_list.get("data", [])
            return list(bucket_list) if bucket_list else []
        except Exception as error:
            print(f"Bucket retrieval error: {error}")
            return []
    
    @staticmethod
    def format_file_size(size_bytes):
        """Convert bytes to human readable format"""
        if not size_bytes:
            return "0 B"
        
        units = ["B", "KB", "MB", "GB"]
        size = float(size_bytes)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
            
        return f"{size:.1f} {units[unit_index]}"

def error_handler(func):
    """Decorator for handling errors gracefully"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            flash(f"Operation failed: {str(e)}", "error")
            return redirect(url_for("home_page"))
    return wrapper

@application.route("/")
def home_page():
    """Main dashboard for file management"""
    selected_bucket = request.args.get("bucket", "my-bucket")
    current_directory = FileManagerHelper.clean_path(request.args.get("folder", ""))
    
    # Get bucket information
    all_buckets = FileManagerHelper.fetch_all_buckets()
    bucket_data = []
    
    for bucket_item in all_buckets:
        if hasattr(bucket_item, 'name'):
            bucket_data.append({"name": bucket_item.name})
        elif isinstance(bucket_item, dict):
            bucket_data.append({"name": bucket_item.get("name", "Unknown")})
        else:
            bucket_data.append({"name": str(bucket_item)})
    
    # Fetch directory contents
    directory_items = []
    try:
        query_options = {"limit": 100, "offset": 0}
        if current_directory:
            query_options["prefix"] = current_directory + "/"
        
        storage_response = supabase_client.storage.from_(selected_bucket).list(current_directory, query_options)
        items_data = storage_response if isinstance(storage_response, list) else storage_response.get("data", [])
        
        for storage_item in items_data:
            if not isinstance(storage_item, dict) or not storage_item.get("name"):
                continue
                
            # Skip hidden files and current directory
            if storage_item["name"] == current_directory or storage_item["name"].endswith(".keep"):
                continue
            
            # Build full path
            if current_directory:
                item_full_path = f"{current_directory}/{storage_item['name']}"
            else:
                item_full_path = storage_item["name"]
            
            # Determine if folder or file
            if storage_item.get("metadata") is None:
                directory_items.append({
                    "name": storage_item["name"],
                    "is_folder": True,
                    "full_path": item_full_path,
                    "size_bytes": 0
                })
            else:
                directory_items.append({
                    "name": storage_item["name"],
                    "is_folder": False,
                    "full_path": item_full_path,
                    "size_bytes": storage_item.get("metadata", {}).get("size", 0)
                })
                
    except Exception as error:
        flash(f"Failed to load directory contents: {error}", "error")
    
    # Generate navigation breadcrumbs
    navigation_trail = FileManagerHelper.build_navigation_trail(current_directory)
    
    return render_template("dashboard.html",
                         items=directory_items,
                         current_bucket=selected_bucket,
                         current_path=current_directory,
                         navigation=navigation_trail,
                         available_buckets=bucket_data,
                         helper=FileManagerHelper)

@application.route("/file_upload/<bucket_name>", methods=["POST"])
@error_handler
def handle_file_upload(bucket_name):
    """Process file uploads to specified bucket"""
    uploaded_file = request.files.get("file")
    target_directory = FileManagerHelper.clean_path(request.form.get("folder", ""))
    
    if not uploaded_file or uploaded_file.filename == "":
        flash("Please select a file to upload", "error")
        return redirect(url_for("home_page", bucket=bucket_name, folder=target_directory))
    
    # Construct file path
    if target_directory:
        file_destination = f"{target_directory}/{uploaded_file.filename}"
    else:
        file_destination = uploaded_file.filename
    
    # Upload to Supabase
    upload_result = supabase_client.storage.from_(bucket_name).upload(file_destination, uploaded_file.read())
    
    if isinstance(upload_result, dict) and upload_result.get("error"):
        flash(f"Upload error: {upload_result['error']['message']}", "error")
    else:
        flash(f"Successfully uploaded: {uploaded_file.filename}", "success")
    
    return redirect(url_for("home_page", bucket=bucket_name, folder=target_directory))

@application.route("/new_directory/<bucket_name>", methods=["POST"])
@error_handler
def create_new_directory(bucket_name):
    """Create a new directory in the specified bucket"""
    directory_name = request.form.get("folder_name", "").strip()
    parent_directory = FileManagerHelper.clean_path(request.form.get("parent_folder", ""))
    
    if not directory_name:
        flash("Directory name is required", "error")
        return redirect(url_for("home_page", bucket=bucket_name, folder=parent_directory))
    
    # Build directory path
    if parent_directory:
        new_directory_path = f"{parent_directory}/{directory_name}"
    else:
        new_directory_path = directory_name
    
    # Create directory by uploading a .keep file
    keep_file_path = f"{new_directory_path}/.keep"
    creation_result = supabase_client.storage.from_(bucket_name).upload(keep_file_path, b"")
    
    if isinstance(creation_result, dict) and creation_result.get("error"):
        flash(f"Directory creation failed: {creation_result['error']['message']}", "error")
    else:
        flash(f"Directory '{directory_name}' created successfully", "success")
    
    return redirect(url_for("home_page", bucket=bucket_name, folder=parent_directory))

@application.route("/remove_file/<bucket_name>")
@error_handler
def remove_file_item(bucket_name):
    """Delete a specific file from storage"""
    file_path = request.args.get("path")
    parent_folder = FileManagerHelper.clean_path(request.args.get("folder", ""))
    
    if not file_path:
        flash("File path is required for deletion", "error")
        return redirect(url_for("home_page", bucket=bucket_name, folder=parent_folder))
    
    deletion_result = supabase_client.storage.from_(bucket_name).remove([file_path])
    
    if isinstance(deletion_result, dict) and deletion_result.get("error"):
        flash(f"File deletion failed: {deletion_result['error']['message']}", "error")
    else:
        flash(f"Successfully deleted: {os.path.basename(file_path)}", "success")
    
    return redirect(url_for("home_page", bucket=bucket_name, folder=parent_folder))

@application.route("/remove_directory/<bucket_name>")
@error_handler
def remove_directory_item(bucket_name):
    """Delete an entire directory and its contents"""
    directory_path = request.args.get("path")
    parent_folder = FileManagerHelper.clean_path(request.args.get("parent", ""))
    
    if not directory_path:
        flash("Directory path is required for deletion", "error")
        return redirect(url_for("home_page", bucket=bucket_name, folder=parent_folder))
    
    # List all items in directory
    list_result = supabase_client.storage.from_(bucket_name).list(directory_path, {"limit": 1000})
    directory_contents = list_result if isinstance(list_result, list) else list_result.get("data", [])
    
    # Prepare deletion list
    files_to_delete = [f"{directory_path}/.keep"]  # Start with .keep file
    
    # Add all files in directory
    for content_item in directory_contents:
        if isinstance(content_item, dict) and content_item.get("name"):
            files_to_delete.append(f"{directory_path}/{content_item['name']}")
    
    if files_to_delete:
        deletion_result = supabase_client.storage.from_(bucket_name).remove(files_to_delete)
        if isinstance(deletion_result, dict) and deletion_result.get("error"):
            flash(f"Directory deletion failed: {deletion_result['error']['message']}", "error")
        else:
            flash(f"Directory '{os.path.basename(directory_path)}' removed successfully", "success")
    else:
        flash("Directory appears to be empty", "info")
    
    return redirect(url_for("home_page", bucket=bucket_name, folder=parent_folder))

@application.route("/duplicate_file/<bucket_name>", methods=["GET", "POST"])
@error_handler
def duplicate_file_item(bucket_name):
    """Create a copy of an existing file"""
    file_path = request.args.get("path")
    current_folder = FileManagerHelper.clean_path(request.args.get("folder", ""))
    
    if request.method == "GET":
        # Generate default copy name
        original_filename = os.path.basename(file_path)
        name_part, extension_part = os.path.splitext(original_filename)
        suggested_name = f"{name_part}_copy{extension_part}"
        
        if current_folder:
            suggested_path = f"{current_folder}/{suggested_name}"
        else:
            suggested_path = suggested_name
        
        return render_template("file_operation.html",
                             operation_type="Duplicate",
                             source_file=file_path,
                             bucket=bucket_name,
                             folder=current_folder,
                             suggested_path=suggested_path)
    
    # Handle POST request
    destination_path = request.form.get("new_path", "").strip()
    if not destination_path:
        flash("Destination path is required", "error")
        return redirect(url_for("home_page", bucket=bucket_name, folder=current_folder))
    
    # Download original file
    file_content = supabase_client.storage.from_(bucket_name).download(file_path)
    if isinstance(file_content, dict) and file_content.get("error"):
        flash(f"Failed to read original file: {file_content['error']['message']}", "error")
        return redirect(url_for("home_page", bucket=bucket_name, folder=current_folder))
    
    # Upload copy
    upload_result = supabase_client.storage.from_(bucket_name).upload(destination_path, file_content)
    if isinstance(upload_result, dict) and upload_result.get("error"):
        flash(f"Duplication failed: {upload_result['error']['message']}", "error")
    else:
        flash(f"File duplicated to: {destination_path}", "success")
    
    return redirect(url_for("home_page", bucket=bucket_name, folder=current_folder))

@application.route("/relocate_file/<bucket_name>", methods=["GET", "POST"])
@error_handler
def relocate_file_item(bucket_name):
    """Move a file to a different location"""
    file_path = request.args.get("path")
    current_folder = FileManagerHelper.clean_path(request.args.get("folder", ""))
    
    if request.method == "GET":
        # Generate default moved name
        original_filename = os.path.basename(file_path)
        name_part, extension_part = os.path.splitext(original_filename)
        suggested_name = f"{name_part}_relocated{extension_part}"
        
        if current_folder:
            suggested_path = f"{current_folder}/{suggested_name}"
        else:
            suggested_path = suggested_name
        
        return render_template("file_operation.html",
                             operation_type="Relocate",
                             source_file=file_path,
                             bucket=bucket_name,
                             folder=current_folder,
                             suggested_path=suggested_path)
    
    # Handle POST request
    destination_path = request.form.get("new_path", "").strip()
    if not destination_path:
        flash("Destination path is required", "error")
        return redirect(url_for("home_page", bucket=bucket_name, folder=current_folder))
    
    # Download original file
    file_content = supabase_client.storage.from_(bucket_name).download(file_path)
    if isinstance(file_content, dict) and file_content.get("error"):
        flash(f"Failed to access original file: {file_content['error']['message']}", "error")
        return redirect(url_for("home_page", bucket=bucket_name, folder=current_folder))
    
    # Upload to new location
    upload_result = supabase_client.storage.from_(bucket_name).upload(destination_path, file_content)
    if isinstance(upload_result, dict) and upload_result.get("error"):
        flash(f"Relocation failed: {upload_result['error']['message']}", "error")
        return redirect(url_for("home_page", bucket=bucket_name, folder=current_folder))
    
    # Remove original file
    removal_result = supabase_client.storage.from_(bucket_name).remove([file_path])
    if isinstance(removal_result, dict) and removal_result.get("error"):
        flash(f"File relocated but original couldn't be removed: {removal_result['error']['message']}", "warning")
    else:
        flash(f"File successfully relocated to: {destination_path}", "success")
    
    return redirect(url_for("home_page", bucket=bucket_name, folder=current_folder))

@application.route("/get_file/<bucket_name>")
@error_handler
def get_file_download(bucket_name):
    """Generate download link for file"""
    file_path = request.args.get("path")
    
    if not file_path:
        flash("File path is required for download", "error")
        return redirect(url_for("home_page", bucket=bucket_name))
    
    # Generate signed URL for download
    url_result = supabase_client.storage.from_(bucket_name).create_signed_url(file_path, 3600)
    
    if isinstance(url_result, dict) and url_result.get("error"):
        flash(f"Download link generation failed: {url_result['error']['message']}", "error")
    else:
        download_url = url_result.get("signedURL") if isinstance(url_result, dict) else None
        if download_url:
            return redirect(download_url)
        flash("Unable to generate download link", "error")
    
    parent_folder = FileManagerHelper.clean_path(os.path.dirname(file_path))
    return redirect(url_for("home_page", bucket=bucket_name, folder=parent_folder))

@application.route("/add_bucket", methods=["POST"])
@error_handler
def add_new_bucket():
    """Create a new storage bucket"""
    bucket_name = request.form.get("bucket_name", "").strip()
    current_bucket = request.form.get("current_bucket", "my-bucket")
    
    if not bucket_name:
        flash("Bucket name cannot be empty", "error")
        return redirect(url_for("home_page", bucket=current_bucket))
    
    # Create bucket using admin client
    creation_result = supabase_admin.storage.create_bucket(bucket_name)
    
    if isinstance(creation_result, dict) and creation_result.get("error"):
        flash(f"Bucket creation failed: {creation_result['error']['message']}", "error")
        return redirect(url_for("home_page", bucket=current_bucket))
    else:
        flash(f"Bucket '{bucket_name}' created successfully!", "success")
        return redirect(url_for("home_page", bucket=bucket_name))

@application.route("/remove_bucket/<bucket_name>")
@error_handler
def remove_bucket_completely(bucket_name):
    """Delete an entire storage bucket"""
    if not bucket_name:
        flash("Bucket name is required for deletion", "error")
        return redirect(url_for("home_page"))
    
    # Delete bucket using admin client
    deletion_result = supabase_admin.storage.delete_bucket(bucket_name)
    
    if isinstance(deletion_result, dict) and deletion_result.get("error"):
        flash(f"Bucket deletion failed: {deletion_result['error']['message']}", "error")
        return redirect(url_for("home_page", bucket=bucket_name))
    else:
        flash(f"Bucket '{bucket_name}' has been deleted", "success")
        
        # Redirect to first available bucket
        available_buckets = FileManagerHelper.fetch_all_buckets()
        fallback_bucket = "my-bucket"
        
        if available_buckets and len(available_buckets) > 0:
            first_available = available_buckets[0]
            if hasattr(first_available, 'name'):
                fallback_bucket = first_available.name
            elif isinstance(first_available, dict):
                fallback_bucket = first_available.get("name", "my-bucket")
            else:
                fallback_bucket = str(first_available)
        
        return redirect(url_for("home_page", bucket=fallback_bucket))

@application.route("/bucket_info")
@error_handler
def show_bucket_information():
    """Display detailed information about all buckets"""
    try:
        all_buckets = FileManagerHelper.fetch_all_buckets()
        bucket_details = []
        
        for bucket_item in all_buckets:
            if hasattr(bucket_item, 'name'):
                bucket_details.append({
                    "name": bucket_item.name,
                    "id": getattr(bucket_item, 'id', 'Not Available'),
                    "created_at": getattr(bucket_item, 'created_at', 'Not Available')
                })
            elif isinstance(bucket_item, dict):
                bucket_details.append({
                    "name": bucket_item.get("name", "Unknown"),
                    "id": bucket_item.get("id", "Not Available"),
                    "created_at": bucket_item.get("created_at", "Not Available")
                })
            else:
                bucket_details.append({
                    "name": str(bucket_item),
                    "id": "Not Available",
                    "created_at": "Not Available"
                })
        
        flash(f"Total buckets found: {len(bucket_details)}. Details logged to console.", "info")
        print("Bucket Information:", bucket_details)
        
    except Exception as error:
        flash(f"Error retrieving bucket information: {error}", "error")
    
    return redirect(url_for("home_page"))

if __name__ == "__main__":
    application.run(debug=True, host="0.0.0.0", port=5000)