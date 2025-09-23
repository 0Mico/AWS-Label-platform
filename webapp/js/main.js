let currentJobPosts = [];
let currentSelectedJob = null;
let labels = [
    { id: 'unlabeled', name: 'Unlabeled', color: '#666' }
];
let selectedLabel = null;
let selectedColor = '#ffd700';
let jobTokensLabels = {};
let currentTokens = [];
let deletionHistory = []; // Track deletions for undo functionality
let isSelecting = false;
let selectionStart = null;
let selectedTokens = new Set();

// API Configuration
const API_BASE_URL = `https://${CONFIG.API_ID}.execute-api.${CONFIG.AWS_REGION}.amazonaws.com/prod`
const API_ENDPOINTS = {
    fetchJobs: `${API_BASE_URL}/Job-Posts`,
    saveJobs: `${API_BASE_URL}/Job-Posts`
};

// Initialize the application
document.addEventListener('DOMContentLoaded', function () {
    setupEventListeners();
    loadJobPosts();
    renderLabelsList();
});

function setupEventListeners() {
    // Color picker
    document.querySelectorAll('.color-option').forEach(option => {
        option.addEventListener('click', function () {
            document.querySelector('.color-option.selected').classList.remove('selected');
            this.classList.add('selected');
            selectedColor = this.dataset.color;
        });
    });

    // Editor content event listeners
    const editorContent = document.getElementById('editor-content');
    editorContent.addEventListener('click', handleTokenClick);
    editorContent.addEventListener('contextmenu', handleTokenRightClick);
    editorContent.addEventListener('mousedown', handleMouseDown);
    editorContent.addEventListener('mousemove', handleMouseMove);
    editorContent.addEventListener('mouseup', handleMouseUp);
    
    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyDown);
}

function handleKeyDown(event) {
    if (!currentSelectedJob) return;
    
    // Delete selected tokens with Delete or Backspace
    if ((event.key === 'Delete' || event.key === 'Backspace') && selectedTokens.size > 0) {
        event.preventDefault();
        deleteSelectedTokens();
    }
    
    // Undo with Ctrl+Z
    if (event.ctrlKey && event.key === 'z') {
        event.preventDefault();
        undoLastDeletion();
    }
    
    // Select all with Ctrl+A
    if (event.ctrlKey && event.key === 'a') {
        event.preventDefault();
        selectAllTokens();
    }
    
    // Clear selection with Escape
    if (event.key === 'Escape') {
        clearSelection();
    }
}

function handleMouseDown(event) {
    const tokenElement = event.target.closest('span[data-token-id]');
    if (tokenElement) {
        isSelecting = true;
        selectionStart = parseInt(tokenElement.dataset.tokenId);
        
        // If not holding Ctrl, clear previous selection
        if (!event.ctrlKey) {
            clearSelection();
        }
        
        // Add/remove token from selection
        toggleTokenSelection(selectionStart);
        event.preventDefault();
    }
}

function handleMouseMove(event) {
    if (isSelecting && selectionStart !== null) {
        const tokenElement = event.target.closest('span[data-token-id]');
        if (tokenElement) {
            const currentTokenId = parseInt(tokenElement.dataset.tokenId);
            selectTokenRange(selectionStart, currentTokenId);
        }
    }
}

function handleMouseUp(event) {
    isSelecting = false;
    selectionStart = null;
}

function handleTokenClick(event) {
    const tokenElement = event.target.closest('span[data-token-id]');
    if (tokenElement && selectedLabel) {
        // If tokens are selected, apply label to all selected tokens
        if (selectedTokens.size > 0) {
            applyLabelToSelectedTokens();
        } else {
            // Single token labeling
            const tokenId = parseInt(tokenElement.dataset.tokenId);
            const token = currentSelectedJob.tokens.find(t => t.id === tokenId);
            if (token) {
                if (selectedLabel.id === 'unlabeled') {
                    token.label = '';
                } else {
                    token.label = selectedLabel.name;
                }
                renderJobContent();
            }
        }
    }
}

function handleTokenRightClick(event) {
    event.preventDefault();
    const tokenElement = event.target.closest('span[data-token-id]');
    if (tokenElement) {
        const tokenId = parseInt(tokenElement.dataset.tokenId);
        
        // If token is not selected, select only this token
        if (!selectedTokens.has(tokenId)) {
            clearSelection();
            toggleTokenSelection(tokenId);
        }
        
        // Show context menu or delete immediately
        if (confirm(`Delete ${selectedTokens.size} token(s)?`)) {
            deleteSelectedTokens();
        }
    }
}

function toggleTokenSelection(tokenId) {
    if (selectedTokens.has(tokenId)) {
        selectedTokens.delete(tokenId);
    } else {
        selectedTokens.add(tokenId);
    }
    updateTokenVisualSelection();
}

function selectTokenRange(startId, endId) {
    const start = Math.min(startId, endId);
    const end = Math.max(startId, endId);
    
    // Clear previous selection
    selectedTokens.clear();
    
    // Select range
    for (let i = start; i <= end; i++) {
        const token = currentSelectedJob.tokens.find(t => t.id === i);
        if (token) {
            selectedTokens.add(i);
        }
    }
    
    updateTokenVisualSelection();
}

