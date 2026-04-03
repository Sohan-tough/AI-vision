// Global state
let currentImage = null;
let selectionBox = null;
let isSelecting = false;
let startPoint = { x: 0, y: 0 };
let currentPoint = { x: 0, y: 0 };

// DOM elements
const repoUrlInput = document.getElementById('repoUrl');
const cloneBtn = document.getElementById('cloneBtn');
const clearBtn = document.getElementById('clearBtn');
const repoStatus = document.getElementById('repoStatus');
const confThreshold = document.getElementById('confThreshold');
const confValue = document.getElementById('confValue');
const imageUpload = document.getElementById('imageUpload');
const imageContainer = document.getElementById('imageContainer');
const displayImage = document.getElementById('displayImage');
const selectionCanvas = document.getElementById('selectionCanvas');
const coordinates = document.getElementById('coordinates');
const resetSelection = document.getElementById('resetSelection');
const processBtn = document.getElementById('processBtn');
const loadingSpinner = document.getElementById('loadingSpinner');
const ocrResults = document.getElementById('ocrResults');
const matchResults = document.getElementById('matchResults');
const explanation = document.getElementById('explanation');
const indexStatus = document.getElementById('indexStatus');

// Utility functions
function showMessage(element, message, type = 'info') {
    element.innerHTML = message;
    element.className = `status-message ${type}`;
    element.style.display = 'block';
}

function hideMessage(element) {
    element.style.display = 'none';
}

function getEventPos(e, element) {
    const rect = element.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    
    return {
        x: clientX - rect.left,
        y: clientY - rect.top
    };
}

function updateSelectionDisplay() {
    if (!selectionBox) return;
    
    const canvas = selectionCanvas;
    const ctx = canvas.getContext('2d');
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw selection box
    ctx.strokeStyle = '#ff0000';
    ctx.lineWidth = 2;
    ctx.fillStyle = 'rgba(255, 0, 0, 0.1)';
    
    ctx.fillRect(selectionBox.x, selectionBox.y, selectionBox.width, selectionBox.height);
    ctx.strokeRect(selectionBox.x, selectionBox.y, selectionBox.width, selectionBox.height);
    
    // Update coordinates display
    const imageRect = displayImage.getBoundingClientRect();
    const scaleX = displayImage.naturalWidth / displayImage.clientWidth;
    const scaleY = displayImage.naturalHeight / displayImage.clientHeight;
    
    const actualBox = {
        x: Math.round(selectionBox.x * scaleX),
        y: Math.round(selectionBox.y * scaleY),
        width: Math.round(selectionBox.width * scaleX),
        height: Math.round(selectionBox.height * scaleY)
    };
    
    coordinates.textContent = `x=${actualBox.x}, y=${actualBox.y}, w=${actualBox.width}, h=${actualBox.height}`;
}

function setupImageSelection() {
    const wrapper = displayImage.parentElement;
    
    // Setup canvas
    selectionCanvas.width = displayImage.clientWidth;
    selectionCanvas.height = displayImage.clientHeight;
    
    // Mouse events
    wrapper.addEventListener('mousedown', handleSelectionStart);
    wrapper.addEventListener('mousemove', handleSelectionMove);
    wrapper.addEventListener('mouseup', handleSelectionEnd);
    
    // Touch events for mobile
    wrapper.addEventListener('touchstart', handleSelectionStart, { passive: false });
    wrapper.addEventListener('touchmove', handleSelectionMove, { passive: false });
    wrapper.addEventListener('touchend', handleSelectionEnd, { passive: false });
    
    // Prevent context menu
    wrapper.addEventListener('contextmenu', (e) => e.preventDefault());
}

function handleSelectionStart(e) {
    e.preventDefault();
    
    const pos = getEventPos(e, displayImage);
    startPoint = pos;
    currentPoint = pos;
    isSelecting = true;
    
    selectionBox = {
        x: pos.x,
        y: pos.y,
        width: 0,
        height: 0
    };
    
    updateSelectionDisplay();
}

function handleSelectionMove(e) {
    if (!isSelecting) return;
    e.preventDefault();
    
    const pos = getEventPos(e, displayImage);
    currentPoint = pos;
    
    // Update selection box
    selectionBox = {
        x: Math.min(startPoint.x, pos.x),
        y: Math.min(startPoint.y, pos.y),
        width: Math.abs(pos.x - startPoint.x),
        height: Math.abs(pos.y - startPoint.y)
    };
    
    updateSelectionDisplay();
}

function handleSelectionEnd(e) {
    if (!isSelecting) return;
    e.preventDefault();
    
    isSelecting = false;
    
    // Ensure minimum selection size
    if (selectionBox.width < 10 || selectionBox.height < 10) {
        selectionBox = null;
        const ctx = selectionCanvas.getContext('2d');
        ctx.clearRect(0, 0, selectionCanvas.width, selectionCanvas.height);
        coordinates.textContent = 'Selection too small - try again';
        return;
    }
    
    updateSelectionDisplay();
    processBtn.style.display = 'block';
}

// Event listeners
confThreshold.addEventListener('input', (e) => {
    confValue.textContent = e.target.value;
});

imageUpload.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
        currentImage = e.target.result;
        displayImage.src = currentImage;
        displayImage.onload = () => {
            imageContainer.style.display = 'block';
            setupImageSelection();
            
            // Reset selection
            selectionBox = null;
            const ctx = selectionCanvas.getContext('2d');
            ctx.clearRect(0, 0, selectionCanvas.width, selectionCanvas.height);
            coordinates.textContent = 'No region selected';
            processBtn.style.display = 'none';
        };
    };
    reader.readAsDataURL(file);
});

