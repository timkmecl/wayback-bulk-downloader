import unittest
import os
import shutil
import tempfile
from wayback_bulk_downloader import WaybackDownloader

class TestWaybackDownloader(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for downloads
        self.test_dir = tempfile.mkdtemp()
        self.downloader = WaybackDownloader(
            output_dir=self.test_dir,
            verbose=True,
            show_progress=False,
            delay=1.0 # Be polite to the API
        )

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def test_single_url_download(self):
        print("\nTesting single URL download...")
        # Use a small, reliable page
        url = "http://example.com"
        results = self.downloader.download_url(url)
        
        self.assertEqual(results['success'], 1)
        self.assertEqual(results['failed'], 0)
        
        # Verify file exists
        # The filename sanitization might vary, so we check if any file is in the dir
        files = os.listdir(self.test_dir)
        self.assertTrue(len(files) > 0, "No files downloaded")
        print(f"Downloaded files: {files}")

    def test_list_download(self):
        print("\nTesting list download...")
        urls = ["http://example.com", "http://www.iana.org/domains/reserved"]
        results = self.downloader.download_from_list(urls)
        
        self.assertEqual(results['success'], 2)
        self.assertEqual(results['failed'], 0)
        
        files = os.listdir(self.test_dir)
        self.assertEqual(len(files), 2, "Should have downloaded 2 files")

    def test_sanitize_filename(self):
        print("\nTesting filename sanitization...")
        from wayback_bulk_downloader import sanitize_filename
        
        self.assertEqual(sanitize_filename("http://example.com"), "example.com")
        self.assertEqual(sanitize_filename("https://example.com/foo/bar"), "example.com_foo_bar")
        self.assertEqual(sanitize_filename("invalid*chars:<>|"), "invalid_chars____")
        
        # Test length truncation
        long_name = "a" * 250
        sanitized = sanitize_filename(long_name)
        self.assertEqual(len(sanitized), 200)

    def test_skip_existing(self):
        print("\nTesting skip_existing functionality...")
        url = "http://example.com"
        
        # First download
        self.downloader.download_url(url)
        
        # Enable skip_existing
        self.downloader.skip_existing = True
        
        # Second download attempt
        results = self.downloader.download_url(url)
        
        self.assertEqual(results['skipped'], 1)
        self.assertEqual(results['success'], 0)

    def test_timestamp_download(self):
        print("\nTesting timestamp download...")
        # Use a specific timestamp for Google
        self.downloader.timestamp = "20100101"
        url = "http://google.com"
        
        results = self.downloader.download_url(url)
        self.assertEqual(results['success'], 1)
        
        # Verify the file name contains the timestamp suffix if the code adds it?
        # Looking at the code: save_path = ... + ts_suffix + ".html"
        # ts_suffix = f"_{self.timestamp}"
        expected_filename = "google.com_20100101.html"
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, expected_filename)))

    def test_not_archived_url(self):
        print("\nTesting non-archived URL...")
        # A random UUID url that definitely shouldn't exist
        url = "http://this-domain-definitely-does-not-exist-12345.com/foo"
        
        results = self.downloader.download_url(url)
        
        # Should fail gracefully
        self.assertEqual(results['failed'], 1)
        self.assertEqual(results['success'], 0)

    def test_logging(self):
        print("\nTesting logging functionality...")
        log_file = os.path.join(self.test_dir, "download_log.csv")
        self.downloader.log_file = log_file
        
        url = "http://example.com"
        self.downloader.download_url(url)
        
        self.assertTrue(os.path.exists(log_file))
        
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Check for header
            self.assertIn("download_timestamp_utc,original_url", content)
            # Check for the URL entry
            self.assertIn("example.com", content)
            self.assertIn("SUCCESS", content)

    def test_template_download(self):
        print("\nTesting template download...")
        # A simple template test. 
        # Using a dummy template that might not return 200s on wayback for all, 
        # but let's try something that likely exists or just check the logic.
        # Actually, let's use a real one but keep it small.
        # specific wikipedia pages usually exist.
        template = "https://en.wikipedia.org/wiki/{}"
        params = ["Python_(programming_language)", "Rust_(programming_language)"]
        
        results = self.downloader.download_from_template(template, params)
        
        self.assertEqual(results['success'], 2)
        
        # Template downloads go into a subdir
        # subdir name is based on the template URL
        subdirs = [d for d in os.listdir(self.test_dir) if os.path.isdir(os.path.join(self.test_dir, d))]
        self.assertTrue(len(subdirs) > 0)
        
        subdir_path = os.path.join(self.test_dir, subdirs[0])
        files = os.listdir(subdir_path)
        self.assertEqual(len(files), 2)

if __name__ == '__main__':
    unittest.main()