function selectAllTokens() {
    selectedTokens.clear();
    currentSelectedJob.tokens.forEach(token => {
        selectedTokens.add(token.id);
    });
    updateTokenVisualSelection();
    updateStatus(`Selected ${selectedTokens.size} tokens`);
}

function clearSelection() {
    selectedTokens.clear();
    updateTokenVisualSelection();
}

function updateTokenVisualSelection() {
    // Update visual selection state
    document.querySelectorAll('span[data-token-id]').forEach(span => {
        const tokenId = parseInt(span.dataset.tokenId);
        if (selectedTokens.has(tokenId)) {
            span.classList.add('selected-token');
        } else {
            span.classList.remove('selected-token');
        }
    });
    
    // Update status
    if (selectedTokens.size > 0) {
        updateStatus(`${selectedTokens.size} token(s) selected`);
    } else {
        updateStatus('Ready');
    }
}

function applyLabelToSelectedTokens() {
    if (!selectedLabel || selectedTokens.size === 0) return;
    
    selectedTokens.forEach(tokenId => {
        const token = currentSelectedJob.tokens.find(t => t.id === tokenId);
        if (token) {
            if (selectedLabel.id === 'unlabeled') {
                token.label = '';
            } else {
                token.label = selectedLabel.name;
            }
        }
    });
    
    clearSelection();
    renderJobContent();
    updateStatus(`Applied "${selectedLabel.name}" label to ${selectedTokens.size} tokens`);
}

function deleteSelectedTokens() {
    if (selectedTokens.size === 0) return;
    
    // Store deletion for undo
    const deletedTokens = currentSelectedJob.tokens.filter(token => selectedTokens.has(token.id));
    deletionHistory.push({
        tokens: deletedTokens,
        timestamp: Date.now()
    });
    
    // Remove tokens from the job
    currentSelectedJob.tokens = currentSelectedJob.tokens.filter(token => !selectedTokens.has(token.id));
    
    // Re-assign sequential IDs to remaining tokens
    currentSelectedJob.tokens.forEach((token, index) => {
        token.id = index;
        token.position = index;
    });
    
    const deletedCount = selectedTokens.size;
    clearSelection();
    renderJobContent();
    updateStatus(`Deleted ${deletedCount} token(s). Press Ctrl+Z to undo.`);
}

function undoLastDeletion() {
    if (deletionHistory.length === 0) {
        updateStatus('Nothing to undo');
        return;
    }
    
    const lastDeletion = deletionHistory.pop();
    
    lastDeletion.tokens.forEach(token => {
        currentSelectedJob.tokens.push(token);
    });
    
    // Re-sort tokens by original position if available
    currentSelectedJob.tokens.sort((a, b) => (a.position || a.id) - (b.position || b.id));
    
    // Re-assign sequential IDs
    currentSelectedJob.tokens.forEach((token, index) => {
        token.id = index;
        token.position = index;
    });
    
    renderJobContent();
    updateStatus(`Restored ${lastDeletion.tokens.length} token(s)`);
}

// Load job posts from API
async function loadJobPosts() {
    try {
        updateStatus('Loading job posts...');

        const response = await fetch(API_ENDPOINTS.fetchJobs);
        const data = await response.json();

        const newJobs = data.jobs.map(job => ({
            id: job.Job_ID,
            title: job.Title,
            company: job.Company,
            tokens: job.Tokens
        }))

        const existingJobIds = currentJobPosts.map(job => job.id);
        const newJobsToAdd = newJobs.filter(job => !existingJobIds.includes(job.id));

        currentJobPosts.push(...newJobsToAdd);
        renderJobList();
        updateStatus('Ready');
    } catch (error) {
        console.error('Failed to load job posts:', error);
        updateStatus('Error loading job posts');
    }
}

function clearAllJobPosts() {
    currentJobPosts = [];
    currentSelectedJob = null;
    deletionHistory = [];
    clearSelection();
    renderJobList();
            
    // Clear the editor content
    const editorTitle = document.getElementById('editor-title');
    const editorContent = document.getElementById('editor-content');
    editorTitle.textContent = 'Select a job post to start labeling';
    editorContent.innerHTML = `
        <div class="no-selection">
            <p>Select a job post from the left panel to begin labeling.</p>
        </div>
        `;
            
    updateStatus('All job posts cleared');
}

function renderJobList() {
    const jobList = document.getElementById('job-list');

    if (currentJobPosts.length === 0) {
        jobList.innerHTML = '<div class="loading">No job posts available</div>';
        return;
    }

    jobList.innerHTML = currentJobPosts.map(job => `
                <div class="job-item" onclick="selectJob('${job.id}')">
                    <div class="job-title">${job.title}</div>
                    <div class="job-company">${job.company}</div>
                    <div class="job-stats">${job.tokens.length} tokens</div>
                </div>
            `).join('');
}

