/* ══════════════════════════════════════════════════════════════════════
   Pi Brivet — Frontend Application Logic
   ══════════════════════════════════════════════════════════════════════ */

// ── State ─────────────────────────────────────────────────────────────
let currentMode = "manual";
let pollInterval = null;
let historyPage = 1;
let pendingSettings = null; // buffered for SAHI warning confirmation
let liveDetectActive = false;
let liveStatusInterval = null;

// ── DOM Refs ──────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const feedImage = $("feedImage");
const feedOverlay = $("feedOverlay");
const connectionDot = $("connectionStatus").querySelector(".status-dot");
const connectionText = $("connectionStatus").querySelector(".status-text");

const btnManual = $("btnManual");
const btnAutomated = $("btnAutomated");
const manualPanel = $("manualPanel");
const automatedPanel = $("automatedPanel");
const btnCapture = $("btnCapture");
const cooldownBar = $("cooldownBar");
const cooldownFill = $("cooldownFill");
const cooldownText = $("cooldownText");

const autoConfig = $("autoConfig");
const autoStatus = $("autoStatus");
const autoRing = $("autoRing");
const autoCount = $("autoCount");
const autoNextText = $("autoNextText");

const processingCard = $("processingCard");
const latestResultCard = $("latestResultCard");
const resultCount = $("resultCount");
const resultDuration = $("resultDuration");
const resultImage = $("resultImage");

const historyGrid = $("historyGrid");
const historyPagination = $("historyPagination");

const confidenceSlider = $("confidence");
const confidenceValue = $("confidenceValue");
const slicesSlider = $("slices");
const slicesValue = $("slicesValue");
const slicesHint = $("slicesHint");

const lightbox = $("lightbox");
const lightboxImage = $("lightboxImage");
const sahiModal = $("sahiModal");
const sahiWarning = $("sahiWarningText");
const toastContainer = $("toastContainer");


// ── Init ──────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    setupFeedMonitor();
    loadSettings();
    loadHistory();
    startPolling();
});


// ── Feed Monitor ──────────────────────────────────────────────────────
function setupFeedMonitor() {
    feedImage.onload = () => {
        feedOverlay.classList.add("hidden");
        setConnection("online");
    };
    feedImage.onerror = () => {
        setConnection("offline");
        // Retry after 3s
        setTimeout(() => {
            feedImage.src = "/api/feed?" + Date.now();
        }, 3000);
    };
}

function setConnection(state) {
    connectionDot.className = "status-dot";
    if (state === "online") {
        connectionDot.classList.add("status-dot--online");
        connectionText.textContent = "Connected";
    } else if (state === "offline") {
        connectionDot.classList.add("status-dot--offline");
        connectionText.textContent = "Disconnected";
    } else {
        connectionDot.classList.add("status-dot--connecting");
        connectionText.textContent = "Connecting…";
    }
}


// ── Mode Switching ────────────────────────────────────────────────────
function setMode(mode) {
    currentMode = mode;

    btnManual.classList.toggle("mode-btn--active", mode === "manual");
    btnAutomated.classList.toggle("mode-btn--active", mode === "automated");

    manualPanel.classList.toggle("hidden", mode !== "manual");
    automatedPanel.classList.toggle("hidden", mode !== "automated");
}


// ── Manual Capture ────────────────────────────────────────────────────
async function triggerCapture() {
    btnCapture.disabled = true;
    showProcessing(true);

    try {
        const res = await fetch("/api/capture", { method: "POST" });
        const data = await res.json();

        if (data.status === "ok") {
            showResult(data.data);
            showToast(`Detected ${data.data.object_count} object(s)`, "success");
            loadHistory();
        } else {
            showToast(data.message || "Capture failed.", "error");
        }
    } catch (err) {
        showToast("Network error: " + err.message, "error");
    } finally {
        showProcessing(false);
        btnCapture.disabled = false;
    }
}


