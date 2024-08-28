import os
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
from subtitle_utils import add_subtitles

LOCAL_FOLDER = '/tmp'
OUTPUT_FOLDER = 'reels'
FRAGMENT_DURATION = 90

def process_video_fragment(video_clip, audio_clip, music_clip, start_time, fragment_index, video_filename, subtitles):
    end_time = min(start_time + FRAGMENT_DURATION, video_clip.duration)
    video_fragment = video_clip.subclip(start_time, end_time)
    voice_fragment = audio_clip.subclip(start_time, end_time)
    music_fragment = music_clip.subclip(0, min(90, video_fragment.duration)).volumex(0.25)

    combined_audio = CompositeAudioClip([voice_fragment, music_fragment])
    final_video_fragment = video_fragment.set_audio(combined_audio).fl(lambda gf, t: add_subtitles(gf, t, subtitles))

    fragment_filename = f"fragment_{fragment_index}_{video_filename}"
    fragment_path = os.path.join(LOCAL_FOLDER, fragment_filename)
    final_video_fragment.write_videofile(fragment_path, codec='libx264', audio_codec='aac')

    return fragment_path