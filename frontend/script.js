const API_BASE = "/api";

// Elements
const uploadScreen = document.getElementById('upload-screen');
const dashboardScreen = document.getElementById('dashboard-screen');
const uploadForm = document.getElementById('upload-form');
const uploadStatus = document.getElementById('upload-status');
const auditTableBody = document.querySelector('#audit-table tbody');
const visualsGrid = document.getElementById('visuals-grid');
const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const sendChatBtn = document.getElementById('send-chat-btn');
const newDatasetBtn = document.getElementById('new-dataset-btn');
const demoBtn = document.getElementById('demo-btn');

// Advanced UI Elements
const encodingLogDiv = document.getElementById('encoding-log');
const corrOutputDiv = document.getElementById('corr-output');

function populateSelects(num_cols, cat_cols) {
    const allCols = [...num_cols, ...cat_cols];
    
    // Transform selects
    let tCol = document.getElementById('transform-col');
    if (tCol) {
        tCol.innerHTML = '';
        allCols.forEach(c => {
            tCol.innerHTML += `<option value="${c}">${c}</option>`;
        });
    }
    
    // Scatter selects
    let sX = document.getElementById('scatter-x');
    let sY = document.getElementById('scatter-y');
    let sH = document.getElementById('scatter-hue');
    sX.innerHTML = ''; sY.innerHTML = ''; sH.innerHTML = '<option value="">None</option>';
    num_cols.forEach(c => {
        sX.innerHTML += `<option value="${c}">${c}</option>`;
        sY.innerHTML += `<option value="${c}">${c}</option>`;
    });
    cat_cols.forEach(c => {
        sH.innerHTML += `<option value="${c}">${c}</option>`;
    });
    
    // PCA selects
    let pH = document.getElementById('pca-hue');
    pH.innerHTML = '<option value="">None</option>';
    cat_cols.forEach(c => {
        pH.innerHTML += `<option value="${c}">${c}</option>`;
    });
    
    // AutoML selects
    let amT = document.getElementById('automl-target');
    amT.innerHTML = '';
    allCols.forEach(c => {
        amT.innerHTML += `<option value="${c}">${c}</option>`;
    });
    
    // Spark selects
    const sparkSelects = [
        'spark-transform-col', 'spark-filter-col', 'spark-group-col', 
        'spark-agg-col', 'spark-win-partition', 'spark-win-order', 
        'spark-win-target', 'spark-sort-col'
    ];
    sparkSelects.forEach(id => {
        let el = document.getElementById(id);
        if (el) {
            el.innerHTML = '';
            allCols.forEach(c => {
                el.innerHTML += `<option value="${c}">${c}</option>`;
            });
        }
    });
}

// Scatter Elements
const scatterX = document.getElementById('scatter-x');
const scatterY = document.getElementById('scatter-y');
const scatterHue = document.getElementById('scatter-hue');
const scatterReg = document.getElementById('scatter-reg');
const plotScatterBtn = document.getElementById('plot-scatter-btn');
const scatterOutput = document.getElementById('scatter-output');

const pcaHue = document.getElementById('pca-hue');
const runPcaBtn = document.getElementById('run-pca-btn');
const pcaMsg = document.getElementById('pca-msg');
const pcaOutput = document.getElementById('pca-output');
// Scorecard
const scoreRows = document.getElementById('score-rows');
const scoreMissing = document.getElementById('score-missing');
const scoreSkew = document.getElementById('score-skew');

// Actions
const autoCleanBtn = document.getElementById('auto-clean-btn');
const downloadCleanBtn = document.getElementById('download-clean-btn');

let currentChatHistory = [];
let sessionId = null;
let currentAbtController = null; // Used to stop AI chat stream

// Theme Logic
const themeBtn = document.getElementById('theme-toggle-btn');
let isLightMode = localStorage.getItem('theme') === 'light';

function applyTheme() {
    if (isLightMode) {
        document.documentElement.setAttribute('data-theme', 'light');
        if (themeBtn) themeBtn.textContent = '🌙 Dark Mode';
    } else {
        document.documentElement.setAttribute('data-theme', 'dark');
        if (themeBtn) themeBtn.textContent = '☀️ Light Mode';
    }
}
applyTheme();