// ── Automated Capture ─────────────────────────────────────────────────
async function startAutomated() {
    const interval = parseInt($("autoInterval").value, 10);
    const maxCaptures = parseInt($("autoMaxCaptures").value, 10);

    if (isNaN(interval) || interval < 45) {
        showToast("Interval must be at least 45 seconds.", "warning");
        return;
    }
    if (isNaN(maxCaptures) || maxCaptures < 1) {
        showToast("Max captures must be at least 1.", "warning");
        return;
    }

    try {
        const res = await fetch("/api/capture/auto/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ interval, max_captures: maxCaptures }),
        });
        const data = await res.json();

        if (data.status === "ok") {
            autoConfig.classList.add("hidden");
            autoStatus.classList.remove("hidden");
            showToast("Automated capture started!", "success");
        } else {
            showToast(data.message || "Could not start.", "error");
        }
    } catch (err) {
        showToast("Network error: " + err.message, "error");
    }
}

async function stopAutomated() {
    try {
        await fetch("/api/capture/auto/stop", { method: "POST" });
        autoConfig.classList.remove("hidden");
        autoStatus.classList.add("hidden");
        setMode("manual");
        showToast("Automated capture stopped.", "info");
        loadHistory();
    } catch (err) {
        showToast("Error stopping automation.", "error");
    }
}


// ── Status Polling ────────────────────────────────────────────────────
function startPolling() {
    pollInterval = setInterval(pollStatus, 2000);
}

async function pollStatus() {
    try {
        const res = await fetch("/api/capture/status");
        const data = await res.json();
        updateStatusUI(data);
    } catch {
        // Silently ignore network blips
    }
}

function updateStatusUI(status) {
    // Cooldown bar
    if (status.cooldown_remaining > 0) {
        const pct = ((45 - status.cooldown_remaining) / 45) * 100;
        cooldownBar.classList.add("visible");
        cooldownFill.style.width = pct + "%";
        cooldownText.textContent = `Cooldown: ${Math.ceil(status.cooldown_remaining)}s remaining`;
        btnCapture.disabled = true;
    } else {
        cooldownBar.classList.remove("visible");
        if (!status.is_processing) {
            btnCapture.disabled = false;
        }
    }

    // Processing state
    if (status.is_processing) {
        showProcessing(true);
    }

    // Automated status
    if (status.mode === "automated") {
        if (currentMode !== "automated") setMode("automated");
        autoConfig.classList.add("hidden");
        autoStatus.classList.remove("hidden");

        const done = status.auto_captures_done || 0;
        const total = status.auto_max_captures || 1;
        autoCount.textContent = `${done}/${total}`;

        // Update ring
        const circumference = 2 * Math.PI * 35; // r=35 in SVG
        const offset = circumference - (done / total) * circumference;
        autoRing.style.strokeDashoffset = offset;

        const nextIn = status.auto_next_capture_in;
        autoNextText.textContent = nextIn > 0
            ? `Next capture in ${Math.ceil(nextIn)}s`
            : "Capturing…";

        // Reload history when new captures appear
        if (status.last_result && status.last_result !== window._lastKnownResult) {
            window._lastKnownResult = status.last_result;
            showResult(status.last_result);
            loadHistory();
        }
    } else {
        if (currentMode === "automated" && !autoConfig.classList.contains("hidden") === false) {
            // Automation ended, revert UI
            autoConfig.classList.remove("hidden");
            autoStatus.classList.add("hidden");
        }
    }
}

function showProcessing(visible) {
    processingCard.classList.toggle("hidden", !visible);
}

function showResult(data) {
    showProcessing(false);
    latestResultCard.classList.remove("hidden");
    resultCount.textContent = data.object_count;
    resultDuration.textContent = data.duration_ms ? (data.duration_ms / 1000).toFixed(1) + "s" : "—";
    resultImage.src = `/api/history/${data.id}/image`;
}


