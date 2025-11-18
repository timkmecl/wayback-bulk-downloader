
# Wayback Machine Bulk Downloader

![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)

A powerful and flexible CLI tool and Python module to bulk download pages from the Internet Archive's Wayback Machine.

This tool is designed for efficiency and politeness, incorporating features like concurrent downloads, rate limiting, automatic retries, and detailed logging. It can be used directly from the command line for archival tasks or imported into your own Python projects for programmatic access.



---

## Key Features

-   **Multiple Download Modes:**
    -   Download a single URL.
    -   Process a list of URLs from a text file.
    -   Use a URL template and a list of parameters to download series of related pages (e.g., articles, comics, user profiles).
-   **High Performance:** Download multiple URLs in parallel using concurrent threads.
-   **Polite & Robust:**
    -   Configurable delay between requests to avoid overwhelming servers.
    -   Automatic retries with exponential backoff when rate-limited (HTTP 429).
-   **Resume Support:** Automatically skips files that have already been downloaded, allowing you to resume interrupted jobs.
-   **Detailed Logging:** Generate a CSV log of every download attempt, including timestamps, final URLs, status, and error messages.
-   **Specific Timestamps:** Fetch the latest available version of a page or specify a precise timestamp (e.g., `20150101`) for point-in-time recovery.
-   **Dual Use:**
    -   A full-featured command-line interface (CLI) for direct use.
    -   An importable Python module (`WaybackDownloader` class) for integration into other scripts.

## Installation

The script is self-contained and requires only the `requests` library.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/wayback-bulk-downloader.git
    cd wayback-bulk-downloader
    ```

2.  **Install dependencies:**
    *(Create a `requirements.txt` file containing the single line: `requests`)*
    ```bash
    pip install -r requirements.txt
    ```

3.  **(Optional) Make the script executable:**
    ```bash
    chmod +x wayback_bulk_downloader.py
    ```

## Usage (Command-Line)

The script is flexible and can be configured with various flags.

### Basic Examples

**1. Show the help menu:**
```bash
python3 wayback_bulk_downloader.py -h
```

**2. Download the latest version of a single URL:**
```bash
python3 wayback_bulk_downloader.py --url "https://www.example.com"
```

**3. Download a list of URLs from a file:**

First, create `urls.txt`:
```
https://www.wikipedia.org
https://xkcd.com/
```

Then run the command:
```bash
python3 wayback_bulk_downloader.py --list urls.txt --output-dir my_downloads
```

### Advanced Example: Template Mode

This mode is perfect for downloading a series of pages, like webcomics with sequential IDs.

**1. Create a parameter file (`comic_ids.txt`):**
```
1
100
242
327
```

**2. Run the tool with the `--template` and `--params` flags:**
The `{}` is a placeholder for each line in your parameter file.
```bash
python3 wayback_bulk_downloader.py \
    --template "https://xkcd.com/{}/" \
    --params comic_ids.txt
```
This will create a subdirectory named `wayback_downloads/xkcd.com_` and save the files inside as `1.html`, `100.html`, etc.

### Power User Example

Download a list of URLs using 8 threads, skipping existing files, creating a detailed log, and fetching versions from the year 2018.

```bash
python3 wayback_bulk_downloader.py \
    --list urls.txt \
    --threads 8 \
    --skip-existing \
    --log progress.csv \
    --timestamp 2018 \
    -v
```

## Usage (as a Python Module)

You can import the `WaybackDownloader` class to integrate it into your own projects.

### Example 1: Download from a Python List

```python
from wayback_bulk_downloader import WaybackDownloader

# 1. Configure the downloader
downloader = WaybackDownloader(
    output_dir="my_archive",
    threads=4,
    skip_existing=True
)

# 2. Provide a list of URLs and run the job
urls = ["https://example.com", "https://wikipedia.org"]
results = downloader.download_from_list(urls)

print(f"Job finished: {results}")
# Output: Job finished: {'success': 2, 'failed': 0, 'skipped': 0, 'total': 2}
```

### Example 2: Download from a Template

```python
from wayback_bulk_downloader import WaybackDownloader

downloader = WaybackDownloader(output_dir="comics")

template = "https://xkcd.com/{}/"
comic_ids = [1, 100, 242, 327] # Can be strings or numbers

# The module automatically creates a subdirectory for template jobs.
# Results will be saved in "comics/xkcd.com_"
results = downloader.download_from_template(template, comic_ids)

print(f"Template job finished: {results}")
```

### Example 3: Using a Progress Callback

For real-time feedback in your application, provide an `on_progress` callback function.

```python
from wayback_bulk_downloader import WaybackDownloader

def my_progress_handler(result):
    """This function is called after each URL is processed."""
    status = result['status']
    url = result['original_url']
    path = result['save_path']
    print(f"[{status}] {url} -> {path}")
    if status == 'FAIL':
        print(f"  └─ Error: {result['error_message']}")

downloader = WaybackDownloader(threads=2)
urls = ["https://example.com", "https://not-a-real-site-12345.org"]

downloader.download_from_list(urls, on_progress=my_progress_handler)
```

## Command-Line Options

| Option             | Alias | Description                                                                                             | Default                  |
| ------------------ | ----- | ------------------------------------------------------------------------------------------------------- | ------------------------ |
| `--url`            | `-u`  | **Mode 1:** A single URL to download.                                                                   | -                        |
| `--list`           | `-l`  | **Mode 2:** Path to a text file with URLs.                                                              | -                        |
| `--template`       |       | **Mode 3:** A URL template with a `{}` placeholder. Must be used with `--params`.                         | -                        |
| `--params`         |       | Path to a text file with parameter values for template mode.                                            | -                        |
| `--output-dir`     | `-o`  | Directory to save downloads.                                                                            | `wayback_downloads`      |
| `--timestamp`      | `-t`  | Wayback Machine timestamp (e.g., `20150101`). If omitted, fetches the latest version.                    | `None` (latest)          |
| `--threads`        |       | Number of concurrent download threads.                                                                  | `1`                      |
| `--delay`          |       | Minimum time (in seconds) between requests across ALL threads.                                          | `1.0`                    |
| `--retries`        |       | Number of retries on rate-limit errors (HTTP 429).                                                      | `3`                      |
| `--skip-existing`  |       | Skip downloading if the output file already exists.                                                     | `False`                  |
| `--log`            |       | Path to a CSV file to log all download attempts.                                                        | `None`                   |
| `--verbose`        | `-v`  | Enable verbose output for debugging.                                                                    | `False`                  |
| `--user-agent`     |       | Custom User-Agent string for requests.                                                                  | `WaybackBulkDownloader/2.6` |

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
