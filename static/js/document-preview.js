/**
 * document-preview.js
 * 3-Tier Document Preview System — shared across all 8 detail templates.
 *
 * Tier 0 (pre-check): converted_pdf already exists → native PDF iframe instantly
 * Tier 1 (Google Docs Viewer): attempt external render, show iframe if Google loads
 * Tier 2 (LibreOffice AJAX): 8s timeout triggers lazy server-side conversion
 * Tier 3 (Download fallback): shown if Tier 2 also fails
 *
 * Usage:
 *   openPreview(originalUrl, convertedPdfUrl, docId, docType)
 *   closePreviewModal()
 *
 * Required DOM:
 *   #previewModal       — the modal overlay (hidden by default)
 *   #previewContent     — container for the preview content area
 *   #previewModalTitle  — optional title element
 */

'use strict';

// ---------------------------------------------------------------------------
// PreviewState — loading state manager
// ---------------------------------------------------------------------------
const PreviewState = {
    _timeout: null,
    _abortController: null,

    showLoading(message) {
        const content = document.getElementById('previewContent');
        if (!content) return;
        content.innerHTML = `
            <div id="previewSpinner" class="flex flex-col items-center justify-center h-full gap-4">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                <p id="previewStatusMessage" class="text-sm font-medium text-gray-500">${message}</p>
            </div>`;
    },

    showIframe(url) {
        const content = document.getElementById('previewContent');
        if (!content) return;
        content.innerHTML = `<iframe
            src="${url}"
            class="w-full h-full border-0"
            allowfullscreen
            loading="lazy"
        ></iframe>`;
    },

    showImage(url) {
        const content = document.getElementById('previewContent');
        if (!content) return;
        content.innerHTML = `<div class="flex items-center justify-center h-full bg-gray-50 p-4">
            <img
                src="${url}"
                class="max-w-full max-h-full object-contain rounded shadow"
                alt="Document preview"
            />
        </div>`;
    },

    showError(originalUrl) {
        const content = document.getElementById('previewContent');
        if (!content) return;
        content.innerHTML = `
            <div class="flex flex-col items-center justify-center h-full gap-4 text-center px-8">
                <div class="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center">
                    <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293
                                 l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                </div>
                <div>
                    <p class="font-semibold text-gray-700">Preview Unavailable</p>
                    <p class="text-sm text-gray-500 mt-1">
                        This document could not be previewed.<br>
                        Please download the file to view it.
                    </p>
                </div>
                <a href="${originalUrl}"
                   download
                   class="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white
                          rounded-xl text-sm font-semibold hover:bg-blue-700 transition-colors shadow-md">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5m0 0l5-5m-5 5V3"/>
                    </svg>
                    Download File
                </a>
            </div>`;
    },

    reset() {
        if (this._timeout) {
            clearTimeout(this._timeout);
            this._timeout = null;
        }
        if (this._abortController) {
            this._abortController.abort();
            this._abortController = null;
        }
    },
};

// ---------------------------------------------------------------------------
// openPreview — entry point called by all template preview buttons
// ---------------------------------------------------------------------------

/**
 * @param {string} originalUrl      — URL of the original file (relative or absolute)
 * @param {string} convertedPdfUrl  — URL of the already-converted PDF, or empty string
 * @param {string|number} docId     — model instance PK (UUID string or integer)
 * @param {string} docType          — one of the whitelisted document_type keys
 * @param {string} [title]          — optional title shown in the modal header
 */
function openPreview(originalUrl, convertedPdfUrl, docId, docType, title) {
    const modal = document.getElementById('previewModal');
    if (!modal) { console.error('[Preview] #previewModal not found'); return; }

    // Update optional title
    const titleEl = document.getElementById('previewModalTitle');
    if (titleEl && title) titleEl.textContent = title;

    // Update the download link in the modal header
    const downloadLink = document.getElementById('downloadLink');
    if (downloadLink) {
        downloadLink.href = originalUrl;
    }

    // Show modal
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.body.style.overflow = 'hidden';

    // --- Tier 0: converted PDF already cached on the server ---
    if (convertedPdfUrl) {
        PreviewState.showIframe(convertedPdfUrl);
        return;
    }

    const ext = originalUrl.split('?')[0].split('.').pop().toLowerCase();

    // --- Native PDF ---
    if (ext === 'pdf') {
        PreviewState.showIframe(originalUrl);
        return;
    }

    // --- Native image ---
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) {
        PreviewState.showImage(originalUrl);
        return;
    }

    // --- DOCX / XLSX / other: Tier 1 → Tier 2 ---
    PreviewState.showLoading('Loading preview\u2026');

    // Guard against doubled URLs when storage backend returns absolute URLs
    const absoluteUrl = originalUrl.startsWith('http')
        ? originalUrl
        : window.location.origin + originalUrl;

    const gviewUrl = `https://docs.google.com/gview?url=${encodeURIComponent(absoluteUrl)}&embedded=true`;

    const iframe = document.createElement('iframe');
    iframe.className = 'w-full h-full border-0';
    iframe.setAttribute('allowfullscreen', '');
    iframe.style.display = 'none';
    iframe.src = gviewUrl;

    // Tier 2 always fires after 8s — it is the SOLE Tier 2 trigger.
    // onload cannot be trusted: Google Docs fires onload even when it shows
    // a blank/error page for files on private LAN IPs it cannot reach.
    PreviewState._timeout = setTimeout(() => {
        PreviewState.showLoading('Generating local preview\u2026');
        _triggerTier2(originalUrl, docId, docType);
    }, 8000);

    // onload only removes the spinner and reveals the iframe.
    // It does NOT clear the timeout — Tier 2 still fires regardless.
    iframe.onload = () => {
        const spinner = document.getElementById('previewSpinner');
        if (spinner) spinner.remove();
        iframe.style.display = '';
    };

    const content = document.getElementById('previewContent');
    if (content) content.appendChild(iframe);
}

// ---------------------------------------------------------------------------
// _triggerTier2 — AJAX LibreOffice conversion
// ---------------------------------------------------------------------------
function _triggerTier2(originalUrl, docId, docType) {
    PreviewState._abortController = new AbortController();

    fetch('/budgets/api/convert-to-pdf/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': _getCsrfToken(),
        },
        body: JSON.stringify({ document_id: docId, document_type: docType }),
        signal: PreviewState._abortController.signal,
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                PreviewState.showIframe(data.pdf_url);
            } else {
                PreviewState.showError(originalUrl);
            }
        })
        .catch(err => {
            if (err.name !== 'AbortError') {
                PreviewState.showError(originalUrl);
            }
        });
}

// ---------------------------------------------------------------------------
// closePreviewModal — resets state and hides the modal
// ---------------------------------------------------------------------------
function closePreviewModal() {
    PreviewState.reset();

    const modal = document.getElementById('previewModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }

    const content = document.getElementById('previewContent');
    if (content) content.innerHTML = '';

    document.body.style.overflow = '';
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function _getCsrfToken() {
    // Try hidden input first (present in any page with {% csrf_token %})
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input) return input.value;
    // Fall back to cookie
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
}

// Close modal on Escape key
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closePreviewModal();
});