// ── Settings ──────────────────────────────────────────────────────────
async function loadSettings() {
    try {
        const res = await fetch("/api/settings");
        const data = await res.json();
        confidenceSlider.value = Math.round(data.confidence * 100);
        confidenceValue.textContent = Math.round(data.confidence * 100) + "%";
        slicesSlider.value = data.slices;
        updateSlicesDisplay(data.slices);
    } catch { /* ignore */ }
}

function onConfidenceChange(val) {
    confidenceValue.textContent = val + "%";
}

function onSlicesChange(val) {
    updateSlicesDisplay(parseInt(val, 10));
}

function updateSlicesDisplay(n) {
    slicesValue.textContent = `${n}×${n}`;
    const tiles = n * n;
    const estSeconds = tiles * 3;
    slicesHint.textContent = `${tiles} tile${tiles > 1 ? "s" : ""} — estimated ~${estSeconds}s per capture`;
}

async function applySettings() {
    const confidence = parseInt(confidenceSlider.value, 10) / 100;
    const slices = parseInt(slicesSlider.value, 10);

    // Show SAHI warning for high slice counts
    if (slices >= 4) {
        const tiles = slices * slices;
        const estSeconds = tiles * 3;
        sahiWarning.textContent =
            `You are setting ${slices}×${slices} slices (${tiles} tiles). ` +
            `Each capture will take approximately ${estSeconds} seconds to process on the Raspberry Pi. ` +
            `Are you sure you want to apply this setting?`;
        pendingSettings = { confidence, slices };
        sahiModal.classList.remove("hidden");
        return;
    }

    await doApplySettings(confidence, slices);
}

function cancelSettings() {
    sahiModal.classList.add("hidden");
    pendingSettings = null;
}

async function confirmSettings() {
    sahiModal.classList.add("hidden");
    if (pendingSettings) {
        await doApplySettings(pendingSettings.confidence, pendingSettings.slices);
        pendingSettings = null;
    }
}

async function doApplySettings(confidence, slices) {
    try {
        const res = await fetch("/api/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ confidence, slices }),
        });
        const data = await res.json();

        if (data.status === "ok") {
            showToast("Settings applied.", "success");
            if (data.warning) {
                showToast(data.warning, "warning");
            }
        } else {
            showToast("Failed to update settings.", "error");
        }
    } catch (err) {
        showToast("Network error: " + err.message, "error");
    }
}


// ── History ───────────────────────────────────────────────────────────
async function loadHistory(page = 1) {
    historyPage = page;
    try {
        const res = await fetch(`/api/history?page=${page}&per_page=12`);
        const data = await res.json();
        renderHistory(data);
    } catch { /* ignore */ }
}

function renderHistory(data) {
    if (!data.data || data.data.length === 0) {
        historyGrid.innerHTML = '<p class="history-empty">No captures yet. Take your first capture!</p>';
        historyPagination.innerHTML = "";
        return;
    }

    historyGrid.innerHTML = data.data.map((d) => {
        const time = new Date(d.timestamp).toLocaleString(undefined, {
            month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
        });
        return `
            <div class="history-item" onclick="openLightbox('/api/history/${d.id}/image')">
                <img src="/api/history/${d.id}/image" alt="Detection ${d.id}" loading="lazy" />
                <div class="history-item__info">
                    <span class="history-item__count">${d.object_count} obj</span>
                    <span class="history-item__time">${time}</span>
                </div>
                <button class="history-item__delete" onclick="event.stopPropagation(); deleteDetection(${d.id})" title="Delete">&times;</button>
            </div>
        `;
    }).join("");

    // Pagination
    if (data.pages > 1) {
        let html = "";
        for (let p = 1; p <= data.pages; p++) {
            const cls = p === data.page ? "btn btn--primary btn--sm" : "btn btn--secondary btn--sm";
            html += `<button class="${cls}" onclick="loadHistory(${p})">${p}</button>`;
        }
        historyPagination.innerHTML = html;
    } else {
        historyPagination.innerHTML = "";
    }
}

