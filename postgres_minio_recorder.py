# connect to postgres and minio
# create a table in postgres that records the minio object path and its unique id etag
# use streamlit to create a web app that allows you to select a minio bucket and a folder to be added to the table
# use the web app to add the minio object path and its unique id etag to the table
# use the web app to view the table

import streamlit as st
import psycopg2
from minio import Minio
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# PostgreSQL connection parameters
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'postgres')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')

# MinIO connection parameters
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')

def init_postgres_connection():
    """Initialize PostgreSQL connection and create table if it doesn't exist"""
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    
    with conn.cursor() as cur:
        # Create table if it doesn't exist (without constraint first)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS minio_objects (
                id SERIAL PRIMARY KEY,
                bucket_name VARCHAR(255),
                object_path VARCHAR(1000),
                etag VARCHAR(255),
                size BIGINT,
                last_modified TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Try to add unique constraint if it doesn't exist
        try:
            cur.execute("""
                ALTER TABLE minio_objects 
                ADD CONSTRAINT minio_objects_bucket_path_key 
                UNIQUE (bucket_name, object_path)
            """)
        except psycopg2.errors.DuplicateTable:
            # Constraint already exists, ignore
            pass
        
    conn.commit()
    return conn

def init_minio_client():
    """Initialize MinIO client"""
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False  # Set to True if using HTTPS
    )

def list_buckets(minio_client):
    """List all MinIO buckets"""
    return [bucket.name for bucket in minio_client.list_buckets()]

def list_objects_in_bucket(minio_client, bucket_name, prefix=""):
    """List all objects in a bucket with optional prefix"""
    objects = minio_client.list_objects(bucket_name, prefix=prefix, recursive=True)
    return objects

def record_objects(conn, bucket_name, objects):
    """Record objects in PostgreSQL database"""
    with conn.cursor() as cur:
        for obj in objects:
            cur.execute("""
                INSERT INTO minio_objects 
                (bucket_name, object_path, etag, size, last_modified)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (bucket_name, object_path) DO UPDATE 
                SET etag = EXCLUDED.etag,
                    size = EXCLUDED.size,
                    last_modified = EXCLUDED.last_modified
            """, (
                bucket_name,
                obj.object_name,
                obj.etag,
                obj.size,
                obj.last_modified
            ))
    conn.commit()

def view_recorded_objects(conn):
    """Retrieve recorded objects from database"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT bucket_name, object_path, etag, size, last_modified, created_at 
            FROM minio_objects 
            ORDER BY created_at DESC
        """)
        return cur.fetchall()

def get_folder_structure(minio_client, bucket_name, prefix=""):
    """Get folders and objects at current prefix level"""
    objects = minio_client.list_objects(bucket_name, prefix=prefix, recursive=False)
    folders = set()
    files = []

    for obj in objects:
        path = obj.object_name
        if prefix:
            # Remove prefix from path for display
            path = path[len(prefix):]
        
        # If object name ends with /, it's a folder
        if obj.object_name.endswith('/'):
            folders.add(obj.object_name)
        # If path contains /, it's inside a folder
        elif '/' in path:
            folder = prefix + path.split('/')[0] + '/'
            folders.add(folder)
        else:
            files.append(obj)

    return sorted(list(folders)), files

def get_parent_folder(current_prefix):
    """Get parent folder path"""
    if not current_prefix:
        return ""
    parts = current_prefix.rstrip('/').split('/')
    if len(parts) > 1:
        return '/'.join(parts[:-1]) + '/'
    return ""

def format_size(size_bytes):
    """Format size in bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"

def main():
    st.title("MinIO Object Recorder")

    try:
        # Initialize connections
        postgres_conn = init_postgres_connection()
        minio_client = init_minio_client()

        # Create tabs
        tab1, tab2 = st.tabs(["Browse & Record", "View Records"])

        with tab1:
            st.header("Browse MinIO Objects")
            
            # Bucket selection
            buckets = list_buckets(minio_client)
            if 'selected_bucket' not in st.session_state:
                st.session_state.selected_bucket = buckets[0] if buckets else None
            
            selected_bucket = st.selectbox("Select Bucket", buckets, 
                                         key='bucket_selector',
                                         index=buckets.index(st.session_state.selected_bucket) if st.session_state.selected_bucket in buckets else 0)
            
            if selected_bucket != st.session_state.selected_bucket:
                st.session_state.selected_bucket = selected_bucket
                st.session_state.current_path = ""
                st.rerun()

            # Initialize session state for current path
            if 'current_path' not in st.session_state:
                st.session_state.current_path = ""

            # Breadcrumb navigation
            path_parts = [("Root", "")]
            current = ""
            for part in st.session_state.current_path.split('/'):
                if part:
                    current += part + "/"
                    path_parts.append((part, current))

            # Display breadcrumb
            st.write("Current location: " + " / ".join(name for name, _ in path_parts))

            # Back button
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.session_state.current_path and st.button("⬅️ Back"):
                    st.session_state.current_path = get_parent_folder(st.session_state.current_path)
                    st.rerun()

            # Get folders and files at current path
            folders, files = get_folder_structure(minio_client, selected_bucket, st.session_state.current_path)

            # Display folders
            if folders:
                st.subheader("Folders")
                cols = st.columns(3)
                for i, folder in enumerate(folders):
                    display_name = folder.replace(st.session_state.current_path, '').rstrip('/')
                    if cols[i % 3].button(f"📁 {display_name}"):
                        st.session_state.current_path = folder
                        st.rerun()

            # Display files with checkboxes
            if files:
                st.subheader("Files")
                
                # Add select all checkbox
                select_all = st.checkbox("Select All Files")
                
                # Create a DataFrame for files
                file_data = []
                for obj in files:
                    file_key = f"file_{obj.object_name}"
                    file_data.append({
                        "Selected": st.checkbox(
                            f"{obj.object_name.split('/')[-1]}", 
                            value=select_all,
                            key=file_key
                        ),
                        "Name": obj.object_name.split('/')[-1],
                        "Size": format_size(obj.size),
                        "Last Modified": obj.last_modified.strftime("%Y-%m-%d %H:%M:%S"),
                        "Object": obj
                    })
                
                if file_data:
                    import pandas as pd
                    df = pd.DataFrame(file_data)
                    selected_files = [row["Object"] for _, row in df.iterrows() if row["Selected"]]

                    # Display file information
                    st.dataframe(df[["Name", "Size", "Last Modified"]])

                    # Show selection summary
                    if selected_files:
                        st.info(f"Selected {len(selected_files)} files")

                        # Record selected files
                        col1, col2 = st.columns([1, 5])
                        with col1:
                            if st.button("📥 Record Selected", type="primary"):
                                with st.spinner("Recording selected objects..."):
                                    record_objects(postgres_conn, selected_bucket, selected_files)
                                    st.success(f"Successfully recorded {len(selected_files)} objects!")
                                    # Clear selections after recording
                                    st.rerun()

        with tab2:
            st.header("View Recorded Objects")
            
            if st.button("🔄 Refresh Records"):
                records = view_recorded_objects(postgres_conn)
                
                if not records:
                    st.info("No records found in the database.")
                else:
                    import pandas as pd
                    df = pd.DataFrame(
                        records,
                        columns=['Bucket', 'Object Path', 'ETag', 'Size (bytes)', 
                                'Last Modified', 'Recorded At']
                    )
                    # Format size column
                    df['Size (bytes)'] = df['Size (bytes)'].apply(format_size)
                    st.dataframe(df)

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")

    finally:
        if 'postgres_conn' in locals():
            postgres_conn.close()

if __name__ == "__main__":
    main()

