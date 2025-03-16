# MinIO Image Viewer

A simple web application built with Streamlit that allows users to browse, view, search, download, and upload images stored in MinIO object storage.

## Features

- **MinIO Connection**: Connect to any MinIO server with endpoint, access key, and secret key
- **Directory Navigation**: Browse through directories in MinIO buckets
- **Image Viewing**: View images in a responsive grid layout
- **Pagination**: Navigate through large collections of images with pagination controls
- **Search**: Filter images by filename
- **Upload**: Upload new images to the current directory
- **Download**: Download images directly from the viewer

## Requirements

- Python 3.7+
- Streamlit
- MinIO Python Client
- Pillow (PIL)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/minio-image-viewer.git
   cd minio-image-viewer
   ```

2. Install the required packages:
   ```bash
   pip install streamlit minio pillow
   ```

3. Run the application:
   ```bash
   streamlit run minio_image_viewer.py
   ```

## Usage

### Connecting to MinIO

1. Enter your MinIO server details in the sidebar:
   - Endpoint (e.g., `localhost:9000`)
   - Access Key (default: `minioadmin`)
   - Secret Key (default: `minioadmin`)
   - Check "Secure (HTTPS)" if your MinIO server uses HTTPS

2. Click "Connect" to establish a connection to your MinIO server

### Browsing Images

1. Select a bucket from the dropdown menu
2. Navigate through directories by clicking on folder icons
3. Use the breadcrumb navigation at the top to move up in the directory structure
4. Click "🏠 Root" to return to the root directory
5. Click "⬆️ Up" to move up one directory level

### Viewing Images

- Images are displayed in a 3x3 grid
- Use pagination controls to navigate through large collections of images
- You can jump to a specific page using the page number input

### Searching Images

- Use the search bar to filter images by filename
- The search is case-insensitive and matches any part of the filename

### Uploading Images

1. Click on the "Upload New Image" expander
2. Choose an image file using the file uploader
3. Optionally, provide a custom object name
4. Click "Upload" to upload the image to the current directory

### Downloading Images

- Click the "Download" button below any image to download it to your local machine

