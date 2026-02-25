let currentTranscript = null;
let currentSummary = "";

/* FILE SELECTION */
document.getElementById('audioFile').addEventListener('change', function (e) {
    const fileName = e.target.files[0]?.name || '';
    document.getElementById('fileName').textContent = fileName ? `Selected: ${fileName}` : '';
    document.getElementById('transcribeBtn').disabled = !fileName;
});

/* TRANSCRIPTION */
async function transcribeAudio() {
    const file = document.getElementById('audioFile').files[0];
    if (!file) return;

    document.getElementById('uploadBox').style.display = 'none';
    document.getElementById('progressSection').style.display = 'block';

    const formData = new FormData();
    formData.append('audio', file);

    const response = await fetch('/transcribe', { method: 'POST', body: formData });
    const result = await response.json();
    document.getElementById('progressSection').style.display = 'none';

    if (!result.success) { alert(result.error); return; }

    if (result.merged_transcript) {
        currentTranscript = { segments: result.merged_transcript, metrics: result.transcript.metrics };
    } else {
        currentTranscript = result.transcript;
    }

    localStorage.setItem("transcript", JSON.stringify(currentTranscript));
    displayTranscript(currentTranscript);
}

/* DISPLAY TRANSCRIPT */
function displayTranscript(transcript) {
    document.getElementById('resultsSection').style.display = 'block';
    document.getElementById('generateSummaryBtn').style.display = 'inline-block';
    document.getElementById('actionItemsBtn').style.display = 'inline-block';
    document.getElementById('sentimentBtn').style.display = 'inline-block';

    document.getElementById('wordCount').textContent = transcript.metrics.word_count;
    document.getElementById('duration').textContent = `${transcript.metrics.duration.toFixed(0)}s`;
    document.getElementById('confidence').textContent = `${(transcript.metrics.avg_confidence * 100).toFixed(1)}%`;

    const container = document.getElementById('transcriptContainer');
    container.innerHTML = '';

    transcript.segments.forEach(seg => {
        container.innerHTML += `
            <div class="transcript-item">
                <div class="transcript-time">${seg.start.toFixed(1)}s – ${seg.end.toFixed(1)}s</div>
                <div class="transcript-text">
                    ${seg.speaker ? `<strong>[${seg.speaker}]</strong> ` : ""}
                    ${seg.text}
                </div>
            </div>
        `;
    });
}

