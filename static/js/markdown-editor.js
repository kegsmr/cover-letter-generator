document.addEventListener("DOMContentLoaded", function () {
    const textarea = document.getElementById("markdown-input");
    const preview = document.getElementById("markdown-preview");

    function updatePreview() {
        preview.innerHTML = marked.parse(textarea.value);
    }

    textarea.addEventListener("input", updatePreview);
    updatePreview();
});