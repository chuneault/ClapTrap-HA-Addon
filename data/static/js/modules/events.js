import { startDetection, stopDetection } from './detection.js';
import { refreshVbanSources } from './vbanSources.js';
import { saveSettings } from './settings.js';

export function setupEventListeners() {
    setupDetectionButtons();
    setupRefreshButton();
    setupThresholdControl();
    setupSoundEventsControls();
    setupParameterChangeListeners();
}

function setupDetectionButtons() {
    const startButton = document.getElementById('startButton');
    const stopButton = document.getElementById('stopButton');

    if (startButton) {
        startButton.addEventListener('click', () => {
            startDetection();
        });
    }
    
    if (stopButton) {
        stopButton.addEventListener('click', stopDetection);
    }
}

function setupRefreshButton() {
    const refreshBtn = document.getElementById('refreshVBANBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshVbanSources);
    }
}

function setupThresholdControl() {
    const threshold = document.getElementById('threshold');
    const thresholdValue = document.getElementById('threshold-value');
    
    if (threshold && thresholdValue) {
        threshold.addEventListener('input', function() {
            thresholdValue.textContent = this.value;
        });
    }
}

function setupParameterChangeListeners() {
    // Ajouter ici les écouteurs pour les changements de paramètres si nécessaire
}

function setupSoundEventsControls() {
    const addButton = document.getElementById('addSoundEventButton');
    const list = document.getElementById('soundEventsList');

    if (addButton && list) {
        addButton.addEventListener('click', () => {
            const item = document.createElement('div');
            item.className = 'list-group-item sound-event-item';
            item.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <input type="text" class="webhook-input sound-event-label" value="" placeholder="Nom du label YAMNet">
                    </div>
                    <div class="source-controls">
                        <label class="switch" title="Activer/Désactiver l'événement">
                            <input type="checkbox" class="sound-event-enabled" checked>
                            <span class="slider round"></span>
                        </label>
                        <button type="button" class="btn btn-light btn-sm delete-sound-event-btn" title="Supprimer l'événement">
                            <span class="icon" style="color: #dc3545;">❌</span>
                        </button>
                    </div>
                </div>
                <div class="setting-control mt-2">
                    <label>Score minimum</label>
                    <input type="number" class="sound-event-threshold" min="0" max="1" step="0.01" value="0.20">
                </div>
            `;
            list.appendChild(item);
        });

        list.addEventListener('click', (event) => {
            const deleteButton = event.target.closest('.delete-sound-event-btn');
            if (!deleteButton) {
                return;
            }

            const item = deleteButton.closest('.sound-event-item');
            if (item) {
                item.remove();
            }
        });
    }
}
