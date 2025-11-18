#!/usr/bin/env python3
"""
Wayback Machine Bulk Downloader (v2.6)

A powerful CLI tool and importable Python module to bulk download pages
from the Internet Archive's Wayback Machine.

**Module Usage Example:**

  from wayback_bulk_downloader import WaybackDownloader

  # --- Example 1: Download a list of URLs ---
  downloader = WaybackDownloader(output_dir="my_archive", threads=4)
  urls = ["https://example.com", "https://wikipedia.org"]
  results = downloader.download_from_list(urls)
  print(f"List download finished: {results}")

  # --- Example 2: Download using a template ---
  template = "https://www.erowid.org/experiences/exp.php?ID={}"
  params = [10931, 8633, 5880] # Can be strings or numbers
  # Results will be in "my_archive/www.erowid.org_experiences_exp.php_ID="
  results = downloader.download_from_template(template, params)
  print(f"Template download finished: {results}")
"""
import requests
import os
import time
import re
import argparse
import sys
import threading
from queue import Queue
import datetime

# --- Default Configuration ---
DEFAULT_OUTPUT_DIR = "wayback_downloads"
DEFAULT_THREADS = 1
DEFAULT_RETRIES = 3
DEFAULT_DELAY = 1.0
DEFAULT_USER_AGENT = "WaybackBulkDownloader/2.6 (Python/Requests; +https://github.com/)"


def sanitize_filename(url_or_string):
    """Converts a string (URL or other) into a safe filename component."""
    s = str(url_or_string) # Ensure it's a string
    if s.endswith('/'): s = s[:-1]
    s = re.sub(r'^https?:\/\/', '', s)
    s = re.sub(r'[\\/:*?"<>|]', '_', s)
    return (s[:200]) if len(s) > 200 else s


