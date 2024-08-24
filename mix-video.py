import os
import random
import boto3
from moviepy.editor import VideoFileClip, concatenate_videoclips

# Initialize S3 client
s3 = boto3.client('s3')

# S3 Bucket and Folder details
BUCKET_NAME = 'facebook-videos-bucket'
VIDEO_FOLDER = 'video-to-mix'
LOCAL_FOLDER = '/tmp'
OUTPUT_FOLDER = 'video-to-mix'
LOG_FILE = 'processed_videos.log'  # Log file to track processed videos

def download_from_s3(s3_key, local_path):
    s3.download_file(BUCKET_NAME, s3_key, local_path)
    print(f"Downloaded {s3_key} to {local_path}")

def upload_to_s3(local_path, s3_key):
    s3.upload_file(local_path, BUCKET_NAME, s3_key)
    print(f"Uploaded {local_path} to {s3_key}")

def create_random_subclips_and_combine(video_path, output_folder, min_duration=30, max_duration=100):
    # Load the video
    video = VideoFileClip(video_path)
    
    start_time = 0
    clip_index = 1
    subclips = []
    
    while start_time < video.duration:
        # Generate a random duration between min_duration and max_duration
        random_duration = random.uniform(min_duration, max_duration)
        end_time = min(start_time + random_duration, video.duration)
        
        # Extract the subclip
        subclip = video.subclip(start_time, end_time)
        subclips.append(subclip)
        
        start_time = end_time
        clip_index += 1

    # Combine all the subclips into a single video
    final_video = concatenate_videoclips(subclips)
    
    # Create a filename for the final combined video
    final_video_filename = f"combined_video_{os.path.basename(video_path)}"
    final_video_path = os.path.join(output_folder, final_video_filename)
    
    # Write the final video to a file
    final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac")
    
    return final_video_path

def load_processed_videos():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, 'r') as log_file:
        processed_videos = {line.strip() for line in log_file}
    return processed_videos

def log_processed_video(video_filename):
    with open(LOG_FILE, 'a') as log_file:
        log_file.write(video_filename + '\n')

def process_video_from_s3(video_s3_key):
    video_filename = os.path.basename(video_s3_key)
    local_video_path = os.path.join(LOCAL_FOLDER, video_filename)
    
    # Download the video from S3
    download_from_s3(video_s3_key, local_video_path)
    
    # Create subclips and combine them into a final video
    final_video_path = create_random_subclips_and_combine(local_video_path, LOCAL_FOLDER)
    
    # Upload the final combined video back to S3
    upload_to_s3(final_video_path, f"{OUTPUT_FOLDER}/{os.path.basename(final_video_path)}")
    
    # Log the processed video
    log_processed_video(video_filename)
    
    # Cleanup local files
    os.remove(local_video_path)
    os.remove(final_video_path)
    print("Processing complete and files cleaned up.")

def process_all_videos():
    # Load the list of already processed videos
    processed_videos = load_processed_videos()
    
    # List all videos in the S3 folder
    s3_video_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=VIDEO_FOLDER).get('Contents', [])
    video_files = [obj['Key'] for obj in s3_video_objects if obj['Key'].endswith('.mp4')]
    
    for video_s3_key in video_files:
        video_filename = os.path.basename(video_s3_key)
        
        if video_filename in processed_videos:
            print(f"Video {video_filename} already processed. Skipping.")
            continue
        
        print(f"Processing video {video_filename}...")
        process_video_from_s3(video_s3_key)

if __name__ == "__main__":
    process_all_videos()
