document.getElementById('webDashBtn').addEventListener('click', () => {
    chrome.tabs.create({ url: "http://127.0.0.1:8000/" });
});

// ==========================================
// MEMORY CHECK FOR CHECKPOINT
// ==========================================
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0] && !tabs[0].url.startsWith("chrome://")) {
        chrome.scripting.executeScript({
            target: { tabId: tabs[0].id },
            func: () => window.dfShieldCheckpoint !== undefined
        }, (results) => {
            if (results && results[0] && results[0].result) {
                document.getElementById('checkpoint-btn').style.display = 'block';
            }
        });
    }
});

// RESTORE CHECKPOINT ON CLICK
document.getElementById('checkpoint-btn').addEventListener('click', async () => {
    let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
            const v = document.querySelector('video');
            if (v && window.dfShieldCheckpoint !== undefined) {
                v.currentTime = window.dfShieldCheckpoint;
                return true;
            }
            return false;
        }
    }, (results) => {
        if (results && results[0] && results[0].result) {
            const btn = document.getElementById('checkpoint-btn');
            btn.innerHTML = "<i class='fa-solid fa-check'></i> Checkpoint Loaded";
            btn.style.color = "#2ea043"; btn.style.borderColor = "#2ea043";
            setTimeout(() => {
                btn.innerHTML = "<i class='fa-solid fa-location-crosshairs'></i> Load Last Checkpoint";
                btn.style.color = "#58a6ff"; btn.style.borderColor = "#58a6ff";
            }, 1500);
        }
    });
});

// ==========================================
// DYNAMIC BUTTON STATE MACHINE
// ==========================================
const checkboxes = document.querySelectorAll('.model-toggle');
const scanBtn = document.getElementById('scanBtn');
let activeMode = 'none'; 

function updateButtonState() {
    const selected = Array.from(checkboxes).filter(box => box.checked).map(box => box.value).sort(); 
    const combo = selected.join('_'); 

    scanBtn.disabled = false; scanBtn.style.color = "#ffffff"; 
    scanBtn.style.backgroundSize = "100% 100%"; scanBtn.style.animation = "none"; scanBtn.style.boxShadow = "none";

    switch (combo) {
        case 'face': activeMode = 'face'; scanBtn.innerHTML = "<i class='fa-solid fa-play'></i> Run Biometric Scan"; scanBtn.style.background = "#6b48ff"; break;
        case 'frame': activeMode = 'frame'; scanBtn.innerHTML = "<i class='fa-solid fa-play'></i> Run Spatial Scan"; scanBtn.style.background = "#ff8c00"; break;
        case 'audio': activeMode = 'audio'; scanBtn.innerHTML = "<i class='fa-solid fa-play'></i> Run Audio Scan"; scanBtn.style.background = "#00b4d8"; break;
        case 'audio_face': activeMode = 'fusion_audio_face'; scanBtn.innerHTML = "<i class='fa-solid fa-bolt'></i> Bio + Audio Fusion"; scanBtn.style.background = "linear-gradient(90deg, #6b48ff, #00b4d8, #6b48ff)"; scanBtn.style.backgroundSize = "200% 200%"; scanBtn.style.animation = "gradient-mix 3s ease infinite"; break;
        case 'face_frame': activeMode = 'fusion_face_frame'; scanBtn.innerHTML = "<i class='fa-solid fa-bolt'></i> Bio + Spatial Fusion"; scanBtn.style.background = "linear-gradient(90deg, #6b48ff, #ff8c00, #6b48ff)"; scanBtn.style.backgroundSize = "200% 200%"; scanBtn.style.animation = "gradient-mix 3s ease infinite"; break;
        case 'audio_frame': activeMode = 'fusion_audio_frame'; scanBtn.innerHTML = "<i class='fa-solid fa-bolt'></i> Spatial + Audio Fusion"; scanBtn.style.background = "linear-gradient(90deg, #ff8c00, #00b4d8, #ff8c00)"; scanBtn.style.backgroundSize = "200% 200%"; scanBtn.style.animation = "gradient-mix 3s ease infinite"; break;
        case 'audio_face_frame': activeMode = 'fusion_all'; scanBtn.innerHTML = "<i class='fa-solid fa-globe'></i> OMNI-SCAN ENGINE"; scanBtn.style.background = "linear-gradient(90deg, #f85149, #6b48ff, #58a6ff, #f85149)"; scanBtn.style.backgroundSize = "300% 300%"; scanBtn.style.animation = "gradient-mix 2.5s ease infinite"; scanBtn.style.boxShadow = "0px 0px 10px rgba(248, 81, 73, 0.4)"; break;
        default: activeMode = 'none'; scanBtn.innerHTML = "<i class='fa-solid fa-lock'></i> Select configuration"; scanBtn.style.background = "#21262d"; scanBtn.disabled = true; scanBtn.style.color = "#8b949e"; break;
    }

    scanBtn.classList.remove('btn-animate');
    setTimeout(() => { scanBtn.classList.add('btn-animate'); }, 10);
}
checkboxes.forEach(box => box.addEventListener('change', updateButtonState));
updateButtonState();