class WaybackDownloader:
    """
    Manages a bulk download job from the Wayback Machine. Instantiate this
    class with your desired configuration, then call one of the download
    methods (`download_from_list`, `download_from_template`).
    """
    def __init__(self, output_dir=DEFAULT_OUTPUT_DIR, threads=DEFAULT_THREADS,
                 delay=DEFAULT_DELAY, retries=DEFAULT_RETRIES,
                 skip_existing=False, user_agent=DEFAULT_USER_AGENT,
                 log_file=None, verbose=False, timestamp=None):
        self.output_dir = output_dir
        self.threads = threads
        self.delay = delay
        self.retries = retries
        self.skip_existing = skip_existing
        self.user_agent = user_agent
        self.log_file = log_file
        self.verbose = verbose
        self.timestamp = timestamp
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})
        # Internal state reset for each job
        self._reset_state()

    def _reset_state(self):
        """Resets the queue and counters for a new download job."""
        self.q = Queue()
        self.rate_limit_lock = threading.Lock()
        self.log_file_lock = threading.Lock() if self.log_file else None
        self.last_request_time = 0
        self.success_count = 0
        self.fail_count = 0
        self.skipped_count = 0

    def download_url(self, url, on_progress=None):
        """Convenience method to download a single URL."""
        return self.download_from_list([url], on_progress)

    def download_from_list(self, url_list, on_progress=None):
        """
        Prepares and runs a download job from a list of URLs.
        Args:
            url_list (list): A list of URL strings to download.
            on_progress (callable, optional): Callback function for progress updates.
        Returns:
            dict: A summary of the download results.
        """
        self._reset_state()
        jobs = []
        for url in url_list:
            ts_suffix = f"_{self.timestamp}" if self.timestamp else ''
            save_path = os.path.join(self.output_dir, sanitize_filename(url) + ts_suffix + ".html")
            jobs.append((url, save_path))
        return self._run_download_job(jobs, on_progress)

    def download_from_template(self, template_url, params_list, on_progress=None):
        """
        Prepares and runs a download job from a URL template and a list of parameters.
        Files will be saved in a subdirectory named after the template.
        Args:
            template_url (str): A URL string with a placeholder '{}'.
            params_list (list): A list of strings or numbers to insert into the template.
            on_progress (callable, optional): Callback function for progress updates.
        Returns:
            dict: A summary of the download results.
        """
        self._reset_state()
        jobs = []
        subdir_name = sanitize_filename(template_url.replace('{}', ''))
        job_output_dir = os.path.join(self.output_dir, subdir_name)
        
        for param in params_list:
            param_str = str(param)
            if re.search(r'[\\/:*?"<>|]', param_str):
                print(f"Warning: Skipping invalid parameter '{param_str}' (contains illegal filename characters).")
                continue
            full_url = template_url.format(param)
            save_path = os.path.join(job_output_dir, f"{param_str}.html")
            jobs.append((full_url, save_path))
        return self._run_download_job(jobs, on_progress, job_output_dir)

    def _run_download_job(self, jobs, on_progress=None, job_output_dir=None):
        """Internal method to execute a prepared list of download jobs."""
        output_dir = job_output_dir or self.output_dir
        os.makedirs(output_dir, exist_ok=True)

        if self.log_file:
            with open(self.log_file, 'w', encoding='utf-8') as lf:
                lf.write("download_timestamp_utc,original_url,final_url,status,local_path,error_message\n")

        for url, path in jobs:
            if self.skip_existing and os.path.exists(path):
                self.skipped_count += 1
                if on_progress:
                    on_progress({
                        'timestamp_utc': datetime.datetime.now(datetime.UTC).isoformat(),
                        'original_url': url, 'final_url': '', 'status': 'SKIPPED',
                        'save_path': path, 'error_message': 'File already exists'
                    })
                continue
            self.q.put((url, path))
        
        self.last_request_time = time.time()
        
        if self.q.empty():
            return {'success': 0, 'failed': 0, 'skipped': self.skipped_count, 'total': len(jobs)}

        threads = []
        for _ in range(self.threads):
            thread = threading.Thread(target=self._download_worker, args=(on_progress,))
            thread.daemon = True; thread.start(); threads.append(thread)
        self.q.join()
        self.session.close()

        return {
            'success': self.success_count, 'failed': self.fail_count,
            'skipped': self.skipped_count, 'total': len(jobs)
        }

    def _download_worker(self, on_progress):
        # This method remains the same as v2.5
        while not self.q.empty():
            original_url, save_path = self.q.get()
            if self.delay > 0:
                with self.rate_limit_lock:
                    now = time.time()
                    elapsed = now - self.last_request_time
                    if elapsed < self.delay: time.sleep(self.delay - elapsed)
                    self.last_request_time = time.time()
            ts_part = f"{self.timestamp}/" if self.timestamp else ""
            wayback_url = f"https://web.archive.org/web/{ts_part}{original_url}"
            if self.verbose: self._tprint(f"  -> Thread {threading.get_ident()}: Requesting {wayback_url}")
            status, final_url, error_msg = "FAIL", "", "Unknown error"
            for attempt in range(self.retries):
                try:
                    response = self.session.get(wayback_url, timeout=45)
                    response.raise_for_status()
                    if "Wayback Machine has not archived that URL." in response.text:
                        error_msg = "No archive found"; break
                    with open(save_path, 'wb') as f: f.write(response.content)
                    status, final_url, error_msg = "SUCCESS", response.url, ""
                    break
                except requests.exceptions.HTTPError as e:
                    error_msg = str(e)
                    if e.response.status_code == 429:
                        retry_delay = 5 * (attempt + 1)
                        if self.verbose: self._tprint(f"  -> Rate limit hit for {original_url}. Retrying in {retry_delay}s...")
                        time.sleep(retry_delay); continue
                    else: break
                except requests.exceptions.RequestException as e: error_msg = str(e); break
            result_info = {
                'timestamp_utc': datetime.datetime.now(datetime.UTC).isoformat(),
                'original_url': original_url, 'final_url': final_url,
                'status': status, 'save_path': save_path,
                'error_message': error_msg
            }
            if status == "SUCCESS": self.success_count += 1
            else: self.fail_count += 1
            if self.log_file: self._log_to_file(result_info)
            if on_progress: on_progress(result_info)
            self.q.task_done()

    def _log_to_file(self, result):
        with self.log_file_lock:
            with open(self.log_file, 'a', encoding='utf-8') as lf:
                lf.write(f'"{result["timestamp_utc"]}","{result["original_url"]}",'
                         f'"{result["final_url"]}","{result["status"]}",'
                         f'"{result["save_path"]}","{result["error_message"]}"\n')
    @staticmethod
    def _tprint(text):
        # A simple static print method for internal verbose use
        print(text)

