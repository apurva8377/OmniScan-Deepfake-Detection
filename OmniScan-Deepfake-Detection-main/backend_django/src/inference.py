import torch
import os
from model import DeepfakeSequenceModel 
from torchvision import transforms
from PIL import Image

# 1. Force CPU usage since this laptop has no GPU
device = torch.device("cpu")
print(f"Running on: {device}")

# 2. Initialize the architecture and load the 'brain'
model = DeepfakeSequenceModel().to(device)
model.load_state_dict(torch.load("saved_models/prototype_model.pth", map_location=device))
model.eval() 

# 3. Standard Preprocessing
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

def predict_local_folder(folder_name):
    folder_path = os.path.join("data", "extracted_faces", folder_name)
    
    if not os.path.exists(folder_path):
        print(f"Error: Folder {folder_path} not found!")
        return

    frames = []
    # Get the first 20 faces extracted by your preprocess.py script
    frame_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.jpg')])[:20]
    
    for f_name in frame_files:
        img_path = os.path.join(folder_path, f_name)
        img = Image.open(img_path).convert('RGB')
        frames.append(transform(img))
    
    # Create a batch of 1 video
    input_tensor = torch.stack(frames).unsqueeze(0).to(device)
    
    with torch.no_grad():
        output = model(input_tensor)
        prob = output.item()
    
    result = "DEEPFAKE" if prob > 0.5 else "REAL"
    print(f"\n--- Result for {folder_name} ---")
    print(f"Prediction: {result}")
    print(f"Confidence: {prob:.4f}")

if __name__ == "__main__":
    # Get the name of the first folder in your extracted_faces directory
    extracted_dir = os.path.join("data", "extracted_faces")
    available_folders = [f for f in os.listdir(extracted_dir) if os.path.isdir(os.path.join(extracted_dir, f))]
    
    if available_folders:
        predict_local_folder(available_folders[0])
    else:
        print("No processed videos found in data/extracted_faces/")