if (themeBtn) {
    themeBtn.addEventListener('click', () => {
        isLightMode = !isLightMode;
        localStorage.setItem('theme', isLightMode ? 'light' : 'dark');
        applyTheme();
    });
}

function escapeHTML(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Markdown converter
function renderMarkdown(text) {
    let safeText = escapeHTML(text);
    let html = safeText
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/\*\*(.*)\*\*/gim, '<b>$1</b>')
        .replace(/\*(.*)\*/gim, '<i>$1</i>')
        .replace(/\n/gim, '<br>');
    return html;
}

// Tab Switching Logic
document.querySelectorAll('.tab-btn').forEach(button => {
    button.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
        
        button.classList.add('active');
        document.getElementById(button.dataset.target).classList.add('active');
    });
});

// Drag to Resize Logic
const resizer = document.getElementById('dragMe');
const leftPanel = document.querySelector('.data-panel');
let isResizing = false;

resizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    resizer.classList.add('resizing');
    document.body.style.cursor = 'col-resize';
});

document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    
    // Calculate new width percentage based on mouse position
    const containerWidth = document.querySelector('.dashboard-layout').clientWidth;
    // Keep it between 30% and 85%
    let newWidth = (e.clientX / containerWidth) * 100;
    if (newWidth < 30) newWidth = 30;
    if (newWidth > 85) newWidth = 85;
    
    leftPanel.style.width = `${newWidth}%`;
});

document.addEventListener('mouseup', () => {
    if (isResizing) {
        isResizing = false;
        resizer.classList.remove('resizing');
        document.body.style.cursor = 'default';
    }
});

async function processUpload(formData) {
    uploadStatus.classList.remove('hidden');
    uploadStatus.style.color = 'var(--success)';
    uploadStatus.textContent = 'Uploading and running Polars EDA analysis...';
    
    try {
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error(await response.text());
        
        const data = await response.json();
        sessionId = data.session_id; // Save session UUID
        populateDashboard(data);
        
        // Switch Screens
        uploadScreen.classList.remove('active');
        uploadScreen.classList.add('hidden');
        dashboardScreen.classList.remove('hidden');
        dashboardScreen.classList.add('active');
        
        // Trigger AI Report Stream
        streamInitialReport();
        checkSparkStatus();
        
    } catch (err) {
        uploadStatus.textContent = `Error: ${err.message}`;
        uploadStatus.style.color = 'var(--danger)';
    }
}

