from django.apps import AppConfig
import torch
import os
from django.conf import settings

class DetectorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'detector'
    
    # Global variables to hold the brain
    model = None
    device = None

    def ready(self):
        from .ml_brain import DeepfakeSequenceModel
        
        print("🧠 Booting up the PyTorch Deepfake Engine...")
        
        # Attach directly to the class, not 'self'
        DetectorConfig.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(base_dir, 'saved_models', 'omniscan_biometric_v1.0.pt')
        
        DetectorConfig.model = DeepfakeSequenceModel().to(DetectorConfig.device)
        DetectorConfig.model.load_state_dict(torch.load(model_path, map_location=DetectorConfig.device))
        DetectorConfig.model.eval()
        print("✅ Engine Online. Waiting for Chrome Extension requests...")