// ==========================================
// INJECTION & RECORDING LOGIC
// ==========================================
scanBtn.addEventListener('click', async () => {
    const statusText = document.getElementById('statusText');
    const loader = document.getElementById('loader');
    const framesContainer = document.getElementById('frames-container');
    const graphContainer = document.getElementById('graph-container');

    scanBtn.style.display = 'none';
    loader.style.display = 'block';
    statusText.innerHTML = "<i class='fa-solid fa-circle-notch fa-spin'></i> Injecting scanner...";
    statusText.style.color = "#58a6ff";
    if(framesContainer) framesContainer.style.display = 'none';
    if(graphContainer) graphContainer.style.display = 'none';

    try {
        let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab.url.startsWith("chrome://") || tab.url.startsWith("edge://")) throw new Error("Cannot scan protected pages.");

        await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: grabAndAnalyzeVideo,
            args: [activeMode] 
        });
        
    } catch (error) {
        statusText.innerHTML = "<i class='fa-solid fa-triangle-exclamation'></i> Cannot scan this page. Try YouTube.";
        statusText.style.color = "#f85149";
        scanBtn.style.display = 'block'; loader.style.display = 'none';
        scanBtn.innerHTML = "<i class='fa-solid fa-rotate-right'></i> Try Again";
    }
});

async function grabAndAnalyzeVideo(passedMode) {
    chrome.runtime.sendMessage({ action: "updateStatus", msg: "<i class='fa-solid fa-satellite-dish fa-fade'></i> Hunting for video stream...", type: "info" });
    
    const video = await new Promise((resolve) => {
        let attempts = 0;
        const checkInterval = setInterval(() => {
            const v = document.querySelector('video');
            if (v) { clearInterval(checkInterval); resolve(v); } 
            else if (++attempts >= 20) { clearInterval(checkInterval); resolve(null); }
        }, 500);
    });

    if (!video) return chrome.runtime.sendMessage({ action: "updateStatus", msg: "<i class='fa-solid fa-video-slash'></i> No video detected.", type: "error" });

    window.dfShieldCheckpoint = video.currentTime;

    let displayModeName = passedMode.replace('fusion_', '').replace('_', ' + ').toUpperCase();
    if (passedMode === 'fusion_all') displayModeName = "OMNI-SCAN";
    
    chrome.runtime.sendMessage({ action: "updateStatus", msg: `<i class='fa-solid fa-record-vinyl fa-spin'></i> Recording 5s for ${displayModeName}...`, type: "info" });

    try {
        const stream = video.captureStream();
        let options = { mimeType: 'video/webm' };
        if (MediaRecorder.isTypeSupported('video/webm;codecs=h264')) {
            options = { mimeType: 'video/webm;codecs=h264' };
        }
        
        const recorder = new MediaRecorder(stream, options);
        const chunks = [];

        recorder.ondataavailable = (e) => chunks.push(e.data);
        
        recorder.onstop = async () => {
            chrome.runtime.sendMessage({ action: "updateStatus", msg: "<i class='fa-solid fa-server'></i> Transmitting to AI Brain...", type: "info" });
            const formData = new FormData();
            
            const blob = new Blob(chunks, { type: 'video/mp4' });
            formData.append('video', blob, 'capture.mp4');
            formData.append('mode', passedMode); 

            try {
                const response = await fetch('http://127.0.0.1:8000/api/analyze/', { method: 'POST', body: formData });
                const data = await response.json();
                
                if (data.error) chrome.runtime.sendMessage({ action: "updateStatus", msg: `<i class='fa-solid fa-triangle-exclamation'></i> Server Error: ${data.error}`, type: "error" });
                else chrome.runtime.sendMessage({ action: "updateStatus", msg: data.status === "Fake" ? `<i class='fa-solid fa-triangle-exclamation'></i> SYNTHETIC (${data.confidence}%)` : `<i class='fa-solid fa-shield-check'></i> AUTHENTIC (${data.confidence}%)`, type: data.status.toLowerCase(), frames: data.frames, breakdown: data.breakdown });
            } catch (err) {
                chrome.runtime.sendMessage({ action: "updateStatus", msg: "<i class='fa-solid fa-link-slash'></i> Cannot reach API.", type: "error" });
            }
        };

        if (video.paused) video.play();
        recorder.start();
        setTimeout(() => { recorder.stop(); video.pause(); }, 5000); 

    } catch (e) {
        chrome.runtime.sendMessage({ action: "updateStatus", msg: "<i class='fa-solid fa-lock'></i> DRM protected video.", type: "error" });
    }
}

