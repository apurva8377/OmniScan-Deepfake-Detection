import streamlit as st
import torch
import torch.nn as nn
import torchvision.models as models
from torchvision import transforms
from PIL import Image
import cv2
import tempfile
import numpy as np

# ==========================================
# 1. THE ARCHITECTURE BLUEPRINT (ResNeXt)
# ==========================================
class DeepfakeSequenceModel(nn.Module):
    def __init__(self, num_classes=2, lstm_layers=1, hidden_dim=2048, bidirectional=False):
        super(DeepfakeSequenceModel, self).__init__()
        # 1. ResNeXt backbone
        resnext = models.resnext50_32x4d(weights=None)
        self.model = nn.Sequential(*list(resnext.children())[:-1])
        
        # 2. LSTM with bias explicitly turned OFF to match their weights
        self.lstm = nn.LSTM(
            input_size=2048, hidden_size=hidden_dim,
            num_layers=lstm_layers, batch_first=True, bidirectional=bidirectional,
            bias=False  # <-- This fixes the missing bias error
        )
        
        # 3. Raw Linear Layer (NOT wrapped in Sequential)
        lstm_output_dim = hidden_dim * 2 if bidirectional else hidden_dim
        self.linear1 = nn.Linear(lstm_output_dim, num_classes)  # <-- This fixes the linear1 error

    def forward(self, x):
        batch_size, seq_length, c, h, w = x.size()
        x = x.view(batch_size * seq_length, c, h, w)
        
        # Pass through ResNeXt
        features = self.model(x)
        features = features.view(features.size(0), -1) 
        features = features.view(batch_size, seq_length, -1)
        
        # Pass through LSTM
        lstm_out, _ = self.lstm(features)
        last_frame_output = lstm_out[:, -1, :]
        
        # Pass through final linear layer
        return self.linear1(last_frame_output)

# ==========================================
# 2. CACHE THE BRAIN (Streamlit Superpower)
# ==========================================
@st.cache_resource
def load_model():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = DeepfakeSequenceModel().to(device)
    
    # Point this to your downloaded .pt file!
    model_path = "saved_models/model_90_acc_20_frames_FF_data.pt"
    
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval() # Lock it in prediction mode
    return model, device

model, device = load_model()

# ==========================================
# 3. VIDEO PROCESSING PIPELINE
# ==========================================
def process_video(video_bytes, sequence_length=20):
    # Save uploaded video to a temporary file for OpenCV to read
    tfile = tempfile.NamedTemporaryFile(delete=False) 
    tfile.write(video_bytes)
    
    cap = cv2.VideoCapture(tfile.name)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Calculate which frames to pull so we get exactly 60 evenly spaced frames
    skip_frames = max(int(total_frames / sequence_length), 1)
    
    frames = []
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    frame_count = 0
    while len(frames) < sequence_length and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count % skip_frames == 0:
            # Convert OpenCV (BGR) to standard RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            tensor_img = transform(pil_img)
            frames.append(tensor_img)
            
        frame_count += 1

    cap.release()
    
    # Pad with black frames if the video was too short
    while len(frames) < sequence_length:
        frames.append(torch.zeros((3, 224, 224)))

    # Stack into a single tensor and add a batch dimension: [1, 60, 3, 224, 224]
    return torch.stack(frames).unsqueeze(0)

# ==========================================
# 4. THE WEB DASHBOARD UI
# ==========================================
st.title("🛡️ Deepfake Video Detector")
st.write("Upload an MP4 video to analyze it for spatial-temporal deepfake artifacts.")

uploaded_video = st.file_uploader("Choose a video file", type=["mp4", "avi", "mov"])

if uploaded_video is not None:
    st.video(uploaded_video)
    
    if st.button("🕵️ Analyze Video"):
        with st.spinner("Extracting frames and running AI analysis... This may take a moment."):
            
            # 1. Process the video (This was the missing line!)
            video_bytes = uploaded_video.read()
            video_tensor = process_video(video_bytes, sequence_length=20).to(device)
            
            # 2. Make the prediction
            with torch.no_grad():
                logits = model(video_tensor)
                # Convert raw scores into two percentages (0 to 1)
                probabilities = torch.nn.functional.softmax(logits, dim=1).squeeze()
                
                # Extract the two probabilities
                class_0_prob = probabilities[0].item()
                class_1_prob = probabilities[1].item()
            
            # 3. Display Results
            st.markdown("---")
            
            # Compare the two output nodes
            if class_0_prob > class_1_prob:
                st.error(f"🚨 **FAKE VIDEO DETECTED** (Confidence: {class_0_prob * 100:.2f}%)")
            else:
                st.success(f"✅ **REAL VIDEO** (Confidence: {class_1_prob * 100:.2f}%)")