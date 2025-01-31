# AI Cover Letter Generator

## Overview

This application generates tailored cover letters based on job descriptions. It extracts relevant information from a user's resume and refines it according to the job posting.

**Note:** This project is a work-in-progress! The web app is not functional yet, but you can use the commandline utility.

## Features

- Extracts text from PDF resumes
- Parses job descriptions from URLs or user input
- Generates optimized cover letters based on past examples
- Supports iterative feedback for refinement

## Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/yourusername/cover-letter-generator.git
   cd cover-letter-generator
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

## Usage

There are two ways to use this application:

### 1. As a Flask Web App

Run the following command to start the web interface:

```sh
python app.py
```

Then, navigate to `http://127.0.0.1:5000/` in your web browser to use the application.

### 2. As a Command-Line Utility

Run the following command:

```sh
python generator.py
```

#### Example Usage

```
Job URL/description: https://www.linkedin.com/jobs/view/4076660630

**Software Engineer Jobs**
...

Feedback:
```

The command-line tool will extract job descriptions from the provided URL or allow manual input. It then generates a cover letter draft, which the user can refine with iterative feedback before saving the final version.

## File Structure

```
.
├── app.py            # Flask web application
├── generator.py      # Command-line cover letter generator
├── templates/        # HTML templates for web interface
├── static/           # CSS, JavaScript, and assets
├── requirements.txt  # Project dependencies
├── README.md         # Project documentation
```

## Technologies Used

- Python
- Flask (for web interface)
- BeautifulSoup (for parsing job posting sites)
- PyPDF2 (for parsing resumes from PDFs)
- Ollama API (for cover letter generation)

## Contributing

Contributions are welcome! Please submit a pull request or open an issue if you have suggestions.

## License

This project is licensed under the MIT-0 License.
