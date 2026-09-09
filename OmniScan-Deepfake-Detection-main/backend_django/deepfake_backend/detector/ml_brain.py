import os
import io
import base64
import cv2
import torch
import torch.nn as nn         
from torchvision import models  
import numpy as np
from PIL import Image
from torchvision import transforms

# === Existing device setup and transforms (UNCHANGED) ===
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

class DeepfakeSequenceModel(nn.Module):
    def __init__(self, num_classes=2, lstm_layers=1, hidden_dim=2048, bidirectional=False):
        super(DeepfakeSequenceModel, self).__init__()
        resnext = models.resnext50_32x4d(weights=None)
        self.model = nn.Sequential(*list(resnext.children())[:-1])
        
        self.lstm = nn.LSTM(
            input_size=2048, hidden_size=hidden_dim,
            num_layers=lstm_layers, batch_first=True, bidirectional=bidirectional,
            bias=False
        )
        self.linear1 = nn.Linear(hidden_dim * 2 if bidirectional else hidden_dim, num_classes)

    def forward(self, x):
        batch_size, seq_length, c, h, w = x.size()
        x = x.view(batch_size * seq_length, c, h, w)
        features = self.model(x)
        features = features.view(features.size(0), -1) 
        features = features.view(batch_size, seq_length, -1)
        lstm_out, _ = self.lstm(features)
        return self.linear1(lstm_out[:, -1, :])


# === 1. VISUAL FACE PROCESSOR (UNCHANGED) ===
def get_center_frame_frames(video_path, num_frames=16):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception(f"Could not open video file: {video_path}")
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Avoid errors for short videos
    num_frames = min(num_frames, total_frames)
    
    selected_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
    frames = []
    
    for idx in selected_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    return frames

def process_video_face(video_path, start_time=None):
    extracted_frames = get_center_frame_frames(video_path)
    frames_for_tensor = []
    b64_frames = []
    
    for frame_rgb in extracted_frames:
        gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        # Security: ensure at least 16 frames are collected, even if faces are missing in some
        if len(faces) == 0:
            if len(frames_for_tensor) == 0:
                h, w, _ = frame_rgb.shape
                face_crop_rgb = frame_rgb[max(0, h//4):min(h, 3*h//4), max(0, w//4):min(w, 3*w//4)]
            else:
                face_crop_rgb = frames_for_tensor[-1]
        else:
            (x, y, w, h) = faces[0]
            # Center the crop and pad slightly for better model accuracy
            cw, ch = x + w//2, y + h//2
            size = max(w, h)
            x_pad, y_pad = int(size*1.1)//2, int(size*1.1)//2
            face_crop_rgb = frame_rgb[max(0, ch-y_pad):min(frame_rgb.shape[0], ch+y_pad), max(0, cw-x_pad):min(frame_rgb.shape[1], cw+x_pad)]
        
        if face_crop_rgb.size == 0:
            continue
            
        transformed_frame = transform(face_crop_rgb)
        frames_for_tensor.append(transformed_frame)
        
        # Prepare face crop for XAI base64 display
        if len(faces) > 0:
            pil_img = Image.fromarray(face_crop_rgb)
            buff = io.BytesIO()
            pil_img.save(buff, format="JPEG")
            b64_str = base64.b64encode(buff.getvalue()).decode('utf-8')
            b64_frames.append(b64_str)

    if not frames_for_tensor:
        raise Exception("No frames processed successfully")
        
    # Stack tensors (ensure precisely 16 frames)
    final_frames = frames_for_tensor[:16]
    while len(final_frames) < 16:
        final_frames.append(frames_for_tensor[-1] if frames_for_tensor else torch.zeros(3, 224, 224))
        
    video_tensor = torch.stack(final_frames).unsqueeze(0).to(device)
    
    # Pad base64 frames similarly for XAI loop
    while len(b64_frames) < len(final_frames):
        if b64_frames: b64_frames.append(b64_frames[-1])
        else: break

    return video_tensor, b64_frames


# === 2. SPATIAL ELA SCANNER (NEW - Mathematical Algorithm) ===
# This function takes a raw frame, compresses it, compares it, enhances the difference, and calculates error
def process_ela_scan_frame(frame, quality=90):
    # 1. Convert to RGB for consistency (OpenCV reads in BGR)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # 2. INTENTIONAL COMPRESSION: Save at known quality in memory
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, encimg = cv2.imencode('.jpg', frame, encode_param)
    compressed_frame = cv2.imdecode(encimg, 1)
    
    # 3. COMPARE: Subtract compressed version from original (matrix difference)
    # Using absolute difference so negative numbers don't wrap around
    diff = cv2.absdiff(frame, compressed_frame)
    
    # 4. ENHANCE: Scale the mathematical difference so we can visually observe it (0-255)
    # This glowing effect is what we return for XAI
    max_diff = np.amax(diff)
    if max_diff == 0: max_diff = 1 # Prevent dividing by zero
    scale = 255.0 / max_diff
    ela_image = cv2.convertScaleAbs(diff, alpha=scale)
    
    # 5. Calculate Average Error: Average brightness of the ELA difference image
    # Higher average brightness = potentially greater manipulation artifacts
    average_error = np.mean(ela_image)
    
    return ela_image, average_error

# Extracts specific frames and runs the above ELA function, returning average error and ELA images for XAI dropdown
def process_video_ela_scan(video_path, num_frames=10):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception(f"Could not open video file: {video_path}")
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    num_frames = min(num_frames, total_frames)
    selected_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
    
    ela_error_scores = []
    b64_ela_frames = []
    
    for idx in selected_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret: break
        
        # FIX: Do not crop! Keep the whole scene (background + face).
        # We just shrink the whole image to 640x360 so the math runs lightning fast.
        full_frame_resized = cv2.resize(frame, (640, 360))

        # Feed the FULL frame to the ELA algorithm
        ela_image, error = process_ela_scan_frame(full_frame_resized)
        ela_error_scores.append(error)
        
        pil_img = Image.fromarray(ela_image)
        buff = io.BytesIO()
        pil_img.save(buff, format="JPEG")
        b64_str = base64.b64encode(buff.getvalue()).decode('utf-8')
        b64_ela_frames.append(b64_str)
        
    cap.release()
    
    if not ela_error_scores:
        raise Exception("No frames processed successfully for ELA scan")
        
    average_error_score = sum(ela_error_scores) / len(ela_error_scores)
    
    return average_error_score, b64_ela_frames