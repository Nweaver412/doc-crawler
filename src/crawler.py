import os
import re
import requests
import time
from github import Github, RateLimitExceededException
import logging
from tqdm import tqdm  # For the spinner

# Setup logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Function to extract links from markdown files
def extract_links_from_md(file_content):
    # Regex to find URLs (starting with http or https)
    urls = re.findall(r'(https?://[^\s]+)', file_content)
    return urls

# Function to implement backoff with spinner
def backoff_with_spinner(delay):
    logging.info(f"Backing off for {delay:.2f} seconds due to rate limit.")
    
    # Create a spinner during the backoff period
    for _ in tqdm(range(int(delay)), desc="Waiting for rate limit reset", unit="sec", ncols=80):
        time.sleep(1)  # Sleep for 1 second each loop iteration

# Function to check if a URL is dead with backoff
def check_url(url, max_retries=3, base_delay=2):
    attempt = 0
    while attempt <= max_retries:
        try:
            response = requests.head(url, timeout=5)
            if response.status_code == 404:
                logging.warning(f"Dead link found: {url} (404 Not Found)")
                return False
            else:
                logging.info(f"Valid link: {url} (Status code: {response.status_code})")
            return True
        except requests.RequestException as e:
            logging.error(f"Error checking link {url}: {e}")
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                backoff_with_spinner(delay)
                attempt += 1
            else:
                logging.error(f"Max retries reached for {url}")
                return False

# Function to handle rate limit exceeded case
def handle_rate_limit_exception(exception):
    reset_time = exception.headers.get("X-RateLimit-Reset")
    if reset_time:
        # Calculate delay until rate limit reset
        current_time = time.time()
        delay = int(reset_time) - int(current_time)
        if delay > 0:
            backoff_with_spinner(delay)
    else:
        # Fallback delay if reset time is not provided
        backoff_with_spinner(60)  # Default to 1 minute

# Function to write dead links to a text file
def write_dead_links_to_file(dead_links, file_name="dead_links.txt"):
    with open(file_name, "w") as f:
        for file_path, dead_link in dead_links:
            f.write(f"Link: {dead_link}  Page: {file_path}\n")
    logging.info(f"Dead links written to {file_name}")

# Main function to crawl a GitHub repo
def check_dead_links_in_github_repo(repo_url, token=None):
    # Authenticate GitHub (optional)
    if token:
        g = Github(token)
    else:
        g = Github()

    # Extract repo name from the URL
    repo_name = repo_url.rstrip('/').split('/')[-1]

    logging.info(f"Starting to check repository: {repo_name}")

    # Get the repo
    repo = g.get_repo(repo_name)

    dead_links = []
    total_links_checked = 0

    # Get all contents of the repository
    contents = repo.get_contents("")
    while contents:
        file_content = contents.pop(0)
        if file_content.type == "dir":
            logging.info(f"Entering directory: {file_content.path}")
            contents.extend(repo.get_contents(file_content.path))
        elif file_content.path.endswith(".md"):
            logging.info(f"Checking file: {file_content.path}")

            # Read the file content
            file_content_decoded = file_content.decoded_content.decode()

            # Extract links
            urls = extract_links_from_md(file_content_decoded)
            logging.info(f"Found {len(urls)} links in {file_content.path}")

            # Check each URL
            for url in urls:
                total_links_checked += 1
                if not check_url(url):
                    dead_links.append((file_content.path, url))

    # Log summary
    logging.info(f"Total links checked: {total_links_checked}")
    logging.info(f"Total dead links found: {len(dead_links)}")

    # Write dead links to a file
    write_dead_links_to_file(dead_links)

    return dead_links

# Example usage
if __name__ == "__main__":
    # GitHub repo URL
    repo_url = input("Enter the GitHub repository URL to check: ")

    if repo_url == "quit":
        exit()
        
    try:
        # Check for dead links
        dead_links = check_dead_links_in_github_repo(repo_url)
    except RateLimitExceededException as e:
        handle_rate_limit_exception(e)

    # Print results
    if dead_links:
        print("Dead links found and written to dead_links.txt.")
    else:
        print("No dead links found.")