# ==============================================================================
# CLI - Command Line Interface Section
# ==============================================================================
def main_cli():
    """Parses arguments and runs the downloader for command-line usage."""
    parser = argparse.ArgumentParser(
        description="A powerful CLI tool to bulk download pages from the Wayback Machine.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    # ... (argparse setup is unchanged) ...
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-u", "--url", help="Mode 1: A single URL to download.")
    group.add_argument("-l", "--list", help="Mode 2: Path to a text file with URLs (one per line).")
    group.add_argument("--template", help="Mode 3: A URL template with a placeholder '{}'. Must be used with --params.")
    parser.add_argument("--params", help="Path to a text file with parameter values for template mode.")
    parser.add_argument("-o", "--output-dir", default=DEFAULT_OUTPUT_DIR, help=f"Directory to save downloads.\n(default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("-t", "--timestamp", help="Wayback Machine timestamp (e.g., 20150101).\nIf omitted, fetches the latest available version.")
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS, help=f"Number of concurrent download threads.\n(default: {DEFAULT_THREADS})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"Controls the minimum time (in seconds) between requests across ALL threads.\n(default: {DEFAULT_DELAY})")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help=f"Number of retries on rate-limit errors.\n(default: {DEFAULT_RETRIES})")
    parser.add_argument("--skip-existing", action='store_true', help="Skip downloading if the output file already exists.")
    parser.add_argument("--log", help="Path to a CSV file to log all download attempts.")
    parser.add_argument("-v", "--verbose", action='store_true', help="Enable verbose output for debugging.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="Custom User-Agent string for requests.")
    args = parser.parse_args()
    if (args.template and not args.params) or (not args.template and args.params):
        parser.error("--template and --params must be used together.")

    def cli_progress_handler(result):
        if result['status'] == 'SUCCESS': print(f"  -> Successfully saved to: {result['save_path']}")
        elif result['status'] == 'SKIPPED': print(f"  -> Skipping existing file: {result['save_path']}")
        else: print(f"  -> FAILED to download {result['original_url']} ({result['error_message']})")

    downloader = WaybackDownloader(
        output_dir=args.output_dir, threads=args.threads, delay=args.delay,
        retries=args.retries, skip_existing=args.skip_existing,
        user_agent=args.user_agent, log_file=args.log,
        verbose=args.verbose, timestamp=args.timestamp
    )
    
    print("--- Wayback Machine Bulk Downloader ---")
    
    results = {}
    if args.url:
        print(f"Mode:                  Single URL: {args.url}")
        results = downloader.download_url(args.url, on_progress=cli_progress_handler)
    elif args.list:
        print(f"Mode:                  URL List: {args.list}")
        try:
            with open(args.list, 'r') as f: urls = [line.strip() for line in f if line.strip()]
            results = downloader.download_from_list(urls, on_progress=cli_progress_handler)
        except FileNotFoundError: print(f"Error: URL list file not found at '{args.list}'"); sys.exit(1)
    elif args.template and args.params:
        print(f"Mode:                  Template: {args.template}")
        try:
            with open(args.params, 'r') as f: params = [line.strip() for line in f if line.strip()]
            results = downloader.download_from_template(args.template, params, on_progress=cli_progress_handler)
        except FileNotFoundError: print(f"Error: Parameter file not found at '{args.params}'"); sys.exit(1)
        
    print("\n--- Download Complete ---")
    print(f"Successfully downloaded: {results.get('success', 0)}")
    print(f"Failed to download:      {results.get('failed', 0)}")
    print(f"Skipped (already exist): {results.get('skipped', 0)}")
    print("-------------------------")

if __name__ == "__main__":
    main_cli()