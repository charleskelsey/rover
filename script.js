document.addEventListener("DOMContentLoaded", () => {
  const API_URL = "http://localhost:8000";
  let currentMap = [];
  let currentRovers = [];
  let currentMines = [];
  let selectedRoverId = null;
  let selectedMineId = null;
  let webSocket = null;
  let mapWidth = 10;
  let mapHeight = 10;

  // --- DOM Elements ---
  const mapGrid = document.getElementById("map-grid");
  const mapWidthInput = document.getElementById("map-width");
  const mapHeightInput = document.getElementById("map-height");
  const btnUpdateMap = document.getElementById("btn-update-map");
  const statusLog = document.getElementById("status-log");
  const roversListDiv = document.getElementById("rovers-list");
  const minesListDiv = document.getElementById("mines-list");
  const roverCommandsInput = document.getElementById("rover-commands");
  const btnCreateRover = document.getElementById("btn-create-rover");
  const mineXInput = document.getElementById("mine-x");
  const mineYInput = document.getElementById("mine-y");
  const mineSerialInput = document.getElementById("mine-serial");
  const btnCreateMine = document.getElementById("btn-create-mine");
  const selectedRoverIdSpan = document.getElementById("selected-rover-id");
  const selectedRoverStatusSpan = document.getElementById(
    "selected-rover-status"
  );
  const selectedRoverPositionSpan = document.getElementById(
    "selected-rover-position"
  );
  const selectedRoverControlsDiv = document.getElementById(
    "selected-rover-controls"
  );
  const btnDispatchRover = document.getElementById("btn-dispatch-rover");
  const btnDeleteRover = document.getElementById("btn-delete-rover");
  const selectedMineIdSpan = document.getElementById("selected-mine-id");
  const selectedMinePositionSpan = document.getElementById(
    "selected-mine-position"
  );
  const selectedMineSerialSpan = document.getElementById(
    "selected-mine-serial"
  );
  const selectedMineControlsDiv = document.getElementById(
    "selected-mine-controls"
  );
  const btnDeleteMine = document.getElementById("btn-delete-mine");
  const tabs = document.querySelectorAll(".tab");
  const tabContents = document.querySelectorAll(".tab-content");
  const realtimeRoverSelect = document.getElementById("realtime-rover-select");
  const realtimeControlPanel = document.getElementById(
    "realtime-control-panel"
  );
  const btnConnectWs = document.getElementById("btn-connect-ws");
  const btnDisconnectWs = document.getElementById("btn-disconnect-ws");
  const realtimeButtonsDiv = document.getElementById("realtime-buttons");
  const realtimeLog = document.getElementById("realtime-log");
  const btnUpdateMine = document.getElementById("btn-update-mine");
  const updateMineFormDiv = document.getElementById("update-mine-form");
  const updateMineIdLabel = document.getElementById("update-mine-id-label");
  const updateMineXInput = document.getElementById("update-mine-x");
  const updateMineYInput = document.getElementById("update-mine-y");
  const updateMineSerialInput = document.getElementById("update-mine-serial");
  const btnSaveMine = document.getElementById("btn-save-mine");
  const btnCancelUpdateMine = document.getElementById("btn-cancel-update-mine");
  const btnWsL = document.getElementById("btn-ws-l");
  const btnWsR = document.getElementById("btn-ws-r");
  const btnWsM = document.getElementById("btn-ws-m");
  const btnWsD = document.getElementById("btn-ws-d");

  // --- Logging ---
  function logStatus(message, type = "info") {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = document.createElement("div");
    logEntry.textContent = `[${timestamp}] ${message}`;
    if (type === "error") logEntry.style.color = "red";
    if (type === "success") logEntry.style.color = "green";
    statusLog.appendChild(logEntry);
    statusLog.scrollTop = statusLog.scrollHeight; // Scroll to bottom
  }

  function logRealtime(message, type = "info") {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = document.createElement("div");
    logEntry.textContent = `[${timestamp}] ${message}`;
    if (type === "error") logEntry.style.color = "red";
    if (type === "sent") logEntry.style.color = "blue";
    if (type === "received") logEntry.style.color = "purple";
    realtimeLog.appendChild(logEntry);
    realtimeLog.scrollTop = realtimeLog.scrollHeight;
  }

  // --- API Helper ---
  async function fetchAPI(endpoint, options = {}) {
    try {
      const response = await fetch(`${API_URL}${endpoint}`, options);
      if (!response.ok) {
        let errorMsg = `HTTP error ${response.status}`;
        try {
          const errorData = await response.json();
          errorMsg += `: ${errorData.detail || JSON.stringify(errorData)}`;
        } catch (e) {
          errorMsg += `: ${await response.text()}`;
        }
        throw new Error(errorMsg);
      }
      // Handle 204 No Content specifically
      if (response.status === 204) {
        return null; // Or return true, or an empty object, depending on context
      }
      return await response.json();
    } catch (error) {
      logStatus(`API Error: ${error.message}`, "error");
      console.error("API Error:", error);
      throw error; // Re-throw to allow calling function to handle
    }
  }

  // --- Map Functions ---
  async function fetchMap() {
    try {
      logStatus("Fetching map...");
      currentMap = await fetchAPI("/map");
      if (currentMap && currentMap.length > 0) {
        mapHeight = currentMap.length;
        mapWidth = currentMap[0].length;
        mapHeightInput.value = mapHeight;
        mapWidthInput.value = mapWidth;
        renderMap();
        logStatus("Map loaded successfully.", "success");
      } else {
        logStatus("Received empty map data.", "error");
        mapGrid.innerHTML = "Failed to load map.";
      }
    } catch (error) {
      mapGrid.innerHTML = "Failed to load map.";
      // Error already logged by fetchAPI
    }
  }

  function renderMap() {
    mapGrid.innerHTML = ""; // Clear previous grid
    mapGrid.style.gridTemplateColumns = `repeat(${mapWidth}, 1fr)`;
    mapGrid.style.gridTemplateRows = `repeat(${mapHeight}, 1fr)`;

    // Helper to get arrow character based on direction
    const getRoverArrow = (facing) => {
      switch (facing) {
        case "N":
          return "↑"; // Up arrow
        case "E":
          return "→"; // Right arrow
        case "S":
          return "↓"; // Down arrow
        case "W":
          return "←"; // Left arrow
        default:
          return "?"; // Unknown
      }
    };

    // Create grid cells
    for (let y = 0; y < mapHeight; y++) {
      for (let x = 0; x < mapWidth; x++) {
        const cell = document.createElement("div");
        cell.classList.add("grid-cell");
        cell.dataset.x = x;
        cell.dataset.y = y;

        // Check for mines at this location
        const mine = currentMines.find((m) => m.x === x && m.y === y);
        // Check for rovers at this location
        const rover = currentRovers.find(
          (r) => r.position && r.position.x === x && r.position.y === y
        );

        if (rover) {
          // Prioritize showing rover if both rover and mine are on the same cell
          cell.classList.add("cell-rover");

          // Create text container for rover ID
          const roverIdSpan = document.createElement("span");
          roverIdSpan.classList.add("rover-id");
          roverIdSpan.textContent = rover.id;
          cell.appendChild(roverIdSpan);

          // Add direction indicator using CSS classes
          if (rover.position && rover.position.facing) {
            const directionIndicator = document.createElement("span");
            directionIndicator.className = `rover-direction rover-direction-${rover.position.facing}`;
            cell.appendChild(directionIndicator);
          }

          cell.title = `Rover ID: ${rover.id}, Status: ${rover.status}, Facing: ${rover.position.facing}`;

          if (mine) {
            // If a mine is also here, indicate it in the title or visually
            cell.title += ` (On Mine ID: ${mine.id})`;
            // Optionally, add a subtle visual cue for rover on mine
            cell.style.border = "2px dotted var(--mine)"; // Example
          }
        } else if (mine) {
          cell.classList.add("cell-mine");
          cell.title = `Mine ID: ${mine.id}, Serial: ${mine.serial_number}`;
          cell.textContent = "M"; // Indicate mine
        } else {
          cell.textContent = "."; // Empty
        }
        mapGrid.appendChild(cell);
      }
    }

    // Highlight selected rover if any
    if (selectedRoverId) {
      const selectedRover = currentRovers.find((r) => r.id === selectedRoverId);
      if (selectedRover && selectedRover.position) {
        const selectedCell = document.querySelector(
          `.grid-cell[data-x="${selectedRover.position.x}"][data-y="${selectedRover.position.y}"]`
        );
        if (selectedCell) {
          selectedCell.classList.add("pulse");
        }
      }
    }
  }

  async function updateMapSize() {
    const newWidth = parseInt(mapWidthInput.value);
    const newHeight = parseInt(mapHeightInput.value);
    if (
      isNaN(newWidth) ||
      isNaN(newHeight) ||
      newWidth <= 0 ||
      newHeight <= 0
    ) {
      logStatus("Invalid map dimensions.", "error");
      return;
    }
    try {
      logStatus(`Updating map size to ${newWidth}x${newHeight}...`);
      await fetchAPI("/map", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ width: newWidth, height: newHeight }),
      });
      logStatus("Map size updated.", "success");
      await fetchMap(); // Re-fetch and render the map
      await fetchMines(); // Mines might have been removed if outside new bounds
      await fetchRovers(); // Rovers might reset or need re-evaluation
    } catch (error) {
      logStatus("Failed to update map size.", "error");
    }
  }

  // --- Rover Functions ---
  async function fetchRovers() {
    try {
      logStatus("Fetching rovers...");
      currentRovers = await fetchAPI("/rovers");
      renderRoversList();
      updateRealtimeRoverSelect();
      logStatus("Rovers loaded.", "success");
      renderMap(); // Update map in case rover positions changed
    } catch (error) {
      roversListDiv.innerHTML = "Failed to load rovers.";
      // Error logged by fetchAPI
    }
  }

  function renderRoversList() {
    roversListDiv.innerHTML = "";
    if (currentRovers.length === 0) {
      roversListDiv.innerHTML = "No rovers created yet.";
      return;
    }
    currentRovers.forEach((rover) => {
      const div = document.createElement("div");
      div.classList.add("list-item");
      div.textContent = `ID: ${rover.id}, Status: ${rover.status}`;
      div.dataset.roverId = rover.id;
      if (rover.id === selectedRoverId) {
        div.classList.add("selected");
      }
      div.addEventListener("click", () => selectRover(rover.id));
      roversListDiv.appendChild(div);
    });
  }

  function selectRover(roverId) {
    selectedRoverId = roverId;
    const rover = currentRovers.find((r) => r.id === roverId);

    // Update selection highlight
    document.querySelectorAll("#rovers-list .list-item").forEach((item) => {
      item.classList.toggle(
        "selected",
        parseInt(item.dataset.roverId) === roverId
      );
    });

    if (rover) {
      selectedRoverIdSpan.textContent = rover.id;
      selectedRoverStatusSpan.textContent = rover.status;
      selectedRoverPositionSpan.textContent = rover.position
        ? `(${rover.position.x}, ${rover.position.y}) Facing ${rover.position.facing}`
        : "N/A";
      selectedRoverControlsDiv.classList.remove("hidden");
      // Enable/disable controls based on status
      btnDispatchRover.disabled = !(
        rover.status === "Not Started" || rover.status === "Finished"
      );
    } else {
      selectedRoverIdSpan.textContent = "None";
      selectedRoverStatusSpan.textContent = "N/A";
      selectedRoverPositionSpan.textContent = "N/A";
      selectedRoverControlsDiv.classList.add("hidden");
    }
    renderMap(); // Update map to highlight selected rover potentially
  }

  // --- Real-time Functions ---
  function updateRealtimeRoverSelect() {
    const currentVal = realtimeRoverSelect.value;
    realtimeRoverSelect.innerHTML =
      '<option value="">-- Select a Rover --</option>';
    currentRovers.forEach((rover) => {
      // Allow selection if rover is Not Started, Finished,
      // or even MOVING (if we want to take over a dispatched rover)
      // but NOT if ELIMINATED
      if (rover.status !== "Eliminated") {
        const option = document.createElement("option");
        option.value = rover.id;
        option.textContent = `Rover ${rover.id} (${rover.status} at ${rover.position.x},${rover.position.y} ${rover.position.facing})`;
        realtimeRoverSelect.appendChild(option);
      }
    });
    if (realtimeRoverSelect.querySelector(`option[value="${currentVal}"]`)) {
      realtimeRoverSelect.value = currentVal;
      realtimeControlPanel.classList.remove("hidden");
    } else {
      realtimeControlPanel.classList.add("hidden");
    }
  }

  async function createNewRover() {
    const commands = roverCommandsInput.value.trim().toUpperCase();
    if (!commands) {
      logStatus("Rover commands cannot be empty.", "error");
      return;
    }
    if (!/^[LRMD]*$/.test(commands)) {
      logStatus(
        "Invalid characters in commands. Only L, R, M, D allowed.",
        "error"
      );
      return;
    }

    try {
      logStatus("Creating rover...");
      await fetchAPI("/rovers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ commands: commands }),
      });
      logStatus("Rover created.", "success");
      roverCommandsInput.value = ""; // Clear input
      await fetchRovers(); // Refresh list
    } catch (error) {
      logStatus("Failed to create rover.", "error");
    }
  }

  async function dispatchSelectedRover() {
    if (!selectedRoverId) return;
    try {
      logStatus(`Dispatching rover ${selectedRoverId}...`);
      const result = await fetchAPI(`/rovers/${selectedRoverId}/dispatch`, {
        method: "POST",
      });
      logStatus(
        `Rover ${selectedRoverId} finished dispatch. Status: ${result.status}`,
        "success"
      );
      await fetchRovers(); // Refresh rover status and list
      selectRover(selectedRoverId); // Re-select to update details panel
    } catch (error) {
      logStatus(`Failed to dispatch rover ${selectedRoverId}.`, "error");
      await fetchRovers(); // Fetch again in case status changed to ELIMINATED server-side
      selectRover(selectedRoverId);
    }
  }

  async function deleteSelectedRover() {
    if (
      !selectedRoverId ||
      !confirm(`Are you sure you want to delete rover ${selectedRoverId}?`)
    )
      return;
    try {
      logStatus(`Deleting rover ${selectedRoverId}...`);
      await fetchAPI(`/rovers/${selectedRoverId}`, { method: "DELETE" });
      logStatus(`Rover ${selectedRoverId} deleted.`, "success");
      selectedRoverId = null; // De-select
      selectRover(null); // Update UI
      await fetchRovers(); // Refresh list
    } catch (error) {
      logStatus(`Failed to delete rover ${selectedRoverId}.`, "error");
    }
  }

  // --- Mine Functions ---
  async function fetchMines() {
    try {
      logStatus("Fetching mines...");
      currentMines = await fetchAPI("/mines");
      renderMinesList();
      logStatus("Mines loaded.", "success");
      renderMap(); // Update map with mine locations
    } catch (error) {
      minesListDiv.innerHTML = "Failed to load mines.";
      // Error logged by fetchAPI
    }
  }

  function renderMinesList() {
    minesListDiv.innerHTML = "";
    if (currentMines.length === 0) {
      minesListDiv.innerHTML = "No mines created yet.";
      return;
    }
    currentMines.forEach((mine) => {
      const div = document.createElement("div");
      div.classList.add("list-item");
      div.textContent = `ID: ${mine.id}, Pos: (${mine.x}, ${mine.y}), Serial: ${mine.serial_number}`;
      div.dataset.mineId = mine.id;
      if (mine.id === selectedMineId) {
        div.classList.add("selected");
      }
      div.addEventListener("click", () => selectMine(mine.id));
      minesListDiv.appendChild(div);
    });
  }

  function selectMine(mineId) {
    selectedMineId = mineId;
    const mine = currentMines.find((m) => m.id === mineId);

    // Update selection highlight
    document.querySelectorAll("#mines-list .list-item").forEach((item) => {
      item.classList.toggle(
        "selected",
        parseInt(item.dataset.mineId) === mineId
      );
    });

    // Hide update form when selecting a new mine
    updateMineFormDiv.classList.add("hidden");

    if (mine) {
      selectedMineIdSpan.textContent = mine.id;
      selectedMinePositionSpan.textContent = `(${mine.x}, ${mine.y})`;
      selectedMineSerialSpan.textContent = mine.serial_number;
      selectedMineControlsDiv.classList.remove("hidden");
    } else {
      selectedMineIdSpan.textContent = "None";
      selectedMinePositionSpan.textContent = "N/A";
      selectedMineSerialSpan.textContent = "N/A";
      selectedMineControlsDiv.classList.add("hidden");
    }
    renderMap(); // Potentially highlight selected mine on map
  }

  function showUpdateMineForm() {
    if (!selectedMineId) return;
    const mine = currentMines.find((m) => m.id === selectedMineId);
    if (!mine) return;

    logStatus(`Preparing update form for mine ${selectedMineId}...`);
    // Populate form with current values
    updateMineIdLabel.textContent = selectedMineId;
    updateMineXInput.value = mine.x;
    updateMineYInput.value = mine.y;
    updateMineSerialInput.value = mine.serial_number;

    // Show the form
    updateMineFormDiv.classList.remove("hidden");
  }

  function hideUpdateMineForm() {
    updateMineFormDiv.classList.add("hidden");
    // Optionally clear the form
    updateMineXInput.value = "";
    updateMineYInput.value = "";
    updateMineSerialInput.value = "";
  }

  async function saveMineUpdate() {
    if (!selectedMineId) return;

    const currentMine = currentMines.find((m) => m.id === selectedMineId);
    if (!currentMine) return; // Should not happen if selectedMineId is set

    const newXStr = updateMineXInput.value;
    const newYStr = updateMineYInput.value;
    const newSerial = updateMineSerialInput.value.trim();

    const updateData = {};

    // Include X if it's provided and different OR if Y is also provided/different
    if (newXStr !== "") {
      const newX = parseInt(newXStr);
      if (isNaN(newX) || newX < 0) {
        logStatus("Invalid value for new X coordinate.", "error");
        return;
      }
      // Only add if different from original, or if Y is also changing.
      // Simpler: Let the backend handle comparison if needed, just send valid input.
      updateData.x = newX;
    }

    // Include Y if it's provided and different OR if X is also provided/different
    if (newYStr !== "") {
      const newY = parseInt(newYStr);
      if (isNaN(newY) || newY < 0) {
        logStatus("Invalid value for new Y coordinate.", "error");
        return;
      }
      updateData.y = newY;
    }

    // Include serial if it's provided and different
    if (newSerial !== "" && newSerial !== currentMine.serial_number) {
      updateData.serial_number = newSerial;
    }

    // Check if anything is actually being updated
    if (Object.keys(updateData).length === 0) {
      logStatus("No changes detected to save.");
      hideUpdateMineForm();
      return;
    }

    try {
      logStatus(`Updating mine ${selectedMineId}...`);
      await fetchAPI(`/mines/${selectedMineId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updateData),
      });
      logStatus(`Mine ${selectedMineId} updated successfully.`, "success");
      hideUpdateMineForm();
      await fetchMines(); // Refresh list and map
      // Reselect the mine to show updated details, but fetchMines already re-renders list
      // selectMine(selectedMineId); // Might cause infinite loop if fetchMines triggers selection? Check needed.
    } catch (error) {
      logStatus(
        `Failed to update mine ${selectedMineId}: ${error.message}`,
        "error"
      );
      // Keep the form open so the user can correct errors
    }
  }

  async function createNewMine() {
    const x = parseInt(mineXInput.value);
    const y = parseInt(mineYInput.value);
    const serial = mineSerialInput.value.trim();

    if (isNaN(x) || isNaN(y) || x < 0 || y < 0) {
      logStatus("Invalid coordinates for mine.", "error");
      return;
    }
    if (!serial) {
      logStatus("Mine serial number cannot be empty.", "error");
      return;
    }
    if (x >= mapWidth || y >= mapHeight) {
      logStatus(
        `Mine coordinates (${x}, ${y}) are outside the current map bounds (${mapWidth}x${mapHeight}).`,
        "error"
      );
      return;
    }

    try {
      logStatus("Creating mine...");
      await fetchAPI("/mines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ x: x, y: y, serial_number: serial }),
      });
      logStatus("Mine created.", "success");
      mineXInput.value = ""; // Clear inputs
      mineYInput.value = "";
      mineSerialInput.value = "";
      await fetchMines(); // Refresh list and map
    } catch (error) {
      logStatus(`Failed to create mine: ${error.message}`, "error"); // More specific error
    }
  }

  async function deleteSelectedMine() {
    if (
      !selectedMineId ||
      !confirm(`Are you sure you want to delete mine ${selectedMineId}?`)
    )
      return;
    try {
      logStatus(`Deleting mine ${selectedMineId}...`);
      await fetchAPI(`/mines/${selectedMineId}`, { method: "DELETE" });
      logStatus(`Mine ${selectedMineId} deleted.`, "success");
      selectedMineId = null; // De-select
      hideUpdateMineForm(); // Hide update form if it was open
      selectMine(null); // Update UI
      await fetchMines(); // Refresh list and map
    } catch (error) {
      logStatus(`Failed to delete mine ${selectedMineId}.`, "error");
    }
  }

  // --- Real-time Functions ---
  function updateRealtimeRoverSelect() {
    const currentVal = realtimeRoverSelect.value;
    realtimeRoverSelect.innerHTML =
      '<option value="">-- Select a Rover --</option>'; // Clear and add placeholder
    currentRovers.forEach((rover) => {
      // Only allow selection if rover is Not Started or Finished
      if (rover.status === "Not Started" || rover.status === "Finished") {
        const option = document.createElement("option");
        option.value = rover.id;
        option.textContent = `Rover ${rover.id} (${rover.status})`;
        realtimeRoverSelect.appendChild(option);
      }
    });
    // Try to restore previous selection if still valid
    if (realtimeRoverSelect.querySelector(`option[value="${currentVal}"]`)) {
      realtimeRoverSelect.value = currentVal;
      realtimeControlPanel.classList.remove("hidden");
    } else {
      realtimeControlPanel.classList.add("hidden");
    }
  }

  function connectWebSocket() {
    const roverIdStr = realtimeRoverSelect.value;
    if (!roverIdStr) {
      logRealtime("Please select a rover first.", "error");
      return;
    }
    const roverId = parseInt(roverIdStr); // Ensure it's a number for lookups

    if (webSocket && webSocket.readyState === WebSocket.OPEN) {
      logRealtime("Already connected.", "error");
      return;
    }

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/${roverId}`;

    logRealtime(`Connecting to ${wsUrl}...`);
    webSocket = new WebSocket(wsUrl);

    webSocket.onopen = (event) => {
      logRealtime("WebSocket connection established.", "success");
      btnConnectWs.classList.add("hidden");
      btnDisconnectWs.classList.remove("hidden");
      realtimeButtonsDiv.classList.remove("hidden");
      realtimeRoverSelect.disabled = true;
    };

    webSocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        logRealtime(`Received: ${JSON.stringify(data)}`, "received");

        // Find the rover in our local array
        // Ensure roverId is a number for comparison if currentRovers[].id is number
        const roverIdNum = parseInt(realtimeRoverSelect.value);
        const roverToUpdate = currentRovers.find((r) => r.id === roverIdNum);

        if (data.status === "connected" && roverToUpdate) {
          roverToUpdate.position = data.position;
          roverToUpdate.status = "Moving";
          logRealtime(
            `Rover ${data.roverId} started at (${data.position.x},${data.position.y}) facing ${data.position.facing}. On Mine: ${data.onMine}`
          );
          renderMap();
          renderRoversList(); // Reflect "Moving" status in the main rover list
          if (selectedRoverId === roverIdNum) selectRover(roverIdNum);
          return;
        }

        if (roverToUpdate && data.position) {
          roverToUpdate.position = data.position;
        }
        if (roverToUpdate && data.newFacing) {
          roverToUpdate.position.facing = data.newFacing;
        }

        let shouldFetchMines = false; // Flag to fetch mines only once if needed

        if (roverToUpdate && data.status) {
          if (data.status === "eliminated") {
            roverToUpdate.status = "Eliminated";
            alert(data.message || "Rover has been eliminated!");
            disconnectWebSocket();
          } else if (data.status === "warning" && data.onMine) {
            logRealtime(data.message || "Rover is on a mine!", "warning");
          } else if (data.status === "success") {
            if (data.command === "D" && data.mineIdDisarmed) {
              logRealtime(
                `Mine ${data.mineIdDisarmed} disarmed. PIN: ${data.pin}`,
                "success"
              );
              shouldFetchMines = true; // Mark that mines need to be fetched
            }
          }
        }

        renderMap(); // Render immediately with local updates

        if (shouldFetchMines) {
          fetchMines(); // Fetch mines if a 'D' command was successful
        }

        if (selectedRoverId === roverIdNum && roverToUpdate) {
          selectedRoverStatusSpan.textContent = roverToUpdate.status;
          selectedRoverPositionSpan.textContent = roverToUpdate.position
            ? `(${roverToUpdate.position.x}, ${roverToUpdate.position.y}) Facing ${roverToUpdate.position.facing}`
            : "N/A";
        }
      } catch (e) {
        logRealtime(`Error processing message: ${e}`, "error");
        logRealtime(`Received raw non-JSON: ${event.data}`);
      }
    };

    webSocket.onclose = (event) => {
      logRealtime(
        `WebSocket connection closed. Code: ${event.code}, Reason: ${
          event.reason || "N/A"
        }`,
        event.wasClean ? "info" : "error"
      );
      webSocket = null;
      btnConnectWs.classList.remove("hidden");
      btnDisconnectWs.classList.add("hidden");
      realtimeButtonsDiv.classList.add("hidden");
      realtimeRoverSelect.disabled = false;

      // Ensure roverId is captured before fetchRovers might change things
      const closedRoverIdStr = realtimeRoverSelect.value; // Or capture it when connection starts

      // Fetch rovers again to get the final status (e.g., FINISHED) from the server.
      // This is important because the server's `finally` block updates status.
      fetchRovers().then(() => {
        // After rovers are fetched and currentRovers is updated:
        renderRoversList(); // Refresh the main rover list
        updateRealtimeRoverSelect(); // Refresh the dropdown as status/position changed

        // If the rover that was being controlled is still the "selectedRoverId"
        // in the main UI, re-select it to update its details panel.
        if (
          closedRoverIdStr &&
          selectedRoverId === parseInt(closedRoverIdStr)
        ) {
          selectRover(parseInt(closedRoverIdStr));
        }
      });
    };

    webSocket.onerror = (event) => {
      logRealtime("WebSocket error.", "error");
      console.error("WebSocket Error: ", event);
    };
  }

  function disconnectWebSocket() {
    if (webSocket) {
      logRealtime("Disconnecting...");
      webSocket.close();
    }
  }

  function sendWsCommand(command) {
    if (webSocket && webSocket.readyState === WebSocket.OPEN) {
      logRealtime(`Sending: ${command}`, "sent");
      webSocket.send(command);
    } else {
      logRealtime("WebSocket not connected.", "error");
    }
  }

  // --- Tab Switching ---
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      // Deactivate all tabs and hide all content
      tabs.forEach((t) => t.classList.remove("active"));
      tabContents.forEach((c) => c.classList.add("hidden"));

      // Activate clicked tab and show its content
      tab.classList.add("active");
      const tabId = tab.getAttribute("data-tab");
      document.getElementById(`${tabId}-tab`).classList.remove("hidden");
    });
  });

  // --- Event Listeners ---
  btnUpdateMap.addEventListener("click", updateMapSize);
  btnCreateRover.addEventListener("click", createNewRover);
  btnCreateMine.addEventListener("click", createNewMine);
  btnDispatchRover.addEventListener("click", dispatchSelectedRover);
  btnDeleteRover.addEventListener("click", deleteSelectedRover);
  btnDeleteMine.addEventListener("click", deleteSelectedMine);
  btnUpdateMine.addEventListener("click", showUpdateMineForm); // Show form on click
  btnSaveMine.addEventListener("click", saveMineUpdate); // Save changes on click
  btnCancelUpdateMine.addEventListener("click", hideUpdateMineForm); // Hide form on cancel
  realtimeRoverSelect.addEventListener("change", () => {
    if (realtimeRoverSelect.value) {
      realtimeControlPanel.classList.remove("hidden");
    } else {
      realtimeControlPanel.classList.add("hidden");
    }
    disconnectWebSocket(); // Disconnect if changing rover
  });
  btnConnectWs.addEventListener("click", connectWebSocket);
  btnDisconnectWs.addEventListener("click", disconnectWebSocket);
  btnWsL.addEventListener("click", () => sendWsCommand("L"));
  btnWsR.addEventListener("click", () => sendWsCommand("R"));
  btnWsM.addEventListener("click", () => sendWsCommand("M"));
  btnWsD.addEventListener("click", () => sendWsCommand("D"));

  // --- Initial Load ---
  async function initialize() {
    logStatus("Initializing Rover Management System...");
    await fetchMap();
    await fetchMines();
    await fetchRovers();
    logStatus("Initialization complete.");
  }

  initialize();
});
