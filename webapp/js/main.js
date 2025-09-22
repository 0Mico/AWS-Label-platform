let currentJobPosts = [];
let currentSelectedJob = null;
let labels = [
    { id: 'unlabeled', name: 'Unlabeled', color: '#666' }
];
let selectedLabel = null;
let selectedColor = '#ffd700';
let jobTokensLabels = {};
let currentTokens = [];

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

    // Text selection for labeling
    document.getElementById('editor-content').addEventListener('click', handleTokenClick);
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
        renderJobContent();
    }
}

function renderJobContent() {
    const editorTitle = document.getElementById('editor-title');
    const editorContent = document.getElementById('editor-content');

    editorTitle.textContent = `${currentSelectedJob.title} - ${currentSelectedJob.company}`;

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
                <div class="job-meta">${currentSelectedJob.company}</div>
            </div>
            <div class="job-description" id="job-description">
                ${tokenSpans}
            </div>
        </div>
    `;
}

function handleTokenClick(event) {
    const tokenElement = event.target.closest('span');
    if (tokenElement) {
        const tokenId = parseInt(tokenElement.dataset.tokenId);
        const token = currentSelectedJob.tokens.find(t => t.id === tokenId);
        if (token) {
            if (selectedLabel.id === 'unlabeled') {
                token.label = '';
            } else
                token.label = selectedLabel.name;
            renderJobContent(); // Re-render to show the new label
        }
    }
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
    if (!currentSelectedJob || !jobLabels[currentSelectedJob.id]) {
        alert('No labels to save');
        return;
    }

    try {
        updateStatus('Saving labels...');

        const payload = {
            jobId: currentSelectedJob.id,
            tokens: currentSelectedJob.tokens,
            labels: jobLabels[currentSelectedJob.id],
            timestamp: new Date().toISOString()
        };

        // Replace with actual API call:
        // const response = await fetch(API_ENDPOINTS.saveJobs, {
        //     method: 'POST',
        //     headers: {
        //         'Content-Type': 'application/json'
        //     },
        //     body: JSON.stringify(payload)
        // });

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