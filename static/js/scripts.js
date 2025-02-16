function navigate(direction) {
    if (direction === -1) {
        window.history.back();
    } else {
        window.history.forward();
    }
}

// function regenerateCoverLetter() {
//     document.getElementById('feedback-popup').style.display = 'block';
// }

function submitFeedback() {
    const feedback = document.getElementById('feedback-input').value;
    // Send feedback to the server (via an API call or form submission)
    alert('Feedback submitted: ' + feedback);
    document.getElementById('feedback-popup').style.display = 'none';
}

function showLoadingOverlay(targetElementId) {
    // Get the target element to gray out
    const targetElement = document.getElementById(targetElementId);

    // Create overlay element
    const overlay = document.createElement("div");
    overlay.style.position = "absolute";
    overlay.style.top = "0";
    overlay.style.left = "0";
    overlay.style.width = "100%";
    overlay.style.height = "100%";
    overlay.style.backgroundColor = "rgba(0, 0, 0, 0.5)";
    overlay.style.display = "flex";
    overlay.style.justifyContent = "center";
    overlay.style.alignItems = "center";
    overlay.style.flexDirection = "column";
    overlay.style.zIndex = "9999";

    // Create spinner element
    const spinner = document.createElement("div");
    spinner.style.border = "4px solid #f3f3f3";
    spinner.style.borderTop = "4px solid #3498db";
    spinner.style.borderRadius = "50%";
    spinner.style.width = "50px";
    spinner.style.height = "50px";
    spinner.style.animation = "spin 2s linear infinite";

    // Append spinner to overlay
    overlay.appendChild(spinner);

    // Create loading message
    const message = document.createElement("p");
    message.textContent = "Loading, please wait...";
    message.style.marginTop = "10px";
    message.style.color = "white";
    message.style.fontSize = "18px";
    message.style.textAlign = "center";

    // Append message to overlay
    overlay.appendChild(message);

    // Append the overlay to the body
    document.body.appendChild(overlay);

    // Apply the grayed-out effect on the target element
    targetElement.style.filter = "grayscale(100%) opacity(0.6)";
    targetElement.style.pointerEvents = "none"; // Disable interaction

    // Add keyframes for spinner rotation
    const styleSheet = document.styleSheets[0];
    styleSheet.insertRule(`
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `, styleSheet.cssRules.length);

    // Return the overlay element so we can remove it later if needed
    return overlay;
}

function hideLoadingOverlay(overlay, targetElementId) {
    // Remove the overlay from the body
    document.body.removeChild(overlay);

    // Get the target element to remove the gray effect
    const targetElement = document.getElementById(targetElementId);
    targetElement.style.filter = "";
    targetElement.style.pointerEvents = ""; // Re-enable interaction
}

// Create and insert the loading screen into the document
function showLoadingScreen(defaultMessage="Getting ready...", extraMessage="") {
    document.body.innerHTML = `
        <div class="loading-container">
            <div class="spinner"></div>
            <div class="status-message">${defaultMessage}</div>
			${extraMessage}
        </div>
    `;

	setInterval(fetchStatus, 3000);
}

// Function to fetch status updates
async function fetchStatus() {
    try {
        const response = await fetch('/status');
        if (!response.ok) throw new Error('Failed to fetch status');
        const data = await response.json();
        document.querySelector('.status-message').textContent = data.status || 'Updating...';
    } catch (error) {
        document.querySelector('.status-message').textContent = 'Error fetching status';
    }
}

function onEnter(callback) {
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Enter' && document.activeElement === document.body) {
            // Call the passed-in callback function
            callback();
        }
    });
}

function onBackspace(callback) {
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Backspace' && document.activeElement === document.body) {
            // Call the passed-in callback function
            callback();
        }
    });
}

function watchInput(element) {
    // Initialize dataset.modified if not already set
    if (!element.dataset.modified) {
        element.dataset.modified = "false";
    }

    // Listen for input events to mark the content as modified
    element.addEventListener("input", function () {
        this.dataset.modified = "true";
    });

    // Listen for the beforeunload event to warn if content is modified
    window.addEventListener("beforeunload", function (event) {
        if (element.dataset.modified === "true") {
            event.preventDefault();
			// redirect("/home")
        }
    });
}

function prefetch(url) {
    var link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = url;
    document.head.appendChild(link);
}