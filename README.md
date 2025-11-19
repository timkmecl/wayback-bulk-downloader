
# Wayback Machine Bulk Downloader

![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)

A powerful and flexible CLI tool and Python module to bulk download pages from the Internet Archive's Wayback Machine.

This tool is designed for efficiency and politeness, incorporating features like concurrent downloads, rate limiting, automatic retries, and detailed logging. It can be used directly from the command line for archival tasks or imported into your own Python projects for programmatic access.



<details>

<summary>Technical Note: Polite and Efficient Request Handling</summary>

### Technical Note: Polite and Efficient Request Handling

A primary challenge with any bulk downloading tool is interacting with the target server respectfully to avoid being rate-limited or blocked. This tool employs a key strategy for this, inspired by a common pattern in robust HTTP clients.

**The Problem:** The most naive approach to downloading is to make a brand new network connection for every single URL (e.g., calling `requests.get()` in a loop). For a server, this looks like a rapid flood of new, independent connections, which can easily trigger "Too Many Requests" errors. This process is also highly inefficient due to the overhead of establishing a new TCP and TLS handshake for every file.

**The Solution: Connection Pooling**

The initial implementation was inspired by a pattern seen in a Ruby-based downloader which uses a `Net::HTTP` persistent connection. In this Python tool, the same principle is applied using a `requests.Session()` object.

The `Session` object maintains a pool of underlying TCP connections. When making multiple requests to the same host (`web.archive.org`), the session reuses an existing, open connection instead of creating a new one.

This provides two major benefits:

1.  **Reduced Overhead:** By skipping the repeated connection handshakes, the total time spent on network negotiation is drastically reduced, making the download process faster.
2.  **Server-Friendliness:** From the server's perspective, a stream of requests over a single, persistent connection looks like a single, well-behaved client. This is far less likely to trigger connection-based rate limiting than a storm of new connections. The session also efficiently persists headers, like our custom `User-Agent`, across all requests.

This connection pooling strategy, combined with the explicit `--delay` between requests and the automatic retry mechanism for `429` status codes, forms a multi-layered approach that makes the downloader both high-performance and respectful of the Internet Archive's infrastructure.

</details>




## Table of Contents