function populateDashboard(data) {
        // Populate Scorecard
        scoreRows.textContent = data.shape[0];
        
        let missingCount = 0;
        let skewCount = 0;
        
        // Populate Audit Table
        auditTableBody.innerHTML = '';
        data.audit.forEach(item => {
            if (item.issue === 'Missing Values') missingCount++;
            if (item.issue === 'High Skew') skewCount++;
            
            let severityClass = 'success';
            if (item.severity.includes('Null') && parseFloat(item.severity) > 0) severityClass = 'warning';
            if (item.severity.includes('Null') && parseFloat(item.severity) > 20) severityClass = 'danger';
            if (item.severity.includes('Skewness') && parseFloat(item.severity.split(':')[1]) > 2) severityClass = 'danger';
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${item.feature}</strong></td>
                <td>${item.issue}</td>
                <td><span class="badge ${severityClass}">${item.severity}</span></td>
                <td>${item.action}</td>
            `;
            auditTableBody.appendChild(tr);
        });
        
        scoreMissing.textContent = missingCount;
        if (missingCount > 0) scoreMissing.className = 'score-value warning';
        else scoreMissing.className = 'score-value success';
        
        scoreSkew.textContent = skewCount;
        if (skewCount > 0) scoreSkew.className = 'score-value danger';
        else scoreSkew.className = 'score-value success';
        
        // Show Auto-Clean Button
        autoCleanBtn.classList.remove('hidden');
        downloadCleanBtn.classList.add('hidden');
        
        // Populate ML Preprocessing
        encodingLogDiv.innerHTML = data.encoding_log.join('<br>');
        
        // Populate Preview Table
        const previewTableHead = document.querySelector('#preview-table thead tr');
        const previewTableBody = document.querySelector('#preview-table tbody');
        previewTableHead.innerHTML = '';
        previewTableBody.innerHTML = '';
        
        if (data.encoded_preview && data.encoded_preview.length > 0) {
            const columns = Object.keys(data.encoded_preview[0]);
            columns.forEach(col => {
                const th = document.createElement('th');
                th.textContent = col;
                previewTableHead.appendChild(th);
            });
            
            data.encoded_preview.forEach(row => {
                const tr = document.createElement('tr');
                columns.forEach(col => {
                    const td = document.createElement('td');
                    td.textContent = row[col];
                    tr.appendChild(td);
                });
                previewTableBody.appendChild(tr);
            });
        }
        
        // Populate Dropdowns
        populateSelects(data.num_cols, data.cat_cols);
        
        // Populate Visuals (Lazy Loading setup)
        visualsGrid.innerHTML = '';
        const allCols = [...data.num_cols, ...data.cat_cols];
        
        // Setup Intersection Observer
        const observer = new IntersectionObserver((entries, observer) => {
            entries.forEach(async entry => {
                if (entry.isIntersecting) {
                    const imgEl = entry.target;
                    const colName = imgEl.dataset.col;
                    
                    try {
                        const res = await fetch(`${API_BASE}/visual/${sessionId}/${encodeURIComponent(colName)}`);
                        if(res.ok) {
                            const vdata = await res.json();
                            imgEl.src = `data:image/png;base64,${vdata.image}`;
                            imgEl.style.opacity = '1';
                        }
                    } catch(e) {
                        console.error(e);
                    }
                    observer.unobserve(imgEl);
                }
            });
        }, { rootMargin: '100px' });

        allCols.forEach(col => {
            const div = document.createElement('div');
            div.className = 'visual-item';
            
            const img = document.createElement('img');
            img.dataset.col = col;
            // Placeholder styles
            img.style.minHeight = '250px';
            img.style.backgroundColor = 'var(--surface)';
            img.style.opacity = '0.5';
            img.style.transition = 'opacity 0.3s';
            img.alt = `Distribution of ${col}`;
            
            observer.observe(img);
            
            div.appendChild(img);
            visualsGrid.appendChild(div);
        });
        
        // Populate Correlation
        if (data.correlation) {
            corrOutputDiv.innerHTML = `<img src="data:image/png;base64,${data.correlation}" style="max-width:100%; border-radius:8px;">`;
        } else {
            corrOutputDiv.innerHTML = `<p style="color:var(--text-muted)">Not enough numerical columns for correlation map.</p>`;
        }
        
        // Populate Dropdowns for Transforms, Scatter and PCA
        const transformCol = document.getElementById('transform-col');
        transformCol.innerHTML = '';
        
        scatterX.innerHTML = '';
        scatterY.innerHTML = '';
        scatterHue.innerHTML = '<option value="">None</option>';
        pcaHue.innerHTML = '<option value="">None</option>';
        
        data.num_cols.forEach(col => {
            scatterX.innerHTML += `<option value="${col}">${col}</option>`;
            scatterY.innerHTML += `<option value="${col}">${col}</option>`;
            transformCol.innerHTML += `<option value="${col}">${col}</option>`;
        });
        
        data.cat_cols.forEach(col => {
            scatterHue.innerHTML += `<option value="${col}">${col}</option>`;
            pcaHue.innerHTML += `<option value="${col}">${col}</option>`;
            transformCol.innerHTML += `<option value="${col}">${col}</option>`;
        });
}

uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('dataset');
    const contextInput = document.getElementById('context');
    if (fileInput.files.length === 0) return;
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('context', contextInput.value);
    
    processUpload(formData);
});

// Auto Clean Dataset
autoCleanBtn.addEventListener('click', async () => {
    const originalText = autoCleanBtn.textContent;
    autoCleanBtn.innerHTML = '⚙️ Cleaning...';
    autoCleanBtn.disabled = true;
    
    try {
        const res = await fetch(`${API_BASE}/clean`, {
            headers: { 'session-id': sessionId }
        });
        if (!res.ok) throw new Error(await res.text());
        
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        
        downloadCleanBtn.href = url;
        downloadCleanBtn.download = "ml_ready_dataset.csv";
        
        autoCleanBtn.classList.add('hidden');
        downloadCleanBtn.classList.remove('hidden');
    } catch (err) {
        alert("Cleaning failed: " + err.message);
    } finally {
        autoCleanBtn.innerHTML = originalText;
        autoCleanBtn.disabled = false;
    }
});

// Interactive Transformation Studio
const applyTransformBtn = document.getElementById('apply-transform-btn');
const transformMsg = document.getElementById('transform-msg');

applyTransformBtn.addEventListener('click', async () => {
    const col = document.getElementById('transform-col').value;
    const transType = document.getElementById('transform-type').value;
    
    applyTransformBtn.disabled = true;
    transformMsg.textContent = '⏳ Applying...';
    transformMsg.style.color = 'var(--text-muted)';
    
    try {
        const res = await fetch(`${API_BASE}/transform`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'session-id': sessionId
            },
            body: JSON.stringify({ session_id: sessionId, column: col, transform_type: transType })
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Transformation failed");
        
        // Refresh dashboard with new data
        populateDashboard(data);
        
        transformMsg.textContent = `✅ ${data.message}`;
        transformMsg.style.color = 'var(--success)';
        
    } catch (err) {
        transformMsg.textContent = `❌ ${err.message}`;
        transformMsg.style.color = 'var(--danger)';
    } finally {
        applyTransformBtn.disabled = false;
        setTimeout(() => { transformMsg.textContent = ''; }, 5000);
    }
});

// Demo Data Generator
demoBtn.addEventListener('click', async () => {
    uploadStatus.classList.remove('hidden');
    uploadStatus.style.color = 'var(--accent)';
    uploadStatus.textContent = 'Generating 1,000 row TCS Synthetic Dataset...';
    
    try {
        const res = await fetch(`${API_BASE}/synthetic`);
        if (!res.ok) throw new Error(await res.text());
        
        const blob = await res.blob();
        const file = new File([blob], "tcs_demo_data.csv", { type: "text/csv" });
        
        uploadStatus.textContent = 'Dataset created! Uploading to pipeline...';
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('context', "This is a synthetic dataset generated for demo purposes. It contains sales and customer data. We want to find patterns.");
        
        processUpload(formData);
    } catch (err) {
        uploadStatus.textContent = `Error: ${err.message}`;
        uploadStatus.style.color = 'var(--danger)';
    }
});

// Custom API calls
const chartTypeSelect = document.getElementById('chart-type');
const regToggleContainer = document.getElementById('reg-toggle-container');

// Only show regression option for scatter plots
chartTypeSelect.addEventListener('change', () => {
    if (chartTypeSelect.value === 'scatter') {
        regToggleContainer.style.display = 'flex';
    } else {
        regToggleContainer.style.display = 'none';
        document.getElementById('scatter-reg').checked = false;
    }
});

const plotChartBtn = document.getElementById('plot-chart-btn');
plotChartBtn.addEventListener('click', async () => {
    scatterOutput.innerHTML = '<i>Generating chart...</i>';
    try {
        const res = await fetch(`${API_BASE}/chart`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'session-id': sessionId
            },
            body: JSON.stringify({
                session_id: sessionId,
                x: scatterX.value,
                y: scatterY.value,
                hue: scatterHue.value,
                chart_type: chartTypeSelect.value,
                reg: document.getElementById('scatter-reg').checked
            })
        });
        const data = await res.json();
        if(res.ok) {
            scatterOutput.innerHTML = `<img src="data:image/png;base64,${data.image}" style="max-width:100%; border-radius:8px;">`;
        } else {
            scatterOutput.innerHTML = `<span style="color:var(--danger)">${data.detail}</span>`;
        }
    } catch (e) {
        scatterOutput.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
    }
});

runPcaBtn.addEventListener('click', async () => {
    pcaOutput.innerHTML = '<i>Running PCA Dimensionality Reduction...</i>';
    pcaMsg.textContent = '';
    try {
        const res = await fetch(`${API_BASE}/pca`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'session-id': sessionId
            },
            body: JSON.stringify({ session_id: sessionId, hue: pcaHue.value })
        });
        const data = await res.json();
        if(res.ok) {
            pcaOutput.innerHTML = `<img src="data:image/png;base64,${data.image}" style="max-width:100%; border-radius:8px;">`;
            pcaMsg.style.color = "var(--success)";
            pcaMsg.textContent = data.message;
        } else {
            pcaMsg.style.color = "var(--danger)";
            pcaMsg.textContent = data.detail;
            pcaOutput.innerHTML = '';
        }
    } catch (e) {
        pcaMsg.style.color = "var(--danger)";
        pcaMsg.textContent = `Error: ${e.message}`;
        pcaOutput.innerHTML = '';
    }
});

// AutoML Logic
document.getElementById('generate-automl-btn').addEventListener('click', async () => {
    const target = document.getElementById('automl-target').value;
    const mtype = document.getElementById('automl-type').value;
    const msg = document.getElementById('automl-msg');
    
    msg.style.color = "var(--text-main)";
    msg.textContent = "Generating Model Script...";
    
    try {
        const res = await fetch(`${API_BASE}/automl`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'session-id': sessionId
            },
            body: JSON.stringify({ session_id: sessionId, target_column: target, model_type: mtype })
        });
        
        if (res.ok) {
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `train_model_${target}.py`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            msg.style.color = "var(--success)";
            msg.textContent = "Script downloaded successfully!";
        } else {
            const data = await res.json();
            msg.style.color = "var(--danger)";
            msg.textContent = data.detail || "Generation failed";
        }
    } catch (e) {
        msg.style.color = "var(--danger)";
        msg.textContent = `Error: ${e.message}`;
    }
});

// PDF Export
document.getElementById('export-pdf-btn').addEventListener('click', () => {
    window.print();
});

// ============================================================
// ⚡ SPARK OPERATIONS
// ============================================================

// Helper: render a list of dicts as an HTML table
function renderSparkTable(rows) {
    if (!rows || rows.length === 0) return '<p style="color:var(--text-muted)">No results.</p>';
    const cols = Object.keys(rows[0]);
    let html = '<table><thead><tr>';
    cols.forEach(c => html += `<th>${c}</th>`);
    html += '</tr></thead><tbody>';
    rows.forEach(row => {
        html += '<tr>';
        cols.forEach(c => html += `<td>${row[c] !== null ? row[c] : 'null'}</td>`);
        html += '</tr>';
    });
    html += '</tbody></table>';
    return html;
}

// Check Spark status on dashboard load
async function checkSparkStatus() {
    try {
        const res = await fetch(`${API_BASE}/spark/status`);
        const data = await res.json();
        const banner = document.getElementById('spark-status-banner');
        const text = document.getElementById('spark-status-text');
        if (data.available) {
            banner.style.borderLeft = '4px solid var(--success)';
            text.innerHTML = '✅ PySpark is available and ready to use.';
            text.style.color = 'var(--success)';
        } else {
            banner.style.borderLeft = '4px solid var(--warning)';
            text.innerHTML = '⚠️ PySpark is not installed. Install it with <code>pip install pyspark</code> to enable these features.';
            text.style.color = 'var(--warning)';
        }
    } catch (e) {
        // Silently fail
    }
}

// Describe
document.getElementById('spark-describe-btn').addEventListener('click', async () => {
    const output = document.getElementById('spark-describe-output');
    output.innerHTML = '<i>Running Spark describe()...</i>';
    try {
        const res = await fetch(`${API_BASE}/spark/describe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'session-id': sessionId },
            body: JSON.stringify({ session_id: sessionId })
        });
        const data = await res.json();
        if (res.ok) {
            output.innerHTML = '<h4 style="margin-bottom:10px;">describe()</h4>' + renderSparkTable(data.describe) +
                '<h4 style="margin:20px 0 10px;">summary()</h4>' + renderSparkTable(data.summary);
        } else {
            output.innerHTML = `<span style="color:var(--danger)">${data.detail}</span>`;
        }
    } catch (e) {
        output.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
    }
});

