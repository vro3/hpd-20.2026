// MIDI panel client — device pickers, SSE event stream, pad pulse on the
// skin, note remap table, kit-change sender, recorder control.

(function () {
    "use strict";

    const panel = document.getElementById("midi-panel");
    if (!panel) return;  // no MIDI panel on this page (e.g. no_backup)

    const openBtn = document.getElementById("midi-open");
    const closeBtn = document.getElementById("midi-close");
    const inputSel = document.getElementById("midi-input");
    const outputSel = document.getElementById("midi-output");
    const connectBtn = document.getElementById("midi-connect-btn");
    const disconnectBtn = document.getElementById("midi-disconnect-btn");
    const refreshBtn = document.getElementById("midi-refresh-btn");
    const status = document.getElementById("midi-status");
    const sendKitBtn = document.getElementById("midi-send-kit-btn");
    const remapForm = document.getElementById("midi-remap-form");
    const remapList = document.getElementById("midi-remap-list");
    const remapSrc = document.getElementById("midi-remap-src");
    const remapDst = document.getElementById("midi-remap-dst");
    const recordBtn = document.getElementById("midi-record-btn");
    const recordName = document.getElementById("midi-record-name");
    const recordStatus = document.getElementById("midi-record-status");
    const activity = document.getElementById("midi-activity");

    const layout = document.getElementById("kit-layout");
    const kitIndex = layout ? parseInt(layout.dataset.kitIndex, 10) : 0;
    let noteToSlot = {};
    let recording = false;
    let eventSource = null;

    // ---------- UI open / close ----------

    function openPanel() { panel.hidden = false; refreshDevices(); refreshRemap(); startEventStream(); loadPadLookup(); }
    function closePanel() { panel.hidden = true; stopEventStream(); }

    if (openBtn) openBtn.addEventListener("click", openPanel);
    if (closeBtn) closeBtn.addEventListener("click", closePanel);

    // ---------- Device pickers ----------

    function refreshDevices() {
        fetch("/api/midi/devices").then(r => r.json()).then(d => {
            fillSelect(inputSel, d.inputs || []);
            fillSelect(outputSel, d.outputs || []);
            refreshStatus();
        }).catch(err => setStatus("error listing devices: " + err));
    }

    function fillSelect(select, names) {
        const prev = select.value;
        select.innerHTML = '<option value="">(none)</option>';
        names.forEach(n => {
            const opt = document.createElement("option");
            opt.value = n;
            opt.textContent = n;
            select.appendChild(opt);
        });
        if (names.includes(prev)) select.value = prev;
    }

    function refreshStatus() {
        fetch("/api/midi/status").then(r => r.json()).then(s => {
            if (s.input || s.output) {
                setStatus(`in: ${s.input || "—"}  ·  out: ${s.output || "—"}`);
            } else {
                setStatus("disconnected");
            }
            if (s.input) inputSel.value = s.input;
            if (s.output) outputSel.value = s.output;
            renderRemap(s.remap || {});
            recording = !!s.recording;
            updateRecordUI(s.recording_event_count || 0);
        });
    }

    function setStatus(text) { status.textContent = text; }

    connectBtn.addEventListener("click", () => {
        const form = new FormData();
        form.append("input_name", inputSel.value);
        form.append("output_name", outputSel.value);
        fetch("/api/midi/connect", { method: "POST", body: form })
            .then(r => r.json()).then(refreshStatus)
            .catch(err => setStatus("connect failed: " + err));
    });
    disconnectBtn.addEventListener("click", () => {
        fetch("/api/midi/disconnect", { method: "POST" }).then(refreshStatus);
    });
    refreshBtn.addEventListener("click", refreshDevices);

    // ---------- Kit change via Program Change ----------

    if (sendKitBtn) sendKitBtn.addEventListener("click", () => {
        fetch(`/api/midi/kit-change/${kitIndex}`, { method: "POST" })
            .then(r => r.json())
            .then(d => setStatus(`sent kit change → ${d.kit + 1}`))
            .catch(err => setStatus("kit change failed: " + err));
    });

    // ---------- Remap table ----------

    function refreshRemap() {
        fetch("/api/midi/remap").then(r => r.json()).then(d => renderRemap(d.remap || {}));
    }

    function renderRemap(remap) {
        remapList.innerHTML = "";
        const entries = Object.entries(remap);
        if (entries.length === 0) {
            remapList.innerHTML = '<li class="midi-empty">no remap rules</li>';
            return;
        }
        entries.forEach(([src, dst]) => {
            const li = document.createElement("li");
            li.innerHTML = `<span class="remap-pair">${src} → ${dst}</span>`;
            const btn = document.createElement("button");
            btn.textContent = "remove";
            btn.type = "button";
            btn.addEventListener("click", () => {
                fetch(`/api/midi/remap/${src}`, { method: "DELETE" })
                    .then(r => r.json()).then(d => renderRemap(d.remap));
            });
            li.appendChild(btn);
            remapList.appendChild(li);
        });
    }

    if (remapForm) remapForm.addEventListener("submit", e => {
        e.preventDefault();
        const src = parseInt(remapSrc.value, 10);
        const dst = parseInt(remapDst.value, 10);
        if (isNaN(src) || isNaN(dst)) return;
        const form = new FormData();
        form.append("src", src);
        form.append("dst", dst);
        fetch("/api/midi/remap", { method: "POST", body: form })
            .then(r => r.json()).then(d => {
                renderRemap(d.remap);
                remapSrc.value = ""; remapDst.value = "";
            });
    });

    // ---------- Recorder ----------

    recordBtn.addEventListener("click", () => {
        if (!recording) {
            fetch("/api/midi/record/start", { method: "POST" }).then(() => {
                recording = true;
                updateRecordUI(0);
                recordStatus.textContent = "recording…";
            });
        } else {
            const form = new FormData();
            form.append("name", recordName.value);
            fetch("/api/midi/record/stop", { method: "POST", body: form })
                .then(r => r.json()).then(d => {
                    recording = false;
                    updateRecordUI(0);
                    recordStatus.textContent = d.saved_to
                        ? `saved ${d.event_count} events → ${d.saved_to}`
                        : `stopped (${d.event_count} events, not saved)`;
                });
        }
    });

    function updateRecordUI(count) {
        recordBtn.textContent = recording ? `■ Stop (${count})` : "● Record";
        recordBtn.classList.toggle("recording", recording);
    }

    // ---------- SSE event stream + pad pulse ----------

    function startEventStream() {
        if (eventSource) return;
        eventSource = new EventSource("/api/midi/events");
        eventSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                onMidiEvent(data);
            } catch (err) {}
        };
        eventSource.onerror = () => {
            setStatus("event stream error — retrying…");
        };
    }
    function stopEventStream() {
        if (eventSource) { eventSource.close(); eventSource = null; }
    }

    function onMidiEvent(ev) {
        if (ev.type === "note_on" && ev.velocity > 0) {
            pulsePadForNote(ev.note);
            addActivity(`♪ note ${ev.note} vel ${ev.velocity}`);
            if (recording) {
                // Update counter via polling-free re-read of status; minimal effort
                updateRecordUI((parseInt((recordBtn.textContent.match(/\d+/)||[0])[0],10)||0) + 1);
            }
        } else if (ev.type === "note_off" || (ev.type === "note_on" && ev.velocity === 0)) {
            unpulsePadForNote(ev.note);
        } else if (ev.type === "program_change") {
            addActivity(`PC ${ev.program}`);
        } else if (ev.type === "status") {
            if (ev.message) addActivity(ev.message);
        }
    }

    function pulsePadForNote(note) {
        const slot = noteToSlot[note];
        if (slot === undefined) return;
        const link = document.querySelector(`.hpd-skin a[data-pad-slot="${slot}"] .pad`);
        if (link) link.classList.add("pulse");
    }
    function unpulsePadForNote(note) {
        const slot = noteToSlot[note];
        if (slot === undefined) return;
        const link = document.querySelector(`.hpd-skin a[data-pad-slot="${slot}"] .pad`);
        if (link) link.classList.remove("pulse");
    }

    function addActivity(text) {
        const li = document.createElement("li");
        const ts = new Date().toLocaleTimeString();
        li.textContent = `${ts}  ${text}`;
        activity.prepend(li);
        while (activity.children.length > 30) activity.lastChild.remove();
    }

    // ---------- pad lookup for current kit ----------

    function loadPadLookup() {
        if (!layout) return;
        fetch(`/api/midi/pad-lookup/${kitIndex}`).then(r => r.json()).then(d => {
            noteToSlot = d.note_to_slot || {};
        });
    }

    // ---------- Play buttons (SVG skin + slot-chooser chips) ----------
    //
    // Capture-phase listener intercepts clicks on any element with
    // [data-pad-slot] inside a .play-btn or .chip-play, POSTs to
    // /api/midi/play/{kit}/{slot}, and swallows the event so the <a>
    // navigation doesn't fire and HTMX doesn't swap the editor.
    document.addEventListener("click", (evt) => {
        const skinBtn = evt.target.closest(".play-btn");
        const chipBtn = evt.target.closest(".chip-play");
        const btn = skinBtn || chipBtn;
        if (!btn) return;
        evt.preventDefault();
        evt.stopPropagation();
        const slot = btn.dataset.padSlot;
        const kit = btn.dataset.kitIndex || kitIndex;
        btn.classList.add("firing");
        fetch(`/api/midi/play/${kit}/${slot}`, { method: "POST" })
            .then(r => {
                if (!r.ok) return r.json().then(d => { throw new Error(d.detail || r.statusText); });
                return r.json();
            })
            .catch(err => {
                // No MIDI output connected, or bad note. Surface briefly in status bar.
                if (status) setStatus("play failed: " + err.message);
            })
            .finally(() => {
                setTimeout(() => btn.classList.remove("firing"), 180);
            });
    }, true);
})();
