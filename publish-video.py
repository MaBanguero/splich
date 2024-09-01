from modules.facebook_video_uploader import FacebookVideoUploader

def main():
    app_id = '804707638525776'
    page_id = '438383526014976'
    page_access_token = '<PAGE_ACCESS_TOKEN>'

    uploader = FacebookVideoUploader(app_id=app_id, page_id=page_id, page_access_token=page_access_token)
    uploader.publish_videos(limit=5)
    print("Videos subidos:", uploader.get_uploaded_videos())

if __name__ == "__main__":
    main()
