#!/usr/bin/env python3
import requests
import os
import time
import re
import argparse
import sys

# --- Default Configuration ---
DEFAULT_OUTPUT_DIR = "wayback_downloads"
DEFAULT_DELAY = 1.0  # seconds
DEFAULT_RETRIES = 3
DEFAULT_USER_AGENT = "WaybackMachineDownloader/1.0 (Python/Requests; +https://github.com/)"

def sanitize_filename(url):
    """Converts a URL into a safe filename."""
    if url.endswith('/'):
        url = url[:-1]
    sanitized = re.sub(r'^https?:\/\/', '', url)
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', sanitized)
    return (sanitized[:200]) if len(sanitized) > 200 else sanitized

def download_url(session, url, timestamp, save_path):
    """
    Downloads a specific URL from the Wayback Machine with retry logic.
    - timestamp: A specific timestamp (e.g., '20150101') or '*' for latest.
    """
    wayback_url = f"https://web.archive.org/web/{timestamp}/{url}"
    
    print(f"  -> Requesting: {wayback_url}")
    
    retry_delay_base = 5  # seconds

    for attempt in range(args.retries):
        try:
            response = session.get(wayback_url, timeout=45)
            response.raise_for_status()

            if "Wayback Machine has not archived that URL." in response.text:
                print(f"  -> No archive found for: {url}")
                return False
            
            final_url = response.url
            if timestamp == '*':
                print(f"  -> Redirected to latest snapshot: {final_url}")
            else:
                 print(f"  -> Found snapshot: {final_url}")

            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            print(f"  -> Successfully saved to: {save_path}")
            return True

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                retry_delay = retry_delay_base * (attempt + 1)
                print(f"  -> Rate limit hit. Waiting {retry_delay}s before retry {attempt + 1}/{args.retries}...")
                time.sleep(retry_delay)
                continue
            else:
                print(f"  -> HTTP Error for {url}: {e}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"  -> Network error for {url}: {e}")
            return False

    print(f"  -> Failed to download {url} after {args.retries} retries.")
    return False

def main(args):
    """Main execution function."""
    
    # 1. Determine the list of URLs to process
    urls_to_process = []
    if args.url:
        urls_to_process.append(args.url)
    elif args.list:
        try:
            with open(args.list, 'r') as f:
                urls_to_process = [line.strip() for line in f if line.strip()]
            if not urls_to_process:
                print(f"Error: Input file '{args.list}' is empty or contains no valid URLs.")
                sys.exit(1)
        except FileNotFoundError:
            print(f"Error: Input file not found at '{args.list}'")
            sys.exit(1)

    # 2. Setup output directory and session
    try:
        os.makedirs(args.output_dir, exist_ok=True)
    except OSError as e:
        print(f"Error: Could not create output directory '{args.output_dir}': {e}")
        sys.exit(1)
        
    headers = {'User-Agent': args.user_agent}
    session = requests.Session()
    session.headers.update(headers)

    # 3. Print summary of the job
    print("--- Wayback Machine Downloader ---")
    print(f"Total URLs to process: {len(urls_to_process)}")
    print(f"Output directory:      {args.output_dir}")
    if args.timestamp == '*':
        print("Timestamp:             Latest available")
    else:
        print(f"Timestamp:             {args.timestamp}")
    print(f"Delay between requests: {args.delay}s")
    print("----------------------------------\n")

    # 4. Process each URL
    success_count = 0
    fail_count = 0
    total_urls = len(urls_to_process)
    
    for i, url in enumerate(urls_to_process):
        print(f"[{i+1}/{total_urls}] Processing: {url}")
        
        # Use a timestamp in the filename if one is provided
        ts_suffix = f"_{args.timestamp}" if args.timestamp != '*' else ''
        filename = sanitize_filename(url) + ts_suffix + ".html"
        file_path = os.path.join(args.output_dir, filename)

        if download_url(session, url, args.timestamp, file_path):
            success_count += 1
        else:
            fail_count += 1

        if i < total_urls - 1:
            time.sleep(args.delay)
    
    session.close()

    # 5. Final Report
    print("\n--- Download Complete ---")
    print(f"Successfully downloaded: {success_count}")
    print(f"Failed to download:      {fail_count}")
    print("-------------------------")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A CLI tool to download archived HTML pages from the Internet Archive's Wayback Machine.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # Input group: user must provide either a single URL or a file list
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "-u", "--url", 
        help="A single URL to download."
    )
    input_group.add_argument(
        "-l", "--list", 
        help="Path to a text file containing a list of URLs to download (one per line)."
    )

    # Optional arguments for customization
    parser.add_argument(
        "-o", "--output-dir", 
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save the downloaded files.\n(default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "-t", "--timestamp", 
        default='*',
        help="The timestamp to use for the snapshot. Format: YYYYMMDDhhmmss\n"
             "Use a partial timestamp like '2015' to get the first snapshot of that year.\n"
             "Use '*' to get the latest available snapshot.\n(default: '*')"
    )
    parser.add_argument(
        "--delay", 
        type=float, 
        default=DEFAULT_DELAY,
        help=f"Polite delay in seconds between each download request.\n(default: {DEFAULT_DELAY}s)"
    )
    parser.add_argument(
        "--retries", 
        type=int, 
        default=DEFAULT_RETRIES,
        help=f"Number of times to retry a download if rate-limited.\n(default: {DEFAULT_RETRIES})"
    )
    parser.add_argument(
        "--user-agent", 
        default=DEFAULT_USER_AGENT,
        help="Custom User-Agent string for HTTP requests."
    )

    args = parser.parse_args()
    main(args)