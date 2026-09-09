import os
import tempfile
import torch
import numpy as np
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .apps import DetectorConfig

from .ml_brain import process_video_face, process_video_ela_scan 
from .audio_brain import process_audio_scan 

@csrf_exempt
def analyze_video(request):
    if request.method == 'POST' and request.FILES.get('video'):
        video_file = request.FILES['video']
        
        scan_mode = request.POST.get('mode', 'face') 
        start_time = float(request.POST.get('start_time', 0.0))
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_vid:
            for chunk in video_file.chunks():
                temp_vid.write(chunk)
            temp_vid_path = temp_vid.name

        try:
            b64_frames = []
            model_breakdown = {} # Dictionary to hold individual scores
            fake_probabilities = [] 

            run_face = 'face' in scan_mode or scan_mode == 'fusion_all'
            run_audio = 'audio' in scan_mode or scan_mode == 'fusion_all'
            run_frame = 'frame' in scan_mode or scan_mode == 'fusion_all'
            
            # 🧠 ENGINE A: Biometric Face Scan
            if run_face:
                video_tensor, face_b64 = process_video_face(temp_vid_path, start_time=start_time)
                with torch.no_grad():
                    logits = DetectorConfig.model(video_tensor)
                    probs = torch.nn.functional.softmax(logits, dim=1).squeeze()
                    face_fake_prob = probs[0].item()
                    
                    fake_probabilities.append(face_fake_prob)
                    model_breakdown['Biometric'] = {'fake': face_fake_prob, 'real': 1.0 - face_fake_prob}
                    b64_frames.extend(face_b64[:6]) 

            # 🎤 ENGINE B: Audio Vocal Scan
            if run_audio:
                audio_results, error = process_audio_scan(temp_vid_path)
                if error: raise Exception(error)
                
                fake_probabilities.append(audio_results['fake_prob'])
                model_breakdown['Audio'] = {'fake': audio_results['fake_prob'], 'real': audio_results['real_prob']}

            # 🖼️ ENGINE C: Spatial Background Scan
            if run_frame:
                average_error, spatial_b64 = process_video_ela_scan(temp_vid_path)
                threshold_avg_error = 15.0  
                max_observed_error = 30.0   

                if average_error > threshold_avg_error:
                    fake_prob = (average_error - threshold_avg_error) / (max_observed_error - threshold_avg_error) * 0.5 + 0.5
                    fake_prob = min(fake_prob, 0.999) 
                else:
                    fake_prob = average_error / threshold_avg_error * 0.5
                    fake_prob = max(fake_prob, 0.001)
                
                fake_probabilities.append(fake_prob)
                model_breakdown['Spatial'] = {'fake': fake_prob, 'real': 1.0 - fake_prob}
                b64_frames.extend(spatial_b64[:6]) 

            if not fake_probabilities:
                raise Exception("No valid scan mode selected.")

            # Average out all the probabilities dynamically
            final_fake_prob = sum(fake_probabilities) / len(fake_probabilities)
            final_real_prob = 1.0 - final_fake_prob

            if final_fake_prob > final_real_prob:
                status = 'Fake'
                confidence_score = round(final_fake_prob * 100, 2)
            else:
                status = 'Real'
                confidence_score = round(final_real_prob * 100, 2)

            os.remove(temp_vid_path)
            
            return JsonResponse({
                'status': status, 
                'confidence': confidence_score,
                'frames': b64_frames,
                'breakdown': model_breakdown 
            })

        except Exception as e:
            if os.path.exists(temp_vid_path):
                os.remove(temp_vid_path)
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'No video provided'}, status=400)