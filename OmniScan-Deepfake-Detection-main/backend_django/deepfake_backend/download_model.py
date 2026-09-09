import os
# Force the unblocked mirror server
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from transformers import pipeline

print("🌐 Contacting mirror server to download the model...")
# 1. Download the model into RAM
audio_classifier = pipeline("audio-classification", model="MelodyMachine/Deepfake-audio-detection-V2")

print("💾 Saving model completely offline...")
# 2. Save the entire pipeline (weights, configs, and extractors) to a local folder!
audio_classifier.save_pretrained("./saved_audio_model")

print("✅ SUCCESS! The model is now saved in the 'saved_audio_model' folder.")
