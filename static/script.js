let currentTranscript = null;
let currentSummary = "";

/* =========================
   FILE SELECTION
========================= */
document.getElementById('audioFile').addEventListener('change', function (e) {
    const fileName = e.target.files[0]?.name || '';
    document.getElementById('fileName').textContent =
        fileName ? `Selected: ${fileName}` : '';
    document.getElementById('transcribeBtn').disabled = !fileName;
});

/* =========================
   TRANSCRIPTION
========================= */
async function transcribeAudio() {
    const file = document.getElementById('audioFile').files[0];
    if (!file) return;

    document.getElementById('uploadBox').style.display = 'none';
    document.getElementById('progressSection').style.display = 'block';

    const formData = new FormData();
    formData.append('audio', file);

    const response = await fetch('/transcribe', {
        method: 'POST',
        body: formData
    });

    const result = await response.json();
    document.getElementById('progressSection').style.display = 'none';

    if (!result.success) {
        alert(result.error);
        return;
    }

    currentTranscript = result.transcript;
    localStorage.setItem("transcript", JSON.stringify(currentTranscript));

    displayTranscript(currentTranscript);
}

/* =========================
   DISPLAY TRANSCRIPT
========================= */
function displayTranscript(transcript) {
    document.getElementById('resultsSection').style.display = 'block';
    document.getElementById('generateSummaryBtn').style.display = 'inline-block';

    document.getElementById('wordCount').textContent =
        transcript.metrics.word_count;
    document.getElementById('duration').textContent =
        `${transcript.metrics.duration.toFixed(0)}s`;
    document.getElementById('confidence').textContent =
        `${(transcript.metrics.avg_confidence * 100).toFixed(1)}%`;

    const container = document.getElementById('transcriptContainer');
    container.innerHTML = '';

    transcript.segments.forEach(seg => {
        container.innerHTML += `
            <div class="transcript-item">
                <div class="transcript-time">
                    ${seg.start.toFixed(1)}s – ${seg.end.toFixed(1)}s
                </div>
                <div class="transcript-text">${seg.text}</div>
            </div>
        `;
    });
}

/* =========================
   GENERATE SUMMARY
========================= */
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

/* =========================
   RENDER FORMATTED SUMMARY
========================= */
function renderSummary(text) {
    const container = document.getElementById("summaryContainer");
    container.innerHTML = "";

    // 🔹 Clean broken lines like "6\n00 PM"
    text = text.replace(/(\d)\n(\d)/g, "$1$2");

    const blocks = text.split(/\n\s*\n/).map(b => b.trim()).filter(Boolean);

    blocks.forEach(block => {
        const lines = block.split("\n").map(l => l.trim()).filter(Boolean);

        const card = document.createElement("div");
        card.className = "summary-card";

        let list = null;

        lines.forEach((line, index) => {

            // 🔷 SECTION TITLE
            if (
                index === 0 &&
                !line.startsWith("-") &&
                !line.startsWith('"') &&
                line === line.toUpperCase() || line.endsWith(":")
            ) {
                const title = document.createElement("h4");
                title.textContent = line.replace(":", "");
                card.appendChild(title);

                list = document.createElement("ul");
                card.appendChild(list);
                return;
            }

            // 🔹 BULLET POINT
            if (line.startsWith("-")) {
                if (!list) {
                    list = document.createElement("ul");
                    card.appendChild(list);
                }
                const li = document.createElement("li");
                li.textContent = line.replace(/^-\s*/, "");
                list.appendChild(li);
                return;
            }

            // 🔸 QUOTE
            if (line.startsWith('"')) {
                const quote = document.createElement("blockquote");
                quote.textContent = line;
                card.appendChild(quote);
                return;
            }

            // 🔹 NORMAL PARAGRAPH
            const p = document.createElement("p");
            p.textContent = line;
            card.appendChild(p);
        });

        container.appendChild(card);
    });

    // ✅ SHOW UI CONTROLS
    document.getElementById("summarySection").style.display = "block";
    document.getElementById("downloadSummaryBtn").style.display = "inline-flex";
}


/* =========================
   DOWNLOAD PDF
========================= */
function downloadSummary() {
    window.open("/download_pdf", "_blank");
}


/* =========================
   RESTORE STATE ON RELOAD
========================= */
document.addEventListener("DOMContentLoaded", () => {
    const savedSummary = localStorage.getItem("summary");

    if (savedSummary) {
        renderSummary(savedSummary);
    }
});


/* =========================
   RESET SESSION
========================= */
function resetSession() {
    localStorage.clear();
    location.reload();
}