function selectJob(jobId) {
    // Update active state
    document.querySelectorAll('.job-item').forEach(item => {
        item.classList.remove('active');
    });
    event.currentTarget.classList.add('active');

    // Find and display the job
    currentSelectedJob = currentJobPosts.find(job => job.id === jobId);
    if (currentSelectedJob) {
        deletionHistory = [];
        clearSelection();
        renderJobContent();
    }
}

function renderJobContent() {
    const editorTitle = document.getElementById('editor-title');
    const editorContent = document.getElementById('editor-content');

    editorTitle.textContent = `${currentSelectedJob.title} - ${currentSelectedJob.company} (${currentSelectedJob.tokens.length} tokens)`;

    const tokenSpans = currentSelectedJob.tokens.map(token => {
        const label = labels.find(l => l.name === token.label);
        const color = label ? label.color : '';
        const tokenClass = label ? 'highlighted-token' : 'token';
        return `<span class="${tokenClass}" style="background-color: ${color}" data-token-id="${token.id}">${token.text}</span>`;
    }).join(' ');

    editorContent.innerHTML = `
        <div class="job-content">
            <div class="job-header">
                <h2>${currentSelectedJob.title}</h2>
                <div class="job-meta">${currentSelectedJob.company} • ${currentSelectedJob.tokens.length} tokens</div>
            </div>
            <div class="editing-instructions">
                <p><strong>Instructions:</strong> Click tokens to label  •  Right-click or select + Delete to remove  •  Ctrl+A to select all  •  Ctrl+Z to undo  •  Esc to clear selection</p>
            </div>
            <div class="job-description" id="job-description">
                ${tokenSpans}
            </div>
        </div>
    `;
}

function createLabel() {
    const labelNameInput = document.getElementById('label-name-input');
    const labelName = labelNameInput.value.trim();

    if (!labelName) {
        alert('Please enter a label name');
        return;
    }

    if (labels.find(l => l.name === labelName)) {
        alert('Label already exists');
        return;
    }

    const newLabel = {
        id: Date.now().toString(),
        name: labelName,
        color: selectedColor
    };

    labels.push(newLabel);
    renderLabelsList();
    labelNameInput.value = '';
}

function renderLabelsList() {
    const labelsList = document.getElementById('labels-list');

    if (labels.length === 0) {
        labelsList.innerHTML = '<div style="color: #969696; font-size: 12px; text-align: center;">No labels created yet</div>';
        return;
    }

    labelsList.innerHTML = labels.map(label => `
                <div class="label-item ${selectedLabel?.id === label.id ? 'selected' : ''}" onclick="selectLabel('${label.id}')">
                    <div class="label-name">
                        <div class="label-color" style="background-color: ${label.color}"></div>
                        ${label.name}
                    </div>
                    <div class="label-actions">
                        ${label.name !== 'Unlabeled' ? `<button class="btn-small" onclick="deleteLabel('${label.id}'); event.stopPropagation();">×</button>` : ''}
                    </div>
                </div>
            `).join('');
}

function selectLabel(labelId) {
    selectedLabel = labels.find(l => l.id === labelId);
    renderLabelsList();
    updateStatus(`Selected label: ${selectedLabel.name}`);
}

function deleteLabel(labelId) {
    const labelToDelete = labels.find(l => l.id === labelId);
    if (labelToDelete && labelToDelete.isDeletable === false) {
        return;
    }
    if (confirm('Are you sure you want to delete this label?')) {
        labels = labels.filter(l => l.id !== labelId);
        if (selectedLabel?.id === labelId) {
            selectedLabel = null;
        }
        renderLabelsList();
        updateStatus('Label deleted');
    }
}

function clearLabels() {
    if (!currentSelectedJob) return;

    currentSelectedJob.tokens.forEach(token => token.label = '');
    renderJobContent();
    updateStatus('Labels cleared');
}

async function saveLabels() {
    if (!currentSelectedJob) {
        alert('No job selected to save');
        return;
    }

    try {
        updateStatus('Saving labels...');

        const payload = {
            jobId: currentSelectedJob.id,
            tokens: currentSelectedJob.tokens,
            totalTokens: currentSelectedJob.tokens.length,
        };

        const response = await fetch(API_ENDPOINTS.saveJobs, {
        method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        // Delete job from the left column list
        currentJobPosts = currentJobPosts.filter(job => job.id !== currentSelectedJob.id);
        renderJobList();

        // Clear the editor
        currentSelectedJob = null;
        const editorTitle = document.getElementById('editor-title');
        const editorContent = document.getElementById('editor-content');
        editorTitle.textContent = 'Select a job post to start labeling';
        editorContent.innerHTML = `
        <div class="no-selection">
            <p>Select a job post from the left panel to begin labeling.</p>
        </div>
        `;

        console.log('Would save:', payload);
        updateStatus('Labels saved successfully');          
    } catch (error) {
        console.error('Failed to save labels:', error);
        updateStatus('Error saving labels');
    }
}

function updateStatus(message) {
    document.getElementById('status-text').textContent = message;
}