// Transform
document.getElementById('spark-transform-btn').addEventListener('click', async () => {
    const col = document.getElementById('spark-transform-col').value;
    const type = document.getElementById('spark-transform-type').value;
    const msg = document.getElementById('spark-transform-msg');
    msg.textContent = 'Applying transformation via Spark...';
    msg.style.color = 'var(--text-main)';
    try {
        const res = await fetch(`${API_BASE}/spark/transform`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'session-id': sessionId },
            body: JSON.stringify({ session_id: sessionId, column: col, transform_type: type })
        });
        const data = await res.json();
        if (res.ok) {
            msg.style.color = 'var(--success)';
            msg.textContent = data.message;
        } else {
            msg.style.color = 'var(--danger)';
            msg.textContent = data.detail;
        }
    } catch (e) {
        msg.style.color = 'var(--danger)';
        msg.textContent = `Error: ${e.message}`;
    }
});

// Filter
document.getElementById('spark-filter-btn').addEventListener('click', async () => {
    const col = document.getElementById('spark-filter-col').value;
    const op = document.getElementById('spark-filter-op').value;
    const val = document.getElementById('spark-filter-value').value;
    const output = document.getElementById('spark-filter-output');
    output.innerHTML = '<i>Filtering...</i>';
    try {
        const res = await fetch(`${API_BASE}/spark/filter`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'session-id': sessionId },
            body: JSON.stringify({ session_id: sessionId, column: col, operator: op, value: val })
        });
        const data = await res.json();
        if (res.ok) {
            output.innerHTML = `<p style="color:var(--success); margin-bottom:10px;">${data.message} — ${data.row_count} rows</p>` + renderSparkTable(data.preview);
        } else {
            output.innerHTML = `<span style="color:var(--danger)">${data.detail}</span>`;
        }
    } catch (e) {
        output.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
    }
});

