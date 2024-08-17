from pydub import AudioSegment
import pyttsx3

def duplicate_voice(audio_path, output_path):
    audio = AudioSegment.from_file(audio_path)
    duplicated_audio = audio + audio
    duplicated_audio.export(output_path, format="wav")
    return output_path

def text_to_speech(text, output_path, duplicated_voice_path=None):
    engine = pyttsx3.init()
    if duplicated_voice_path:
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        duplicated_audio = AudioSegment.from_file(duplicated_voice_path)
        tts_audio = AudioSegment.from_file(output_path)
        combined_audio = duplicated_audio.overlay(tts_audio)
        combined_audio.export(output_path, format="wav")
    else:
        engine.save_to_file(text, output_path)
        engine.runAndWait()
    return output_path