async function deleteDetection(id) {
    if (!confirm("Delete this detection record?")) return;
    try {
        await fetch(`/api/history/${id}`, { method: "DELETE" });
        showToast("Detection deleted.", "info");
        loadHistory(historyPage);
    } catch {
        showToast("Failed to delete.", "error");
    }
}


// ── Lightbox ──────────────────────────────────────────────────────────
function openLightbox(src) {
    lightboxImage.src = src;
    lightbox.classList.remove("hidden");
}

function closeLightbox() {
    lightbox.classList.add("hidden");
    lightboxImage.src = "";
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeLightbox();
});


// ── Toasts ────────────────────────────────────────────────────────────
function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.transition = "opacity 0.3s, transform 0.3s";
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}


// ── Live Object Detection ─────────────────────────────────────────────

async function toggleLiveDetection() {
    if (liveDetectActive) {
        await stopLiveDetection();
    } else {
        await startLiveDetection();
    }
}

async function startLiveDetection() {
    const btn = $("btnLiveToggle");
    btn.disabled = true;

    try {
        // Send settings first
        const confidence = parseInt($("liveConfidence").value, 10) / 100;
        const resolution = $("liveResolution").value;

        await fetch("/api/live/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ confidence, resolution }),
        });

        // Start live detection
        const res = await fetch("/api/live/start", { method: "POST" });
        const data = await res.json();

        if (data.status === "ok") {
            liveDetectActive = true;

            // Switch feed source to live detection stream
            feedImage.src = "/api/live/feed?" + Date.now();

            // Update UI
            $("liveToggleText").textContent = "Stop Live Detection";
            btn.classList.add("btn--active-danger");
            $("detectBadge").classList.remove("hidden");
            $("feedStats").classList.remove("hidden");

            // Start polling live status
            liveStatusInterval = setInterval(pollLiveStatus, 1000);

            showToast("Live detection started!", "success");
        } else {
            showToast(data.message || "Failed to start.", "error");
        }
    } catch (err) {
        showToast("Network error: " + err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

async function stopLiveDetection() {
    const btn = $("btnLiveToggle");
    btn.disabled = true;

    try {
        await fetch("/api/live/stop", { method: "POST" });

        liveDetectActive = false;

        // Switch feed back to normal preview
        feedImage.src = "/api/feed?" + Date.now();

        // Update UI
        $("liveToggleText").textContent = "Start Live Detection";
        btn.classList.remove("btn--active-danger");
        $("detectBadge").classList.add("hidden");
        $("feedStats").classList.add("hidden");

        // Stop polling
        if (liveStatusInterval) {
            clearInterval(liveStatusInterval);
            liveStatusInterval = null;
        }

        showToast("Live detection stopped.", "info");
    } catch (err) {
        showToast("Error stopping live detection.", "error");
    } finally {
        btn.disabled = false;
    }
}

async function pollLiveStatus() {
    if (!liveDetectActive) return;
    try {
        const res = await fetch("/api/live/status");
        const data = await res.json();
        $("statFps").textContent = data.fps + " FPS";
        $("statObjects").textContent = data.object_count + " object" + (data.object_count !== 1 ? "s" : "");
    } catch { /* ignore */ }
}

function onLiveConfidenceChange(val) {
    $("liveConfidenceValue").textContent = val + "%";

    // Apply immediately if live detection is active
    if (liveDetectActive) {
        fetch("/api/live/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ confidence: parseInt(val, 10) / 100 }),
        }).catch(() => { });
    }
}

async function onLiveResolutionChange(val) {
    if (!liveDetectActive) return; // Will be applied on start

    showToast("Changing resolution… feed will briefly pause.", "info");
    try {
        await fetch("/api/live/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ resolution: val }),
        });
        // Reconnect the feed (new resolution)
        feedImage.src = "/api/live/feed?" + Date.now();
    } catch (err) {
        showToast("Failed to change resolution.", "error");
    }
}