// ==========================================
// EXPLAINABLE AI UI LISTENER (EXTENSION VERSION)
// ==========================================
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "updateStatus") {
        const statusText = document.getElementById('statusText');
        const scanBtn = document.getElementById('scanBtn');
        const loader = document.getElementById('loader');
        const framesContainer = document.getElementById('frames-container');
        const framesGrid = document.getElementById('frames-grid');
        const graphContainer = document.getElementById('graph-container'); // Restored!

        statusText.innerHTML = request.msg;
        
        if (request.type === "fake" || request.type === "real") {
            statusText.className = request.type === "fake" ? "result-fake" : "result-real";
            scanBtn.style.display = 'block'; loader.style.display = 'none';
            
            scanBtn.style.animation = "none";
            scanBtn.innerHTML = "<i class='fa-solid fa-rotate-right'></i> Scan Again";
            
            document.getElementById('checkpoint-btn').style.display = 'block';

            // ==========================================
            // 1. RENDER GRAPHS (RESTORED!)
            // ==========================================
            if (graphContainer) {
                graphContainer.innerHTML = ''; 
                if (request.breakdown) {
                    graphContainer.style.display = 'flex';
                    for (const [modelName, scores] of Object.entries(request.breakdown)) {
                        const isFake = scores.fake > scores.real;
                        const dominantScore = isFake ? scores.fake : scores.real;
                        const percentage = (dominantScore * 100).toFixed(1);
                        
                        // Create a safe ID for the animation
                        const safeId = "ext-bar-" + modelName.replace(/\s+/g, '-');
                        
                        const graphHTML = `
                            <div class="graph-column">
                                <div class="graph-title">${modelName}</div>
                                <div class="graph-box">
                                    <div class="zero-line"></div>
                                    <div id="${safeId}" class="${isFake ? 'bar-fake' : 'bar-real'}" style="height: 0%;"></div>
                                </div>
                                <div class="graph-percentage" style="color: ${isFake ? '#f85149' : '#2ea043'}">
                                    ${percentage}%
                                </div>
                            </div>
                        `;
                        graphContainer.innerHTML += graphHTML;

                        
                        setTimeout(() => {
                            const bar = document.getElementById(safeId);
                            if (bar) bar.style.height = (dominantScore * 50) + '%';
                        }, 50);
                    }
                } else {
                    graphContainer.style.display = 'none';
                }
            }

            
            if (framesGrid) {
                framesGrid.innerHTML = '';
                if (request.breakdown && request.frames && request.frames.length > 0) {
                    framesContainer.style.display = 'block';
                    let frameIndex = 0;

                    for (const [modelName, scores] of Object.entries(request.breakdown)) {
                        const isFake = scores.fake > scores.real;
                        const statusColor = isFake ? '#f85149' : '#2ea043';
                        const statusText = isFake ? 'ANOMALY DETECTED' : 'CLEARED';
                        
                        let icon = 'fa-microchip';
                        if (modelName.includes('Biometric')) icon = 'fa-users-viewfinder';
                        else if (modelName.includes('Spatial')) icon = 'fa-object-group';
                        else if (modelName.includes('Audio')) icon = 'fa-wave-square';

                        const frameData = request.frames[frameIndex] || request.frames[request.frames.length - 1];
                        if (frameIndex < request.frames.length - 1) frameIndex++;

                        let visualOverlay = ''; let imgFilter = '';
                        
                        if (modelName.includes('Biometric')) {
                            visualOverlay = `<div class="target-box" style="border-color: ${statusColor}; box-shadow: 0 0 5px ${statusColor} inset;"></div>`;
                        } else if (modelName.includes('Spatial')) {
                            imgFilter = 'filter: contrast(150%) saturate(200%) hue-rotate(90deg);'; 
                            visualOverlay = `<div class="ela-scan-line" style="background: ${statusColor}; box-shadow: 0 0 10px ${statusColor};"></div>`;
                        } else if (modelName.includes('Audio')) {
                            imgFilter = 'filter: grayscale(100%) opacity(0.4);';
                            visualOverlay = `<div class="audio-waves" style="color: ${statusColor};"><div class="bar"></div><div class="bar"></div><div class="bar"></div></div>`;
                        }

                        const cardHTML = `
                            <div class="xai-card" style="border-top: 2px solid ${statusColor};">
                                <div class="xai-header"><i class="fa-solid ${icon}"></i> ${modelName}</div>
                                <div class="xai-image-wrapper">
                                    <img src="data:image/jpeg;base64,${frameData}" style="${imgFilter}">
                                    ${visualOverlay}
                                </div>
                                <div class="xai-footer" style="color: ${statusColor};">
                                    ${statusText} (${(Math.max(scores.fake, scores.real)*100).toFixed(1)}%)
                                </div>
                            </div>
                        `;
                        framesGrid.innerHTML += cardHTML;
                    }
                } else { framesContainer.style.display = 'none'; }
            }
        } else if (request.type === "error") {
            statusText.style.color = "#f85149"; scanBtn.style.display = 'block'; loader.style.display = 'none';
            scanBtn.style.animation = "none";
            scanBtn.innerHTML = "<i class='fa-solid fa-rotate-right'></i> Try Again";
            if(framesContainer) framesContainer.style.display = 'none'; 
            if(graphContainer) graphContainer.style.display = 'none';
        } else if (request.type === "info") {
            statusText.style.color = "#c9d1d9";
        }
    }
});