// GroupBy
document.getElementById('spark-groupby-btn').addEventListener('click', async () => {
    const gcol = document.getElementById('spark-group-col').value;
    const acol = document.getElementById('spark-agg-col').value;
    const afunc = document.getElementById('spark-agg-func').value;
    const output = document.getElementById('spark-groupby-output');
    output.innerHTML = '<i>Grouping...</i>';
    try {
        const res = await fetch(`${API_BASE}/spark/groupby`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'session-id': sessionId },
            body: JSON.stringify({ session_id: sessionId, group_cols: [gcol], agg_dict: { [acol]: afunc } })
        });
        const data = await res.json();
        if (res.ok) {
            output.innerHTML = `<p style="color:var(--success); margin-bottom:10px;">${data.message}</p>` + renderSparkTable(data.result);
        } else {
            output.innerHTML = `<span style="color:var(--danger)">${data.detail}</span>`;
        }
    } catch (e) {
        output.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
    }
});

// Window Functions
document.getElementById('spark-window-btn').addEventListener('click', async () => {
    const partition = document.getElementById('spark-win-partition').value;
    const order = document.getElementById('spark-win-order').value;
    const func = document.getElementById('spark-win-func').value;
    const target = document.getElementById('spark-win-target').value;
    const output = document.getElementById('spark-window-output');
    output.innerHTML = '<i>Applying window function...</i>';
    try {
        const res = await fetch(`${API_BASE}/spark/window`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'session-id': sessionId },
            body: JSON.stringify({ session_id: sessionId, partition_col: partition, order_col: order, func: func, target_col: target })
        });
        const data = await res.json();
        if (res.ok) {
            output.innerHTML = `<p style="color:var(--success); margin-bottom:10px;">${data.message}</p>` + renderSparkTable(data.result);
        } else {
            output.innerHTML = `<span style="color:var(--danger)">${data.detail}</span>`;
        }
    } catch (e) {
        output.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
    }
});

