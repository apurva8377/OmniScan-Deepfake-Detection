import torch
import torch.nn as nn
import torchvision.models as models

class DeepfakeSequenceModel(nn.Module):
    def __init__(self, num_classes=1, hidden_dim=256, lstm_layers=1, bidirectional=False):
        super(DeepfakeSequenceModel, self).__init__()
        
        # 1. CNN Feature Extractor 
        # Changed to weights=None so it doesn't try to download from the internet!
        resnet = models.resnet50(weights=None)
        self.feature_extractor = nn.Sequential(*list(resnet.children())[:-1])
        
        # 2. LSTM Sequence Analyzer
        self.lstm = nn.LSTM(
            input_size=2048,
            hidden_size=hidden_dim,
            num_layers=lstm_layers,
            batch_first=True,
            bidirectional=bidirectional
        )
        
        # 3. Final Classifier
        lstm_output_dim = hidden_dim * 2 if bidirectional else hidden_dim
        self.classifier = nn.Sequential(
            nn.Linear(lstm_output_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes),
            nn.Sigmoid()
        )

    def forward(self, x):
        batch_size, seq_length, c, h, w = x.size()
        x = x.view(batch_size * seq_length, c, h, w)
        features = self.feature_extractor(x)
        features = features.view(features.size(0), -1) 
        features = features.view(batch_size, seq_length, -1)
        lstm_out, _ = self.lstm(features)
        last_frame_output = lstm_out[:, -1, :]
        return self.classifier(last_frame_output)