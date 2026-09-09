import os
import tempfile

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from moviepy import VideoFileClip
from transformers import pipeline

# ==========================================
# 3. THE AUDIO PROCESSOR (Wav2Vec2)
# ==========================================

print("🧠 Booting up the Audio Deepfake Engine...")
# NOTE: The very first time you run this, it will download a ~350MB weights file from Hugging Face.
# After the first download, it will cache it locally and load instantly.
audio_model_path = "./saved_models/audio_model"
audio_classifier = pipeline("audio-classification", model=audio_model_path)

def process_audio_scan(video_path):
    temp_audio_path = None
    try:
        # 1. Rip the audio from the video file
        video_clip = VideoFileClip(video_path)
        
        # Security check: Does the video actually have sound?
        if video_clip.audio is None:
            video_clip.close()
            return None, "No audio track found in the video."

        # Create a temporary .wav file to hold the ripped audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            temp_audio_path = temp_audio.name
        
        # Write the audio to the temp file (logger=None hides the messy terminal progress bars)
        video_clip.audio.write_audiofile(temp_audio_path, logger=None)
        video_clip.close()

        # 2. Feed the audio to the Hugging Face AI
        results = audio_classifier(temp_audio_path)
        
        # 3. Parse the results
        # Hugging Face returns a list like: [{'label': 'fake', 'score': 0.95}, {'label': 'real', 'score': 0.05}]
        fake_score = 0.0
        real_score = 0.0
        
        for res in results:
            label = res['label'].lower()
            if label == 'fake' or label == 'spoof':
                fake_score = res['score']
            else:
                real_score = res['score']

        return {
            'fake_prob': fake_score,
            'real_prob': real_score
        }, None

    except Exception as e:
        return None, str(e)
        
    finally:
        # 4. Clean up the evidence! Delete the temp audio file so your hard drive doesn't fill up.
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)