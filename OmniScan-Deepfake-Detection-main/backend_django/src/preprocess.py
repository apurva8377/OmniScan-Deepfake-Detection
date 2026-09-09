import cv2
import mediapipe as mp
import os

# Initialize MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)

def process_video(video_path, output_folder, max_frames=20):
    """
    Extracts evenly spaced frames from a video, crops the face, and saves them.
    """
    os.makedirs(output_folder, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Check if video was read properly
    if total_frames == 0:
        print(f"Warning: Could not read frames from {video_path}")
        return

    interval = max(1, total_frames // max_frames)
    
    frame_count = 0
    saved_count = 0
    
    while cap.isOpened() and saved_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count % interval == 0:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_detection.process(rgb_frame)
            
            if results.detections:
                detection = results.detections[0]
                bboxC = detection.location_data.relative_bounding_box
                ih, iw, _ = frame.shape
                
                x = int(bboxC.xmin * iw)
                y = int(bboxC.ymin * ih)
                w = int(bboxC.width * iw)
                h = int(bboxC.height * ih)
                
                margin_x, margin_y = int(w * 0.2), int(h * 0.2)
                x1, y1 = max(0, x - margin_x), max(0, y - margin_y)
                x2, y2 = min(iw, x + w + margin_x), min(ih, y + h + margin_y)
                
                cropped_face = frame[y1:y2, x1:x2]
                
                if cropped_face.size > 0:
                    resized_face = cv2.resize(cropped_face, (224, 224)) 
                    filename = os.path.join(output_folder, f"frame_{saved_count:03d}.jpg")
                    cv2.imwrite(filename, resized_face)
                    saved_count += 1
                    
        frame_count += 1
        
    cap.release()
    print(f"Success: Saved {saved_count} faces to {output_folder}")

# --- Process All Videos in Folder ---
if __name__ == "__main__":
    raw_videos_dir = os.path.join("data", "raw_videos")
    extracted_faces_dir = os.path.join("data", "extracted_faces")
    
    if not os.path.exists(raw_videos_dir):
        print(f"Error: The folder {raw_videos_dir} does not exist.")
    else:
        video_files = [f for f in os.listdir(raw_videos_dir) if f.endswith(('.mp4', '.avi', '.mov'))]
        
        if not video_files:
            print(f"Error: No video files (.mp4, .avi, .mov) found inside {raw_videos_dir}")
        else:
            for video_filename in video_files:
                input_video_path = os.path.join(raw_videos_dir, video_filename)
                output_directory = os.path.join(extracted_faces_dir, video_filename.split('.')[0])
                
                print(f"\n--- Processing {video_filename} ---")
                process_video(input_video_path, output_directory, max_frames=20)
            
            print("\nAll videos processed successfully!")