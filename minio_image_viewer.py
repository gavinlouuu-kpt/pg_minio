# a web app that allows you to view images from minio
# it should have a simple interface to enter the minio endpoint, access key, and secret key
# it should have a simple interface with a dropdown to select the bucket and a list of images
# it should also have a search bar to search for images
# it should also have a button to download the image
# it should also have a button to upload a new image

import streamlit as st
import io
import os
from minio import Minio
from minio.error import S3Error
from PIL import Image
import tempfile

def main():
    st.title("MinIO Image Viewer")
    
    # Connection settings
    with st.sidebar:
        st.header("MinIO Connection")
        endpoint = st.text_input("Endpoint", value="localhost:9000")
        access_key = st.text_input("Access Key", value="minioadmin")
        secret_key = st.text_input("Secret Key", value="minioadmin", type="password")
        secure = st.checkbox("Secure (HTTPS)", value=False)
        
        if st.button("Connect"):
            if not endpoint or not access_key or not secret_key:
                st.error("Please fill in all connection details")
            else:
                st.session_state.client = create_minio_client(endpoint, access_key, secret_key, secure)
                st.session_state.connected = True
                st.success("Connected to MinIO")
                st.session_state.buckets = list_buckets(st.session_state.client)
    
    # Main content
    if 'connected' in st.session_state and st.session_state.connected:
        # Initialize current path in session state if not exists
        if 'current_path' not in st.session_state:
            st.session_state.current_path = ""
        
        # Bucket selection
        selected_bucket = st.selectbox("Select Bucket", st.session_state.buckets)
        
        if selected_bucket:
            # Path bar styling
            st.markdown("""
                <style>
                    .path-bar {
                        background-color: #1e2a35;
                        padding: 10px;
                        border-radius: 4px;
                        margin-bottom: 10px;
                    }
                    .back-button {
                        margin-right: 10px;
                        margin-top: 5px;
                    }
                    .nav-container {
                        display: flex;
                        align-items: center;
                        gap: 10px;
                    }
                </style>
            """, unsafe_allow_html=True)
            
            # Path display in MinIO style
            current_path = f"{selected_bucket} / {st.session_state.current_path}" if st.session_state.current_path else selected_bucket
            
            # Navigation container
            col1, col2 = st.columns([6, 1])
            with col1:
                # Back button and path in one column
                if st.session_state.current_path:
                    cols = st.columns([0.5, 5.5])
                    with cols[0]:
                        st.button("←", key="back_btn")
                    with cols[1]:
                        st.markdown(f"<div class='path-bar'>{current_path}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='path-bar'>{current_path}</div>", unsafe_allow_html=True)
            
            with col2:
                st.button("Refresh", key="refresh_btn")
            
            # Search bar
            search_term = st.text_input("Search", placeholder="Search for objects...")
            
            # List contents
            contents = list_contents(
                st.session_state.client, 
                selected_bucket, 
                st.session_state.current_path,
                search_term
            )
            
            # Display contents in a table view
            if contents['folders'] or contents['images']:
                # Create table header
                header_cols = st.columns([0.5, 3, 2, 1])
                header_cols[0].write("☐")  # Checkbox column
                header_cols[1].write("Name")
                header_cols[2].write("Last Modified")
                header_cols[3].write("Size")
                
                st.markdown("<hr style='margin: 5px 0px'>", unsafe_allow_html=True)
                
                # Display folders first
                for folder in contents['folders']:
                    folder_name = folder.rstrip('/')
                    base_name = os.path.basename(folder_name)
                    
                    cols = st.columns([0.5, 3, 2, 1])
                    cols[0].write("☐")
                    if cols[1].button(f"📁 {base_name}", key=f"folder_{folder_name}"):
                        st.session_state.current_path = folder
                        st.rerun()
                    cols[2].write("-")
                    cols[3].write("-")
                
                # Display images
                for image_name in contents['images']:
                    try:
                        stat = st.session_state.client.stat_object(selected_bucket, image_name)
                        base_name = os.path.basename(image_name)
                        
                        cols = st.columns([0.5, 3, 2, 1])
                        cols[0].write("☐")
                        
                        # Name column with preview functionality
                        if cols[1].button(f"🖼️ {base_name}", key=f"file_{image_name}"):
                            st.session_state.preview_image = image_name
                        
                        # Last modified
                        cols[2].write(stat.last_modified.strftime("%Y-%m-%d %H:%M"))
                        
                        # Size
                        cols[3].write(format_size(stat.size))
                        
                    except Exception as e:
                        st.error(f"Error displaying {image_name}: {str(e)}")
            
            # Preview modal
            if 'preview_image' in st.session_state and st.session_state.preview_image:
                with st.sidebar:
                    st.subheader("Preview")
                    try:
                        image_data = get_image(
                            st.session_state.client,
                            selected_bucket,
                            st.session_state.preview_image,
                            convert_to_png=True  # Convert to PNG for preview
                        )
                        st.image(
                            image_data, 
                            use_container_width=True
                        )
                        
                        # Download button below preview - use original format
                        original_image_data = get_image(
                            st.session_state.client,
                            selected_bucket,
                            st.session_state.preview_image,
                            convert_to_png=False
                        )
                        st.download_button(
                            "Download",
                            data=original_image_data,
                            file_name=os.path.basename(st.session_state.preview_image),
                            mime="application/octet-stream"
                        )
                        
                        if st.button("Close"):
                            del st.session_state.preview_image
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error displaying preview: {str(e)}")
                        del st.session_state.preview_image
            
            # Upload new image
            with st.expander("Upload New Image"):
                upload_file = st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png", "gif"])
                upload_path = st.text_input("Object name (optional)")
                
                if st.button("Upload") and upload_file is not None:
                    object_name = upload_path if upload_path else upload_file.name
                    upload_image(st.session_state.client, selected_bucket, object_name, upload_file)
                    st.success(f"Uploaded {object_name} to {selected_bucket}")
                    # Refresh image list
                    contents = list_contents(st.session_state.client, selected_bucket, st.session_state.current_path, search_term)

