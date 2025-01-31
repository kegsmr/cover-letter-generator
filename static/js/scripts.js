function navigate(direction) {
    if (direction === -1) {
        window.history.back();
    } else {
        window.history.forward();
    }
}

function regenerateCoverLetter() {
    document.getElementById('feedback-popup').style.display = 'block';
}

function submitFeedback() {
    const feedback = document.getElementById('feedback-input').value;
    // Send feedback to the server (via an API call or form submission)
    alert('Feedback submitted: ' + feedback);
    document.getElementById('feedback-popup').style.display = 'none';
}