// Sort
document.getElementById('spark-sort-btn').addEventListener('click', async () => {
    const col = document.getElementById('spark-sort-col').value;
    const dir = document.getElementById('spark-sort-dir').value;
    const output = document.getElementById('spark-sort-output');
    output.innerHTML = '<i>Sorting...</i>';
    try {
        const res = await fetch(`${API_BASE}/spark/sort`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'session-id': sessionId },
            body: JSON.stringify({ session_id: sessionId, column: col, ascending: dir === 'asc' })
        });
        const data = await res.json();
        if (res.ok) {
            output.innerHTML = `<p style="color:var(--success); margin-bottom:10px;">${data.message}</p>` + renderSparkTable(data.result);
        } else {
            output.innerHTML = `<span style="color:var(--danger)">${data.detail}</span>`;
        }
    } catch (e) {
        output.innerHTML = `<span style="color:var(--danger)">Error: ${e.message}</span>`;
    }
});

// Chat logic
async function streamInitialReport() {
    chatHistory.innerHTML = '<div class="message ai-message" id="initial-report"><i>Analyzing dataset...</i></div>';
    
    currentAbtController = new AbortController();
    document.getElementById('stop-chat-btn').classList.remove('hidden');
    
    try {
        const response = await fetch(`${API_BASE}/ai/report`, {
            headers: { 'session-id': sessionId },
            signal: currentAbtController.signal
        });
        if(!response.ok) throw new Error("Failed to get report.");
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let reportText = "";
        
        const reportDiv = document.getElementById('initial-report');
        reportDiv.innerHTML = '';
        
        while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            reportText += decoder.decode(value);
            reportDiv.innerHTML = renderMarkdown(reportText);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
        
        currentChatHistory.push({"role": "assistant", "content": reportText});
        
    } catch(e) {
        if (e.name === 'AbortError') {
            document.getElementById('initial-report').innerHTML += `\n\n<i>[Stopped by User]</i>`;
        } else {
            document.getElementById('initial-report').innerHTML = `<i>Error: ${e.message}</i>`;
        }
    } finally {
        document.getElementById('stop-chat-btn').classList.add('hidden');
        currentAbtController = null;
    }
}

