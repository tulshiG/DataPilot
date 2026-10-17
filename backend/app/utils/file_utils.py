import os
import uuid
from fastapi import UploadFile
from app.core.constants import ALLOWED_FILE_EXTENSIONS, MAX_FILE_SIZE_MB, UPLOAD_DIR
from app.core.exceptions import BadRequestException

# def validate_csv_file(file: UploadFile):
#     ext = os.path.splitext(file.filename)[1].lower()
#     if ext not in ALLOWED_FILE_EXTENSIONS:
#         raise BadRequestException(f"Invalid file type: {file.filename}. Only CSV allowed.")
def validate_csv_file(file: UploadFile):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_FILE_EXTENSIONS:
        raise BadRequestException(f"Invalid file type: {file.filename}. Only CSV allowed.")

    if not file.filename or file.filename.strip() == "":
        raise BadRequestException("File must have a valid name.")

    # Guard against path traversal in filenames
    if ".." in file.filename or "/" in file.filename or "\\" in file.filename:
        raise BadRequestException("Invalid filename.")

def generate_stored_filename(original_filename: str) -> str:
    ext = os.path.splitext(original_filename)[1]
    return f"{uuid.uuid4().hex}{ext}"

def save_upload_file(file: UploadFile, workspace_id: int) -> tuple[str, str, int]:
    """Returns (stored_filename, full_path, file_size_bytes)"""
    workspace_dir = os.path.join(UPLOAD_DIR, str(workspace_id))
    os.makedirs(workspace_dir, exist_ok=True)

    stored_filename = generate_stored_filename(file.filename)
    full_path = os.path.join(workspace_dir, stored_filename)

    contents = file.file.read()
    file_size = len(contents)

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise BadRequestException(f"{file.filename} exceeds {MAX_FILE_SIZE_MB}MB limit")

    with open(full_path, "wb") as f:
        f.write(contents)

    return stored_filename, full_path, file_size