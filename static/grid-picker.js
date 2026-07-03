// A click-and-drag time-slot picker. Reads slot data from a <script type="application/json">
// sibling, renders one cell per slot, and (unless data-readonly="true") lets the student drag
// across contiguous free cells to pick a reservation window, updating hidden start/end/ram
// inputs in the accompanying form as the selection changes.
function initGridPicker(container) {
  const dataEl = document.getElementById(container.dataset.slotDataId);
  const slots = JSON.parse(dataEl.textContent);
  const readonly = container.dataset.readonly === "true";
  const totalRamMb = parseInt(container.dataset.totalRamMb, 10);

  const grid = document.createElement("div");
  grid.className = "grid-picker";
  slots.forEach((slot, index) => {
    const cell = document.createElement("div");
    cell.className = "grid-cell " + freeRatioClass(slot.free_mb, totalRamMb);
    cell.dataset.index = String(index);
    cell.title = `${slot.label} — ${slot.free_mb} MB free`;
    cell.textContent = slot.label;
    grid.appendChild(cell);
  });
  container.appendChild(grid);

  if (readonly) return;

  let dragStart = null;
  let dragEnd = null;

  function freeRatioClass(freeMb, totalMb) {
    const ratio = freeMb / totalMb;
    if (freeMb <= 0) return "cell-full";
    if (ratio < 0.5) return "cell-partial";
    return "cell-free";
  }

  function cellAt(index) {
    return grid.children[index];
  }

  function clearSelectionStyles() {
    Array.from(grid.children).forEach((c) => c.classList.remove("cell-selected"));
  }

  function applySelectionStyles() {
    if (dragStart === null || dragEnd === null) return;
    const [lo, hi] = [dragStart, dragEnd].sort((a, b) => a - b);
    for (let i = lo; i <= hi; i++) cellAt(i).classList.add("cell-selected");
  }

  function commitSelection() {
    if (dragStart === null || dragEnd === null) return;
    const [lo, hi] = [dragStart, dragEnd].sort((a, b) => a - b);
    const selected = slots.slice(lo, hi + 1);
    const minFree = Math.min(...selected.map((s) => s.free_mb));

    const form = container.closest("form");
    form.querySelector('[name="start"]').value = selected[0].start;
    form.querySelector('[name="end"]').value = selected[selected.length - 1].end;
    const ramInput = form.querySelector('[name="ram_mb"]');
    ramInput.max = minFree;
    if (parseInt(ramInput.value || "0", 10) > minFree) ramInput.value = String(minFree);

    const caption = form.querySelector(".selection-caption");
    if (caption) caption.textContent = `${selected[0].label}–${selected[selected.length - 1].label_end} · up to ${minFree} MB free`;

    form.querySelector('button[type="submit"]').disabled = false;
  }

  grid.addEventListener("pointerdown", (event) => {
    const cell = event.target.closest(".grid-cell");
    if (!cell || cell.classList.contains("cell-full")) return;
    dragStart = dragEnd = parseInt(cell.dataset.index, 10);
    clearSelectionStyles();
    applySelectionStyles();
    grid.setPointerCapture(event.pointerId);
  });

  grid.addEventListener("pointermove", (event) => {
    if (dragStart === null) return;
    const cell = document.elementFromPoint(event.clientX, event.clientY);
    const gridCell = cell && cell.closest(".grid-cell");
    if (!gridCell || gridCell.classList.contains("cell-full")) return;
    dragEnd = parseInt(gridCell.dataset.index, 10);
    clearSelectionStyles();
    applySelectionStyles();
  });

  grid.addEventListener("pointerup", () => {
    commitSelection();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".grid-picker-container").forEach(initGridPicker);
});
document.addEventListener("htmx:afterSwap", (event) => {
  event.target.querySelectorAll(".grid-picker-container").forEach(initGridPicker);
});
