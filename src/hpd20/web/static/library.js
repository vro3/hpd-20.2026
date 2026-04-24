// Instrument library: loads all sounds once, filters client-side,
// clicking a name applies it to the currently-selected pad's Layer A
// (shift-click -> Layer B). Favorite star toggles server-side.

(function () {
    "use strict";

    const search = document.getElementById("library-search");
    const favList = document.getElementById("library-fav-list");
    const allList = document.getElementById("library-all-list");
    const countEl = document.getElementById("library-count");
    const library = document.getElementById("instrument-library");
    if (!library) return;

    let items = [];          // [{id, name, favorite}]
    let favorites = new Set();

    function currentPad() {
        const el = document.getElementById("pad-editor-inner");
        return el ? { kit: parseInt(library.dataset.kitIndex, 10),
                      slot: parseInt(el.dataset.slot, 10) } : null;
    }

    function render() {
        const q = (search.value || "").trim().toLowerCase();
        favList.innerHTML = "";
        const favItems = items.filter(it => favorites.has(it.id));
        if (favItems.length === 0) {
            favList.innerHTML = '<li class="library-empty">(none yet — click ☆ to favorite)</li>';
        } else {
            favItems.forEach(it => favList.appendChild(row(it, true)));
        }
        const filtered = q ? items.filter(it => it.name.toLowerCase().includes(q)) : items;
        allList.innerHTML = "";
        filtered.slice(0, 400).forEach(it => allList.appendChild(row(it, false)));
        countEl.textContent = q ? `${filtered.length} match${filtered.length === 1 ? "" : "es"}` : `${items.length}`;
    }

    function row(it, isFav) {
        const li = document.createElement("li");
        li.className = "library-row";
        const star = document.createElement("button");
        star.type = "button";
        star.className = "star" + (favorites.has(it.id) ? " on" : "");
        star.textContent = favorites.has(it.id) ? "★" : "☆";
        star.title = favorites.has(it.id) ? "Remove favorite" : "Favorite";
        star.addEventListener("click", e => {
            e.stopPropagation();
            toggleFavorite(it.id);
        });
        const name = document.createElement("button");
        name.type = "button";
        name.className = "instr-name";
        name.textContent = it.name;
        name.title = "click → Layer A · shift-click → Layer B";
        name.addEventListener("click", e => applyInstrument(it.id, e.shiftKey ? 1 : 0));
        li.append(star, name);
        return li;
    }

    function toggleFavorite(id) {
        fetch(`/api/favorites/${id}`, { method: "POST" })
            .then(r => r.json())
            .then(d => { favorites = new Set(d.favorites); render(); });
    }

    function applyInstrument(id, layer) {
        const pad = currentPad();
        if (!pad) return;
        const form = new FormData();
        form.append("layer", layer);
        form.append("instrument_id", id);
        fetch(`/kit/${pad.kit}/pad/${pad.slot}/patch`, {
            method: "POST",
            body: form,
            headers: { "HX-Request": "true" },
        })
            .then(r => r.text())
            .then(html => {
                document.getElementById("pad-editor").innerHTML = html;
                // Rather than re-render the skin, reload the page lightly: the skin
                // shows this pad's layer-A name. If you only set layer B we can skip
                // this; simpler to always reload.
                if (layer === 0) {
                    setTimeout(() => window.location.reload(), 100);
                }
            });
    }

    function load() {
        fetch("/api/instruments")
            .then(r => r.json())
            .then(d => {
                items = d.items;
                favorites = new Set(d.favorites);
                render();
            });
    }

    search.addEventListener("input", render);
    load();
})();