-   [Key Features](#key-features)
-   [Installation](#installation)
-   [Usage (Command-Line)](#usage-command-line)
-   [Command-Line Options](#command-line-options)
-   [Usage (as a Python Module)](#usage-as-a-python-module)
-   [API Reference](#api-reference)

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
    -   An importable Python module (`WaybackDownloader` class) with a simple API and built-in progress logging.




## Installation

The script is self-contained and requires only the `requests` library.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/wayback-bulk-downloader.git
    cd wayback-bulk-downloader
    ```

2.  **Install dependencies:**
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
| `--silent`         |       | Suppress real-time console progress updates.                                                            | `False`                  |
| `--user-agent`     |       | Custom User-Agent string for requests.                                                                  | `WaybackBulkDownloader/2.7` |



---


## Usage (as a Python Module)

You can import the `WaybackDownloader` class to integrate it into your own projects.

### Example 1: Download with CLI-style Progress

The easiest way to get started. Simply instantiate the downloader with `show_progress=True` to get real-time console feedback, just like the command-line tool.

```python
from wayback_bulk_downloader import WaybackDownloader

# Enable CLI-style progress logging with `show_progress=True`
downloader = WaybackDownloader(
    output_dir="my_archive",
    threads=4,
    show_progress=True
)

urls = ["https://example.com", "https://wikipedia.org"]
results = downloader.download_from_list(urls)

print(f"\nJob finished: {results}")
# Output: Job finished: {'success': 2, 'failed': 0, 'skipped': 0, 'total': 2}
```

### Example 2: Download from a Template

```python
from wayback_bulk_downloader import WaybackDownloader

# We'll enable progress logging here too.
downloader = WaybackDownloader(output_dir="comics", show_progress=True)

template = "https://xkcd.com/{}/"
comic_ids = [1, 100, 242, 327] # Can be strings or numbers

# The module automatically creates a subdirectory for template jobs.
# Results will be saved in "comics/xkcd.com_"
results = downloader.download_from_template(template, comic_ids)

print(f"\nTemplate job finished: {results}")
```

### Example 3: Using a Custom Progress Callback

For more advanced control (e.g., updating a GUI, writing to a database), provide a custom `on_progress` callback function. This will override the default `show_progress` behavior.

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






## API Reference

This section provides a detailed reference for developers who want to use `wayback-bulk-downloader` as a Python module.

### `class WaybackDownloader`

The main class for managing and executing download jobs. You should create an instance of this class with your desired configuration before starting a download.

---

#### `__init__(...)`

Initializes the `WaybackDownloader`.

```python
downloader = WaybackDownloader(
    output_dir="wayback_downloads",
    threads=1,
    delay=1.0,
    retries=3,
    skip_existing=False,
    user_agent="WaybackBulkDownloader/2.7 ...",
    log_file=None,
    verbose=False,
    timestamp=None,
    show_progress=False
)
```

**Parameters:**

| Parameter       | Type                | Description                                                                                             | Default                  |
| --------------- | ------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------ |
| `output_dir`    | `str`               | The root directory where downloaded files will be saved.                                                | `"wayback_downloads"`    |
| `threads`       | `int`               | The number of concurrent download threads to use.                                                       | `1`                      |
| `delay`         | `float`             | The minimum delay in seconds between requests across all threads.                                         | `1.0`                    |
| `retries`       | `int`               | The number of times to retry a download if a rate-limit error (HTTP 429) is encountered.                | `3`                      |
| `timeout`       | `int`               | The timeout in seconds for HTTP requests.                                                                | `45`                     |
| `skip_existing` | `bool`              | If `True`, the downloader will skip any URL whose output file already exists.                             | `False`                  |
| `user_agent`    | `str`               | The User-Agent string to use for all HTTP requests.                                                     | `WaybackBulkDownloader/2.7...` |
| `log_file`      | `str`, `optional`   | If provided, the path to a CSV file where all download attempts will be logged.                         | `None`                   |
| `verbose`       | `bool`              | If `True`, enables verbose internal logging, useful for debugging.                                      | `False`                  |
| `timestamp`     | `str`, `optional`   | The Wayback Machine timestamp to use (e.g., `"20150101"`). If `None`, the latest version is fetched.       | `None`                   |
| `show_progress` | `bool`              | If `True`, prints real-time, CLI-style progress updates to the console. A custom `on_progress` callback will override this. | `False`                  |

---

#### `download_from_list(...)`

Downloads a collection of URLs from a Python list.

**Parameters:**

-   `url_list` (`list[str]`): A list of URL strings to download.
-   `on_progress` (`callable`, `optional`): A function to call after each URL is processed. See [The `on_progress` Callback](#the-on_progress-callback) section for details.

**Returns:**

-   `(dict)`: A dictionary summarizing the results of the job.
    The dictionary contains the following keys:

    | Key       | Type  | Description                                                                    |
    | --------- | ----- | ------------------------------------------------------------------------------ |
    | `success` | `int` | The number of URLs that were successfully downloaded.                            |
    | `failed`  | `int` | The number of URLs that failed to download after all retries.                  |
    | `skipped` | `int` | The number of URLs that were skipped because the output file already existed.    |
    | `total`   | `int` | The total number of URLs that were initially provided for the job.               |


---

#### `download_from_template(...)`

Downloads a collection of URLs built from a template string and a list of parameters. The files are saved in a subdirectory named after the template.

**Parameters:**

-   `template_url` (`str`): A URL string containing a single placeholder `{}`.
-   `params_list` (`list[str | int]`): A list of strings or numbers to be inserted into the template's placeholder.
-   `on_progress` (`callable`, `optional`): A function to call after each URL is processed.

**Returns:**

-   `(dict)`: A dictionary summarizing the results of the job.

---

#### `download_url(...)`

A convenience method for downloading a single URL.

**Parameters:**

-   `url` (`str`): The single URL to download.
-   `on_progress` (`callable`, `optional`): A function to call after the URL is processed.

**Returns:**

-   `(dict)`: A dictionary summarizing the results of the job.

---

#### The `on_progress` Callback

When you provide a callable function to the `on_progress` parameter of a download method, that function will be executed after each URL is processed. It receives a single argument: a dictionary containing detailed information about the attempt.

**Callback Function Signature:**

```python
def my_handler(result: dict):
    # Your logic here
    pass
```

**The `result` Dictionary Structure:**

| Key                 | Type     | Description                                                                     |
| ------------------- | -------- | ------------------------------------------------------------------------------- |
| `timestamp_utc`     | `str`    | The ISO 8601 timestamp (in UTC) of when the download attempt finished.            |
| `original_url`      | `str`    | The URL that was originally requested.                                          |
| `final_url`         | `str`    | The actual snapshot URL after any redirects. Empty on failure.                  |
| `status`            | `str`    | The outcome of the attempt. Can be `SUCCESS`, `FAIL`, or `SKIPPED`.             |
| `save_path`         | `str`    | The local filesystem path where the file was (or would have been) saved.        |
| `error_message`     | `str`    | A description of the error if the status was `FAIL`. Empty on success.          |

---

### Functions

#### `sanitize_filename(url_or_string)`

A standalone helper function to convert a string (like a URL) into a safe string that can be used as part of a filename.

**Parameters:**

-   `url_or_string` (`str`): The input string to sanitize.

**Returns:**

-   `(str)`: A filesystem-safe string.


## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
