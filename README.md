# AI Cover Letter Generator

This project is a web-based application that allows users to upload their resume in PDF format, extract text from it, edit the extracted text, and generate cover letters tailored to job postings. The application is built using Flask, Playwright, pdfplumber, BeautifulSoup, and Ollama for AI-generated content.

## Features
- Upload a resume in PDF format
- Extract and edit resume text
- Input job descriptions manually or extract from URLs
- Generate AI-assisted cover letters based on resume and job description
- Store session-based resume data for easy editing

## Requirements
Ensure you have the following dependencies installed:

```
bs4
flask
ollama
pdfplumber
playwright
```

You can install them using:
```
pip install -r requirements.txt
```

## Usage

### Running the Application
1. Clone the repository:
   ```
   git clone <repository-url>
   cd <project-directory>
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Start the Flask server:
   ```
   python app.py
   ```
4. Open your browser and go to `http://127.0.0.1:5000/`

### Uploading a Resume
- Navigate to `/resume/upload`
- Upload a PDF file
- The extracted text will be stored in the session

### Editing Resume Text
- Navigate to `/resume/edit`
- Modify the extracted text as needed

### Generating a Cover Letter
- Provide a job description or URL
- The system extracts job details and generates a cover letter using AI
- Users can refine the cover letter with iterative feedback

## File Structure
```
.
├── app.py            # Flask web application
├── generator.py      # Resume parsing and cover letter generation
├── templates/        # HTML templates for web interface
├── static/           # CSS, JavaScript, and assets
├── requirements.txt  # Project dependencies
├── README.md         # Project documentation
```

## Technologies Used
- **Flask** - Web framework for handling requests
- **pdfplumber** - Extract text from PDFs
- **BeautifulSoup** - Parse and clean job postings from webpages
- **Playwright** - Automate job posting extraction
- **Ollama** - AI-powered cover letter generation

## License
This project is licensed under the MIT License. See `LICENSE` for details.

## Contributing
Feel free to fork the repository and submit pull requests for improvements or bug fixes.