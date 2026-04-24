// Pad swap mode: click "Swap pads", then two pads -> POST /kit/{k}/pad-swap/{a}/{b}.
// Intercepts clicks only while body.swap-mode is set; normal HTMX flow is untouched otherwise.

(function () {
    "use strict";

    const body = document.body;
    const banner = document.getElementById("swap-banner");
    const msg = banner && banner.querySelector(".swap-msg");
    const btn = document.getElementById("swap-pads-btn");
    const cancel = document.getElementById("swap-cancel");
    const kitIndex = parseInt(document.getElementById("kit-layout").dataset.kitIndex || "0", 10);

    let firstSlot = null;

    function enterMode() {
        body.classList.add("swap-mode");
        banner.hidden = false;
        msg.innerHTML = "Click <b>first</b> pad to swap…";
        firstSlot = null;
    }

    function exitMode() {
        body.classList.remove("swap-mode");
        banner.hidden = true;
        firstSlot = null;
        clearHighlight();
    }

    function clearHighlight() {
        document.querySelectorAll(".pad.swap-first").forEach(el => el.classList.remove("swap-first"));
    }

    function handlePadClick(evt) {
        if (!body.classList.contains("swap-mode")) return;  // normal mode: leave alone
        const link = evt.target.closest("a[data-pad-slot]");
        if (!link) return;
        evt.preventDefault();
        evt.stopPropagation();
        const slot = parseInt(link.dataset.padSlot, 10);
        if (firstSlot === null) {
            firstSlot = slot;
            const shape = link.querySelector(".pad");
            if (shape) shape.classList.add("swap-first");
            msg.innerHTML = "Click <b>second</b> pad…";
        } else if (slot === firstSlot) {
            // clicking same pad cancels selection
            clearHighlight();
            firstSlot = null;
            msg.innerHTML = "Click <b>first</b> pad to swap…";
        } else {
            postSwap(firstSlot, slot);
        }
    }

    function postSwap(a, b) {
        const form = new FormData();
        fetch(`/kit/${kitIndex}/pad-swap/${a}/${b}`, { method: "POST", redirect: "follow" })
            .then(r => {
                if (!r.ok) throw new Error(`swap failed: ${r.status}`);
                window.location.href = `/kit/${kitIndex}`;
            })
            .catch(err => {
                alert("Swap failed: " + err.message);
                exitMode();
            });
    }

    if (btn) btn.addEventListener("click", enterMode);
    if (cancel) cancel.addEventListener("click", exitMode);
    document.addEventListener("keydown", e => {
        if (e.key === "Escape" && body.classList.contains("swap-mode")) exitMode();
    });

    // Capture-phase listener catches pad clicks before HTMX consumes them.
    document.addEventListener("click", handlePadClick, true);
})();
