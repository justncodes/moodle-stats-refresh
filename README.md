# Moodle Quiz Statistics Refresher

## Purpose

This Python script automates the process of visiting the \"Statistics\" report page for multiple Moodle quizzes. The primary goal is **not** to scrape or download the statistics data, but simply to access the page. Accessing this specific page (`/mod/quiz/report.php?id={cmid}&mode=statistics`) triggers Moodle to recalculate and refresh the underlying quiz statistics, such as the Facility Index and Discriminative Efficiency for questions within the quiz.

This can be useful in scenarios where these statistics have disappeared or are not updating correctly in the Moodle Question Bank view after changes such as migration or potential Moodle bugs.

## How it Works

The script uses the `requests` library to simulate a web browser:

1.  Reads configuration settings (Moodle URL, credentials, paths, delay, SSL settings) from a `config.ini` file.
2.  Logs into the specified Moodle instance using the credentials from the config file.
3.  Reads a list of Moodle **Course Module IDs** (`cmid`s) for quizzes from a text file (path specified via command-line or config file).
4.  For each `cmid` in the list, it constructs the URL for the quiz statistics report page.
5.  It sends an HTTP GET request to that URL using the established Moodle session.
6.  It briefly pauses between requests (delay configurable in `config.ini`) to avoid overloading the Moodle server.

## Prerequisites

*   **Python 3:** The script is written for Python 3.
*   **Required Libraries:** You need to install `requests` and `beautifulsoup4`.
    ```bash
    pip install requests beautifulsoup4
    ```
*   **Moodle Access:** You need valid Moodle user credentials with permission to view the quizzes and their statistics reports, so ideally Administrator.
*   **Database Access (for ID extraction):** You may need access to the Moodle database (MariaDB/MySQL) to extract the necessary Course Module IDs (`cmid`s).

## Setup

1.  **Save the Script:** Save the Python code as `refresh_moodle_stats_requests.py` (or your preferred name).

2.  **Create Configuration File (`config.ini`):**
    *   In the same directory as the script (or specify a different path using `-C`), create a file named `config.ini`.
    *   Add the following content, replacing placeholder values with your actual details. Sections `[Paths]` and `[Settings]` are optional; the script will use internal defaults if they or their keys are missing.

        ```ini
        [Moodle]
        base_url = https://your.moodle.url.here.com
        username = your_moodle_username_here
        password = your_moodle_password_here

        # OPTIONAL CONFIGURATIONS BELOW
        [Paths]
        # Define relative paths for common Moodle endpoints, in case they're different in your instance.
        login_path = /login/index.php
        post_login_check_path = /my/
        # The script looks for quiz_ids.txt in the script directory by default. Change to your path if needed.
        quiz_id_file_path = quiz_ids.txt

        [Settings]
        # Delay between requests in seconds in case of rate limits. 0.5 seconds should be good enough for most cases.
        request_delay_seconds = 0.5
        # SSL Verification (true/false). Set to false if using a cert that would fail to validate (such as sef-signed).
        verify_ssl = false
        ```
    *   **Security:** Protect this file appropriately, as it contains sensitive credentials. Restrict file permissions.

3.  **Extract Course Module IDs (`cmid`s):**
    *   This script requires the **Course Module ID (`cmid`)** for each quiz.
    *   Connect to your Moodle database and run the following SQL query (adjust the `mdl_` prefix if necessary):
        ```sql
        SELECT cm.id
        FROM mdl_course_modules cm
        JOIN mdl_modules m ON cm.module = m.id
        WHERE m.name = 'quiz'
        ORDER BY cm.id ASC;
        ```
    *   Save the output of this query to a plain text file. The default filename the script looks for is `quiz_cmids.txt` (as set in `config.ini`), but you can change this in the config or specify a different file using the `-q` command-line option. Each line in the file should contain exactly one `cmid` number.

## Usage

Run the script from your terminal or command prompt.

**Basic usage (using default `config.ini` and default `quiz_cmids.txt` specified within it):**

```bash
python refresh_moodle_stats_requests.py
```

**Specifying the Quiz CMID file via command-line (overrides `quiz_id_file_path` in config):**

```bash
python refresh_moodle_stats_requests.py -q path/to/your_quiz_ids.txt
```

**Specifying a different configuration file:**

```bash
python refresh_moodle_stats_requests.py -C /path/to/other_config.ini
```

**Combining options:**

```bash
python refresh_moodle_stats_requests.py -C /path/to/other_config.ini -q /another/path/to/quiz_ids.txt
```

*(Note: The `-d` / `--delay` command-line argument has been removed. Control delay via `request_delay_seconds` in `config.ini`)*

## Security Considerations

*   **Credentials:** Storing passwords in plain text `config.ini` files has security risks. Ensure the file has strict permissions (readable only by the intended user). Avoid committing this file to version control if it contains real passwords.
*   **SSL Verification (`verify_ssl`):** The default setting in the example `config.ini` (`verify_ssl = false`) disables SSL certificate verification. This is often necessary for Moodle instances using self-signed certificates internally. **Do not** disable verification (`set verify_ssl = true`) if connecting to a Moodle site with a valid, trusted SSL certificate over the public internet, as disabling bypasses an important security check.

## Troubleshooting

*   **Config File Not Found:** Ensure `config.ini` exists in the same directory as the script, or use the `-C` option to specify the correct path. Check for typos.
*   **Configuration Error / Missing Section/Key:** Verify your `config.ini` file structure matches the example. Ensure the `[Moodle]` section and its `base_url`, `username`, and `password` keys exist and have values.
*   **Login Failed:** Double-check username/password in `config.ini`. Verify `base_url` and `login_path` are correct for your Moodle site.
*   **Quiz ID File Not Found:** Check the path specified via `-q` or the `quiz_id_file_path` in `config.ini`. Ensure the file exists at that location.
*   **404 Not Found / Error Visiting Page:**
    *   Confirm you extracted **Course Module IDs (`cmid`s)** using the correct SQL query (Setup Step 3).
    *   Ensure the Moodle user specified in `config.ini` has permission to view the specific quizzes and their reports (`mod/quiz:viewreport`).
    *   Manually try visiting one of the failing URLs in your browser while logged in as the same user to see the exact error.
*   **Session Expired:** If the script runs for a very long time on many IDs, the Moodle session might time out. You may need to run the script in smaller batches by splitting your CMID file.
*   **Connection Errors / SSL Errors:** Check your network connection. Verify `base_url`. If you get SSL errors and have `verify_ssl = true`, ensure your system's certificate store is up-to-date or consider setting `verify_ssl = false` if appropriate for your environment (e.g., internal server with self-signed cert).
```