async function sendChatMessage() {
    const message = chatInput.value.trim();
    if (!message) return;
    const userDiv = document.createElement('div');
    userDiv.className = 'message user-message';
    userDiv.textContent = message;
    chatHistory.appendChild(userDiv);
    chatInput.value = '';
    const aiDiv = document.createElement('div');
    aiDiv.className = 'message ai-message';
    aiDiv.innerHTML = '<i>Thinking...</i>';
    chatHistory.appendChild(aiDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    try {
        currentAbtController = new AbortController();
        document.getElementById('stop-chat-btn').classList.remove('hidden');
        
        const response = await fetch(`${API_BASE}/ai/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'session-id': sessionId
            },
            body: JSON.stringify({ message: message, history: currentChatHistory, session_id: sessionId }),
            signal: currentAbtController.signal
        });
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let aiText = "";
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            aiText += chunk;
            aiDiv.innerHTML = renderMarkdown(aiText);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
        currentChatHistory.push({"role": "user", "content": message});
        currentChatHistory.push({"role": "assistant", "content": aiText});
    } catch (err) {
        if (err.name === 'AbortError') {
            aiDiv.innerHTML += `\n\n<i>[Stopped by User]</i>`;
        } else {
            aiDiv.innerHTML = `<span style="color:red">Error: ${err.message}</span>`;
        }
    } finally {
        document.getElementById('stop-chat-btn').classList.add('hidden');
        currentAbtController = null;
    }
}

document.getElementById('stop-chat-btn').addEventListener('click', () => {
    if (currentAbtController) {
        currentAbtController.abort();
    }
});

sendChatBtn.addEventListener('click', sendChatMessage);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
    }
});

newDatasetBtn.addEventListener('click', () => { location.reload(); });
