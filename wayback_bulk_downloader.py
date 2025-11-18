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
DEFAULT_DELAY = 1.0
DEFAULT_RETRIES = 3
DEFAULT_THREADS = 1
DEFAULT_USER_AGENT = "WaybackBulkDownloader/2.1 (Python/Requests; +https://github.com/)"

# Thread-safe print and counters
print_lock = threading.Lock()
success_count = 0
fail_count = 0

def tprint(text):
    """A thread-safe print function."""
    with print_lock:
        print(text)

def sanitize_filename(url):
    """Converts a URL into a safe filename."""
    if url.endswith('/'):
        url = url[:-1]
    sanitized = re.sub(r'^https?:\/\/', '', url)
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', sanitized)
    return (sanitized[:200]) if len(sanitized) > 200 else sanitized

def download_worker(q, session, args, log_file_lock, log_file_path):
    """The function run by each thread to process URLs from the queue."""
    global success_count, fail_count

    while not q.empty():
        original_url, save_path = q.get()
        
        # Get the current time in UTC for consistent logging
        timestamp_utc_str = datetime.utcnow().isoformat()
        # Build the correct Wayback Machine URL
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
                    break # No point in retrying if it's not archived

                with open(save_path, 'wb') as f:
                    f.write(response.content)
                
                status = "SUCCESS"
                final_url = response.url
                error_msg = ""
                
                if args.verbose:
                    tprint(f"  -> Redirected to: {final_url}")
                tprint(f"  -> Successfully saved to: {save_path}")
                break # Success, exit retry loop

            except requests.exceptions.HTTPError as e:
                error_msg = str(e)
                if e.response.status_code == 429:
                    retry_delay = 5 * (attempt + 1)
                    tprint(f"  -> Rate limit hit for {original_url}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                else:
                    tprint(f"  -> HTTP Error for {original_url}: {e}")
                    break
            except requests.exceptions.RequestException as e:
                error_msg = str(e)
                tprint(f"  -> Network error for {original_url}: {e}")
                break
        
        # Update counters and log file safely
        with print_lock:
            if status == "SUCCESS":
                success_count += 1
            else:
                fail_count += 1
        
        if log_file_path:
            with log_file_lock:
                with open(log_file_path, 'a', encoding='utf-8') as lf:
                    lf.write(f'"{timestamp_utc_str}","{original_url}","{final_url}","{status}","{save_path}","{error_msg}"\n')

        q.task_done()

def main(args):
    """Main execution function."""
    
    # 1. Get list of URLs
    urls_to_process = []
    if args.url:
        urls_to_process.append(args.url)
    elif args.list:
        try:
            with open(args.list, 'r') as f:
                urls_to_process = [line.strip() for line in f if line.strip()]
            if not urls_to_process:
                print(f"Error: Input file '{args.list}' is empty.")
                sys.exit(1)
        except FileNotFoundError:
            print(f"Error: Input file not found at '{args.list}'")
            sys.exit(1)

    # 2. Setup output directory and session
    os.makedirs(args.output_dir, exist_ok=True)
    session = requests.Session()
    session.headers.update({'User-Agent': args.user_agent})
    
    # 3. Setup log file if requested
    log_file_lock = threading.Lock() if args.log else None
    if args.log:
        with open(args.log, 'w', encoding='utf-8') as lf:
            lf.write("download_timestamp_utc,original_url,final_url,status,local_path,error_message\n")

    # 4. Populate queue with jobs
    q = Queue()
    skipped_count = 0
    for url in urls_to_process:
        ts_suffix = f"_{args.timestamp}" if args.timestamp else ''
        filename = sanitize_filename(url) + ts_suffix + ".html"
        file_path = os.path.join(args.output_dir, filename)

        if args.skip_existing and os.path.exists(file_path):
            tprint(f"  -> Skipping existing file: {file_path}")
            skipped_count += 1
            continue
        
        q.put((url, file_path))
    
    # 5. Print summary
    print("--- Wayback Machine Bulk Downloader ---")
    print(f"URLs to download:      {q.qsize()}")
    print(f"URLs skipped:          {skipped_count}")
    print(f"Output directory:      {args.output_dir}")
    print(f"Timestamp:             {'Latest available' if not args.timestamp else args.timestamp}")
    print(f"Concurrent threads:    {args.threads}")
    if args.log:
        print(f"Log file:              {args.log}")
    print("---------------------------------------\n")
    
    if q.empty():
        print("No URLs to download. Exiting.")
        return

    # 6. Start worker threads
    threads = []
    for _ in range(args.threads):
        thread = threading.Thread(
            target=download_worker, 
            args=(q, session, args, log_file_lock, args.log)
        )
        thread.daemon = True
        thread.start()
        threads.append(thread)

    q.join()
    session.close()

    # 7. Final Report
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

    # Input group
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-u", "--url", help="A single URL to download.")
    input_group.add_argument("-l", "--list", help="Path to a text file with URLs (one per line).")

    # Configuration options
    parser.add_argument("-o", "--output-dir", default=DEFAULT_OUTPUT_DIR, help=f"Directory to save downloads.\n(default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("-t", "--timestamp", help="Wayback Machine timestamp (e.g., 20150101).\nIf omitted, fetches the latest available version.")
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS, help=f"Number of concurrent download threads.\n(default: {DEFAULT_THREADS})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"Polite delay between requests (per thread).\n(This feature is less effective with threads; use retries).")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help=f"Number of retries on rate-limit errors.\n(default: {DEFAULT_RETRIES})")
    
    # Behavior flags
    parser.add_argument("--skip-existing", action='store_true', help="Skip downloading a URL if the output file already exists.")
    parser.add_argument("--log", help="Path to a CSV file to log all download attempts.")
    parser.add_argument("-v", "--verbose", action='store_true', help="Enable verbose output for debugging.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="Custom User-Agent string for requests.")
    
    args = parser.parse_args()
    main(args)