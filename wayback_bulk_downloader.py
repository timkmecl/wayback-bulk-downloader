#!/usr/bin/env python3
import requests
import os
import time
import re
import argparse
import sys
import threading
from queue import Queue
from datetime import datetime

# --- Default Configuration ---
DEFAULT_OUTPUT_DIR = "wayback_downloads"
DEFAULT_THREADS = 1
DEFAULT_RETRIES = 3
DEFAULT_DELAY = 1.0 # Default delay of 1 second between requests
DEFAULT_USER_AGENT = "WaybackBulkDownloader/2.3 (Python/Requests; +https://github.com/)"

# --- Global Threading Primitives ---
print_lock = threading.Lock()
# For global rate limiting
rate_limit_lock = threading.Lock()
last_request_time = 0
# For tracking progress
success_count = 0
fail_count = 0

def tprint(text):
    """A thread-safe print function."""
    with print_lock:
        print(text)

def sanitize_filename(url_or_string):
    """Converts a string (URL or other) into a safe filename component."""
    s = url_or_string
    if s.endswith('/'):
        s = s[:-1]
    s = re.sub(r'^https?:\/\/', '', s)
    s = re.sub(r'[\\/:*?"<>|]', '_', s)
    return (s[:200]) if len(s) > 200 else s

def download_worker(q, session, args, log_file_lock, log_file_path):
    """The function run by each thread to process URLs from the queue."""
    global success_count, fail_count, last_request_time

    while not q.empty():
        original_url, save_path = q.get()
        timestamp_utc_str = datetime.utcnow().isoformat()

        # --- Global Rate Limiting ---
        if args.delay > 0:
            with rate_limit_lock:
                now = time.time()
                elapsed = now - last_request_time
                if elapsed < args.delay:
                    time.sleep(args.delay - elapsed)
                last_request_time = time.time()
        # --- End Rate Limiting ---

        if args.timestamp:
            wayback_url = f"https://web.archive.org/web/{args.timestamp}/{original_url}"
        else:
            wayback_url = f"https://web.archive.org/web/{original_url}"

        if args.verbose:
            tprint(f"  -> Thread {threading.get_ident()}: Requesting {wayback_url}")
        
        status, final_url, error_msg = "FAIL", "", "Unknown error"
        
        for attempt in range(args.retries):
            try:
                response = session.get(wayback_url, timeout=45)
                response.raise_for_status()
                if "Wayback Machine has not archived that URL." in response.text:
                    error_msg = "No archive found"
                    tprint(f"  -> No archive found for: {original_url}")
                    break

                with open(save_path, 'wb') as f: f.write(response.content)
                status, final_url, error_msg = "SUCCESS", response.url, ""
                if args.verbose: tprint(f"  -> Redirected to: {final_url}")
                tprint(f"  -> Successfully saved to: {save_path}")
                break

            except requests.exceptions.HTTPError as e:
                error_msg = str(e)
                if e.response.status_code == 429:
                    retry_delay = 5 * (attempt + 1)
                    tprint(f"  -> Rate limit hit for {original_url}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                else:
                    tprint(f"  -> HTTP Error for {original_url}: {e}"); break
            except requests.exceptions.RequestException as e:
                error_msg = str(e); tprint(f"  -> Network error for {original_url}: {e}"); break
        
        with print_lock:
            if status == "SUCCESS": success_count += 1
            else: fail_count += 1
        
        if log_file_path:
            with log_file_lock:
                with open(log_file_path, 'a', encoding='utf-8') as lf:
                    lf.write(f'"{timestamp_utc_str}","{original_url}","{final_url}","{status}","{save_path}","{error_msg}"\n')
        q.task_done()

def main(args):
    """Main execution function."""
    global last_request_time
    last_request_time = time.time()
    
    jobs = []
    mode_description = ""
    
    if args.template and args.params:
        mode_description = f"Template: {args.template}, Params: {args.params}"
        subdir_name = sanitize_filename(args.template.replace('{}', ''))
        job_output_dir = os.path.join(args.output_dir, subdir_name)
        os.makedirs(job_output_dir, exist_ok=True)
        try:
            with open(args.params, 'r') as f: params = [line.strip() for line in f if line.strip()]
            for param in params:
                if re.search(r'[\\/:*?"<>|]', param):
                    tprint(f"Warning: Skipping invalid parameter '{param}' (contains illegal filename characters).")
                    continue
                full_url = args.template.format(param)
                filename = f"{param}.html"
                save_path = os.path.join(job_output_dir, filename)
                jobs.append((full_url, save_path))
        except FileNotFoundError: print(f"Error: Parameter file not found at '{args.params}'"); sys.exit(1)
    else:
        urls_to_process = []
        if args.url: urls_to_process.append(args.url); mode_description = f"Single URL: {args.url}"
        elif args.list:
            mode_description = f"URL List: {args.list}"
            try:
                with open(args.list, 'r') as f: urls_to_process = [line.strip() for line in f if line.strip()]
            except FileNotFoundError: print(f"Error: URL list file not found at '{args.list}'"); sys.exit(1)
        for url in urls_to_process:
            ts_suffix = f"_{args.timestamp}" if args.timestamp else ''
            filename = sanitize_filename(url) + ts_suffix + ".html"
            save_path = os.path.join(args.output_dir, filename)
            jobs.append((url, save_path))

    session = requests.Session()
    session.headers.update({'User-Agent': args.user_agent})
    
    log_file_lock = threading.Lock() if args.log else None
    if args.log:
        with open(args.log, 'w', encoding='utf-8') as lf:
            lf.write("download_timestamp_utc,original_url,final_url,status,local_path,error_message\n")

    q = Queue()
    skipped_count = 0
    for url, path in jobs:
        if args.skip_existing and os.path.exists(path):
            tprint(f"  -> Skipping existing file: {path}"); skipped_count += 1; continue
        q.put((url, path))

    print("--- Wayback Machine Bulk Downloader ---")
    print(f"Mode:                  {mode_description}")
    print(f"URLs to download:      {q.qsize()}")
    print(f"URLs skipped:          {skipped_count}")
    print(f"Output directory:      {args.output_dir}")
    print(f"Timestamp:             {'Latest available' if not args.timestamp else args.timestamp}")
    print(f"Concurrent threads:    {args.threads}")
    print(f"Delay between requests: {args.delay}s")
    if args.log: print(f"Log file:              {args.log}")
    print("---------------------------------------\n")
    
    if q.empty(): print("No new URLs to download. Exiting."); return

    threads = []
    for _ in range(args.threads):
        thread = threading.Thread(target=download_worker, args=(q, session, args, log_file_lock, args.log))
        thread.daemon = True; thread.start(); threads.append(thread)
    q.join(); session.close()

    print("\n--- Download Complete ---")
    print(f"Successfully downloaded: {success_count}")
    print(f"Failed to download:      {fail_count}")
    print(f"Skipped (already exist): {skipped_count}")
    print("-------------------------")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A powerful CLI tool to bulk download pages from the Wayback Machine.",
        formatter_class=argparse.RawTextHelpFormatter
    )
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
    main(args)