const MATRIX_GLYPHS = "01AUGENPBX#<>/{}";
const LOADING_LINES = [
  "[BOOT] Initializing matrix channel...",
  "[NET] Opening lotto archive endpoints...",
  "[ML] Loading TensorFlow inference stack...",
  "[SCRAPE] Harvesting PowerBall AU history...",
  "[MODEL] Training neural probability grid...",
];

function resolveEndpoint(datasetKey, fallbackPath) {
  const configuredUrl = document.body?.dataset?.[datasetKey]?.trim();
  if (configuredUrl && !configuredUrl.includes("{{")) {
    return configuredUrl;
  }

  return fallbackPath;
}

function getErrorMessage(error) {
  if (!error?.message) {
    return "Unknown UI error.";
  }

  if (error.message === "Failed to fetch") {
    return "No se pudo conectar con Flask. Ejecuta la app desde app.py o gunicorn.";
  }

  return error.message;
}

function randomStream(length) {
  let output = "";

  for (let index = 0; index < length; index += 1) {
    const char = MATRIX_GLYPHS[Math.floor(Math.random() * MATRIX_GLYPHS.length)];
    output += `${char}<br>`;
  }

  return output;
}

function initMatrix() {
  document.querySelectorAll("[data-stream]").forEach((node, index) => {
    const render = () => {
      node.innerHTML = randomStream(90 + ((index * 7) % 30));
    };

    render();
    window.setInterval(render, 2800 + index * 180);
  });
}

function flashSlot(node, value) {
  node.textContent = String(value).padStart(2, "0");
  node.classList.add("flash");
  window.setTimeout(() => node.classList.remove("flash"), 850);
}

function updateNumbers(prediction) {
  if (!prediction) {
    return;
  }

  const slots = [...document.querySelectorAll("[data-ball-slot]")];
  slots.forEach((slot, index) => {
    flashSlot(slot, prediction.numbers[index]);
  });

  const powerball = document.querySelector("[data-powerball-slot]");
  flashSlot(powerball, prediction.powerball);
}

function updateState(state) {
  if (!state) {
    return;
  }

  const runtimeNode = document.querySelector("[data-runtime-state]");
  const startNode = document.querySelector("[data-last-start]");
  const endNode = document.querySelector("[data-last-end]");

  runtimeNode.textContent = state.running
    ? "RUNNING"
    : (state.last_status || "IDLE").toUpperCase();
  startNode.textContent = state.last_start || "--";
  endNode.textContent = state.last_end || "--";
}

function initTerminalModal() {
  const modal = document.getElementById("terminal-modal");
  const closeButton = document.getElementById("close-modal");
  const trigger = document.getElementById("generate-button");
  const output = document.getElementById("terminal-output");
  const statusLine = document.getElementById("terminal-status-line");
  let loadingTicker = null;

  const openModal = () => {
    modal.classList.add("modal-open");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("overflow-hidden");
  };

  const closeModal = () => {
    modal.classList.remove("modal-open");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("overflow-hidden");
  };

  const stopTicker = () => {
    if (loadingTicker) {
      window.clearInterval(loadingTicker);
      loadingTicker = null;
    }
  };

  const startTicker = () => {
    let cursor = 0;
    output.textContent = `${LOADING_LINES[0]}\n`;
    statusLine.textContent = "Generating prediction...";

    loadingTicker = window.setInterval(() => {
      cursor += 1;
      output.textContent += `${LOADING_LINES[cursor % LOADING_LINES.length]}\n`;
      output.scrollTop = output.scrollHeight;
    }, 950);
  };

  trigger.addEventListener("click", async () => {
    trigger.disabled = true;
    openModal();
    startTicker();

    try {
      const response = await fetch(resolveEndpoint("runUrl", "/api/predict"), {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
      });
      const payload = await response.json();

      stopTicker();
      output.textContent = payload.output || payload.message || "No output received.";
      statusLine.textContent = response.ok
        ? "Prediction completed."
        : (payload.message || "Execution failed.");

      updateNumbers(payload.prediction);
      updateState(payload.state);

      if (!response.ok) {
        throw new Error(payload.message || "Execution failed.");
      }
    } catch (error) {
      stopTicker();
      statusLine.textContent = "Execution failed.";
      output.textContent = `${output.textContent}\n\n[UI] ${getErrorMessage(error)}`;
    } finally {
      trigger.disabled = false;
    }
  });

  closeButton.addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeModal();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeModal();
    }
  });
}

async function syncInitialState() {
  try {
    const response = await fetch(resolveEndpoint("statusUrl", "/status"));
    const state = await response.json();
    updateState(state);
  } catch (_error) {
    // Best effort only for UI hydration.
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initMatrix();
  initTerminalModal();
  syncInitialState();
});