/* DOWNLOAD TRANSCRIPT JSON */
function downloadTranscript() {
    if (!currentTranscript) return;
    const blob = new Blob([JSON.stringify(currentTranscript, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "transcript.json";
    a.click();
    URL.revokeObjectURL(url);
}

/* GENERATE SUMMARY */
async function generateSummary() {
    document.getElementById('summarySection').style.display = 'block';
    const summaryBox = document.getElementById('summaryContainer');
    summaryBox.innerHTML = `<p class="loading">Generating professional summary…</p>`;

    const response = await fetch('/summarize', { method: 'POST' });
    const data = await response.json();

    if (!data.success) {
        summaryBox.innerHTML = `<p class="error">${data.error}</p>`;
        return;
    }

    currentSummary = data.summary;
    localStorage.setItem("summary", currentSummary);
    renderSummary(currentSummary);
}

/* RENDER FORMATTED SUMMARY */
function renderSummary(text) {
    const container = document.getElementById("summaryContainer");
    container.innerHTML = "";

    text = text.replace(/(\d)\n(\d)/g, "$1$2");
    const blocks = text.split(/\n\s*\n/).map(b => b.trim()).filter(Boolean);

    blocks.forEach(block => {
        const lines = block.split("\n").map(l => l.trim()).filter(Boolean);
        const card = document.createElement("div");
        card.className = "summary-card";
        let list = null;

        lines.forEach((line, index) => {
            if (index === 0 && !line.startsWith("-") && !line.startsWith('"') &&
                (line === line.toUpperCase() || line.endsWith(":"))) {
                const title = document.createElement("h4");
                title.textContent = line.replace(":", "");
                card.appendChild(title);
                list = document.createElement("ul");
                card.appendChild(list);
                return;
            }
            if (line.startsWith("-")) {
                if (!list) { list = document.createElement("ul"); card.appendChild(list); }
                const li = document.createElement("li");
                li.textContent = line.replace(/^-\s*/, "");
                list.appendChild(li);
                return;
            }
            if (line.startsWith('"')) {
                const quote = document.createElement("blockquote");
                quote.textContent = line;
                card.appendChild(quote);
                return;
            }
            const p = document.createElement("p");
            p.textContent = line;
            card.appendChild(p);
        });

        container.appendChild(card);
    });

    document.getElementById("downloadSummaryBtn").style.display = "inline-flex";
}

/* DOWNLOAD SUMMARY PDF */
function downloadSummary() {
    window.open("/download_pdf", "_blank");
}

/* RESTORE STATE ON RELOAD */
document.addEventListener("DOMContentLoaded", () => {
    const savedTranscript = localStorage.getItem("transcript");
    const savedSummary = localStorage.getItem("summary");
    if (savedTranscript) {
        currentTranscript = JSON.parse(savedTranscript);
        displayTranscript(currentTranscript);
    }
    if (savedSummary) { renderSummary(savedSummary); }
});

/* RESET SESSION */
function resetSession() {
    localStorage.clear();
    location.reload();
}

/* ACTION ITEMS */
async function extractActionItems() {
    const actionOutput = document.getElementById('action-output');
    actionOutput.innerHTML = '<p class="loading"> Extracting action items with Groq...</p>';
    actionOutput.style.display = 'block';

    try {
        const response = await fetch('/action_items', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (data.success) {
            actionOutput.innerHTML = `
                <div class="result-box">
                    <h3> Action Items Found: ${data.count}</h3>
                    <div style="background:#f8f9fa; padding:20px; border-radius:8px; white-space:pre-wrap; font-family:monospace; font-size:14px;">
                        ${data.formatted}
                    </div>
                    <button onclick="downloadActionItems()" style="width:100%; margin-top:10px; padding:10px; background:#28a745; color:white; border:none; border-radius:6px; cursor:pointer;">
                         Download Action Items JSON
                    </button>
                </div>`;
        } else {
            actionOutput.innerHTML = `<p class="error"> ${data.error}</p>`;
        }
    } catch (error) {
        actionOutput.innerHTML = '<p class="error"> Failed to extract action items.</p>';
        console.error('Action items error:', error);
    }
}

/* SENTIMENT ANALYSIS */
async function analyzeSentiment() {
    const sentimentOutput = document.getElementById('sentiment-output');
    sentimentOutput.innerHTML = '<p class="loading">Analysing sentiment...</p>';
    sentimentOutput.style.display = 'block';

    try {
        const response = await fetch('/sentiment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (!data.success) {
            sentimentOutput.innerHTML = `<p class="error">${data.error}</p>`;
            return;
        }

        const overall = data.result.overall;
        const segments = data.result.segments;

        // Calculate breakdown from segments
        let counts = { Positive: 0, Neutral: 0, Negative: 0 };
        segments.forEach(seg => {
            if (counts[seg.sentiment] !== undefined) counts[seg.sentiment]++;
        });
        const total = segments.length || 1;
        const pctPositive = Math.round((counts.Positive / total) * 100);
        const pctNeutral  = Math.round((counts.Neutral  / total) * 100);
        const pctNegative = Math.round((counts.Negative / total) * 100);

        // Overall label — "Mixed" if neither side dominates
        let overallLabel = overall.sentiment;
        if (pctPositive > 0 && pctNegative > 0 && Math.abs(pctPositive - pctNegative) < 20) {
            overallLabel = 'Mixed';
        }

        const labelColor = {
            Positive: '#28a745',
            Negative: '#dc3545',
            Neutral:  '#6c757d',
            Mixed:    '#fd7e14'
        };

        const pillColor = {
            Positive: { bg: '#d4edda', text: '#155724' },
            Negative: { bg: '#f8d7da', text: '#721c24' },
            Neutral:  { bg: '#e2e3e5', text: '#383d41' }
        };

        // Segment rows
        const segmentRows = segments.map(seg => {
            const pill = pillColor[seg.sentiment] || pillColor.Neutral;
            return `
                <tr>
                    <td style="padding:10px 8px; border-bottom:1px solid #eee; font-weight:500;">${seg.label}</td>
                    <td style="padding:10px 8px; border-bottom:1px solid #eee;">
                        <span style="background:${pill.bg}; color:${pill.text}; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600;">
                            ${seg.sentiment}
                        </span>
                    </td>
                    <td style="padding:10px 8px; border-bottom:1px solid #eee; color:#555; font-size:13px;">${seg.reason}</td>
                </tr>
            `;
        }).join('');

        sentimentOutput.innerHTML = `
            <div class="result-box">
                <h3>Sentiment Analysis</h3>

                <!-- Overall label + summary -->
                <div style="margin-bottom:16px;">
                    <span style="font-size:18px; font-weight:700; color:${labelColor[overallLabel] || '#333'};">
                        ${overallLabel}
                    </span>
                    <p style="margin:6px 0 0 0; color:#555; font-size:14px;">${overall.summary}</p>
                </div>

                <!-- Tri-color bar -->
                <div style="margin-bottom:8px;">
                    <div style="display:flex; height:14px; border-radius:8px; overflow:hidden; background:#e9ecef;">
                        <div style="width:${pctPositive}%; background:#28a745; transition:width 0.6s ease;"></div>
                        <div style="width:${pctNeutral}%;  background:#adb5bd; transition:width 0.6s ease;"></div>
                        <div style="width:${pctNegative}%; background:#dc3545; transition:width 0.6s ease;"></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:12px; color:#777; margin-top:5px;">
                        <span style="color:#28a745;">${pctPositive}% Positive</span>
                        <span style="color:#adb5bd;">${pctNeutral}% Neutral</span>
                        <span style="color:#dc3545;">${pctNegative}% Negative</span>
                    </div>
                </div>

                <!-- Segment table -->
                <table style="width:100%; border-collapse:collapse; font-size:14px; margin-top:16px;">
                    <thead>
                        <tr style="background:#f1f1f1;">
                            <th style="padding:10px 8px; text-align:left; font-weight:600;">Speaker / Topic</th>
                            <th style="padding:10px 8px; text-align:left; font-weight:600;">Sentiment</th>
                            <th style="padding:10px 8px; text-align:left; font-weight:600;">Reason</th>
                        </tr>
                    </thead>
                    <tbody>${segmentRows}</tbody>
                </table>
            </div>`;

    } catch (error) {
        sentimentOutput.innerHTML = '<p class="error">Failed to analyse sentiment.</p>';
        console.error('Sentiment error:', error);
    }
}

function downloadActionItems() {
    fetch('/action_items', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            const blob = new Blob([JSON.stringify(data.items, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'action_items.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
}