resetSelection.addEventListener('click', () => {
    selectionBox = null;
    const ctx = selectionCanvas.getContext('2d');
    ctx.clearRect(0, 0, selectionCanvas.width, selectionCanvas.height);
    coordinates.textContent = 'No region selected';
    processBtn.style.display = 'none';
});

cloneBtn.addEventListener('click', async () => {
    const repoUrl = repoUrlInput.value.trim();
    if (!repoUrl) {
        showMessage(repoStatus, 'Please enter a repository URL', 'error');
        return;
    }
    
    cloneBtn.disabled = true;
    cloneBtn.textContent = 'Cloning...';
    hideMessage(repoStatus);
    
    try {
        const response = await fetch('/api/clone-repo', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ repo_url: repoUrl })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showMessage(repoStatus, data.message, 'success');
            updateStatus();
        } else {
            showMessage(repoStatus, data.error || 'Failed to clone repository', 'error');
        }
    } catch (error) {
        showMessage(repoStatus, `Error: ${error.message}`, 'error');
    } finally {
        cloneBtn.disabled = false;
        cloneBtn.textContent = 'Clone + Build Index';
    }
});

clearBtn.addEventListener('click', async () => {
    clearBtn.disabled = true;
    clearBtn.textContent = 'Clearing...';
    
    try {
        const response = await fetch('/api/clear-repo', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showMessage(repoStatus, data.message, 'success');
            updateStatus();
        } else {
            showMessage(repoStatus, data.error || 'Failed to clear cache', 'error');
        }
    } catch (error) {
        showMessage(repoStatus, `Error: ${error.message}`, 'error');
    } finally {
        clearBtn.disabled = false;
        clearBtn.textContent = 'Clear Cache';
    }
});

processBtn.addEventListener('click', async () => {
    if (!currentImage || !selectionBox) {
        alert('Please select an image and draw a selection box');
        return;
    }
    
    processBtn.disabled = true;
    processBtn.textContent = 'Processing...';
    loadingSpinner.style.display = 'block';
    ocrResults.style.display = 'none';
    matchResults.style.display = 'none';
    explanation.style.display = 'none';
    
    try {
        // Calculate actual coordinates
        const scaleX = displayImage.naturalWidth / displayImage.clientWidth;
        const scaleY = displayImage.naturalHeight / displayImage.clientHeight;
        
        const actualBox = {
            x: Math.round(selectionBox.x * scaleX),
            y: Math.round(selectionBox.y * scaleY),
            width: Math.round(selectionBox.width * scaleX),
            height: Math.round(selectionBox.height * scaleY)
        };
        
        const response = await fetch('/api/process-image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                image_data: currentImage,
                bbox: actualBox,
                conf_threshold: parseFloat(confThreshold.value)
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show OCR results
            document.getElementById('ocrMain').textContent = data.ocr_main || 'No text found';
            document.getElementById('ocrNearby').textContent = data.ocr_nearby.join(', ') || 'None';
            ocrResults.style.display = 'block';
            
            // Show matches
            if (data.matches && data.matches.length > 0) {
                displayMatches(data.matches);
                matchResults.style.display = 'block';
                
                // Show explanation
                if (data.explanation) {
                    document.getElementById('explanationText').innerHTML = data.explanation.replace(/\n/g, '<br>');
                    explanation.style.display = 'block';
                }
            }
            
            showMessage(repoStatus, data.message, data.matches.length > 0 ? 'success' : 'info');
        } else {
            showMessage(repoStatus, data.error || 'Failed to process image', 'error');
        }
    } catch (error) {
        showMessage(repoStatus, `Error: ${error.message}`, 'error');
    } finally {
        processBtn.disabled = false;
        processBtn.textContent = '🚀 Run OCR + Match';
        loadingSpinner.style.display = 'none';
    }
});

function displayMatches(matches) {
    const matchesList = document.getElementById('matchesList');
    matchesList.innerHTML = '';
    
    matches.forEach((match, index) => {
        const matchDiv = document.createElement('div');
        matchDiv.className = 'match-item';
        
        matchDiv.innerHTML = `
            <div class="match-header">
                Match ${index + 1}: ${match.component || 'Unknown'} (${match.score_pct || 0}% confidence)
            </div>
            <div class="match-details">
                <strong>File:</strong> ${match.file || 'N/A'}<br>
                <strong>Lines:</strong> ${match.line_start || '?'}-${match.line_end || '?'}<br>
                <strong>Tag:</strong> ${match.tag || 'N/A'}
            </div>
            <div class="match-code">${match.snippet || 'No code snippet available'}</div>
        `;
        
        matchesList.appendChild(matchDiv);
    });
}

async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        if (data.index_loaded) {
            indexStatus.textContent = `📊 Index: ${data.stats.total_chunks || 0} chunks loaded`;
        } else {
            indexStatus.textContent = '📊 Index: Not loaded';
        }
    } catch (error) {
        console.error('Failed to update status:', error);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    updateStatus();
    
    // Handle window resize
    window.addEventListener('resize', () => {
        if (displayImage.complete && displayImage.naturalWidth > 0) {
            selectionCanvas.width = displayImage.clientWidth;
            selectionCanvas.height = displayImage.clientHeight;
            updateSelectionDisplay();
        }
    });
});