def create_minio_client(endpoint, access_key, secret_key, secure=False):
    """Create and return a MinIO client."""
    try:
        client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        return client
    except Exception as e:
        st.error(f"Failed to connect to MinIO: {str(e)}")
        return None

def list_buckets(client):
    """List all buckets in the MinIO instance."""
    try:
        buckets = client.list_buckets()
        return [bucket.name for bucket in buckets]
    except S3Error as e:
        st.error(f"Error listing buckets: {str(e)}")
        return []

def list_contents(client, bucket_name, prefix="", search_term=""):
    """List folders and images in a bucket with the given prefix."""
    try:
        objects = client.list_objects(bucket_name, prefix=prefix, recursive=False)
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        
        folders = set()
        images = []
        
        for obj in objects:
            object_name = obj.object_name
            
            # Skip the current prefix itself
            if object_name == prefix:
                continue
                
            # Handle folders
            if object_name.endswith('/'):
                folders.add(object_name)
            # Handle nested folders (objects with / in their name after the prefix)
            elif '/' in object_name[len(prefix):]:
                folder_path = object_name[:object_name.find('/', len(prefix)) + 1]
                folders.add(folder_path)
            # Handle images
            elif any(object_name.lower().endswith(ext) for ext in image_extensions):
                if not search_term or search_term.lower() in os.path.basename(object_name).lower():
                    images.append(object_name)
        
        return {
            'folders': sorted(list(folders)),
            'images': sorted(images)
        }
    except S3Error as e:
        st.error(f"Error listing objects in bucket {bucket_name}: {str(e)}")
        return {'folders': [], 'images': []}

def list_images(client, bucket_name, search_term=""):
    """List all images in a bucket, optionally filtered by search term."""
    if 'current_path' not in st.session_state:
        st.session_state.current_path = ""
    contents = list_contents(client, bucket_name, st.session_state.current_path, search_term)
    return contents['images']

def get_image(client, bucket_name, object_name, convert_to_png=False):
    """Get image data from MinIO. Optionally convert to PNG format."""
    try:
        response = client.get_object(bucket_name, object_name)
        image_data = response.read()
        response.close()
        response.release_conn()
        
        if convert_to_png:
            # Convert image to PNG using PIL
            image = Image.open(io.BytesIO(image_data))
            # Convert to RGB if image is in RGBA or other modes
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save as PNG to bytes buffer
            buf = io.BytesIO()
            image.save(buf, format='PNG')
            return buf.getvalue()
            
        return image_data
    except S3Error as e:
        st.error(f"Error retrieving {object_name}: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Error processing {object_name}: {str(e)}")
        return None

def download_image(client, bucket_name, object_name):
    """Download an image and provide it to the user."""
    try:
        image_data = get_image(client, bucket_name, object_name)
        return image_data
    except Exception as e:
        st.error(f"Error downloading {object_name}: {str(e)}")
        return None

def upload_image(client, bucket_name, object_name, file_data):
    """Upload an image to MinIO."""
    try:
        # Create a temporary file to get the file size
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file_data.getvalue())
            temp_file_path = temp_file.name
        
        # Get file size
        file_size = os.path.getsize(temp_file_path)
        
        # Upload the file
        client.put_object(
            bucket_name,
            object_name,
            io.BytesIO(file_data.getvalue()),
            file_size,
            content_type=file_data.type
        )
        
        # Clean up the temporary file
        os.unlink(temp_file_path)
        
        return True
    except S3Error as e:
        st.error(f"Error uploading {object_name}: {str(e)}")
        return False

def format_size(size_in_bytes):
    """Format file size in human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.1f} PB"

if __name__ == "__main__":
    main()
