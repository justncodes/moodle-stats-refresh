#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import sys
import os
import time
import urllib3
import argparse
import configparser

# --- Argument Parsing ---
parser = argparse.ArgumentParser(
    description="Refresh Moodle quiz statistics by visiting the stats page for each quiz ID using settings from a config file.",
    formatter_class=argparse.RawTextHelpFormatter
)
parser.add_argument(
    '-q', '--quiz-file',
    metavar='QUIZ_ID_FILE', type=str, default=None,
    help="Path to the text file containing Moodle Quiz CMIDs, one per line.\n"
         "Overrides 'quiz_id_file_path' in the config file."
)
parser.add_argument(
    '-C', '--config',
    metavar='CONFIG_FILE', type=str, default='config.ini',
    help="Path to the configuration file (default: config.ini).\n"
         "See script/README for expected format."
)

args = parser.parse_args()

# --- Configuration Loading ---
config_file_path = args.config
print(f"[*] Using configuration file: {config_file_path}")

if not os.path.exists(config_file_path):
    print(f"[!!!] Error: Configuration file not found at '{config_file_path}'.")
    print( "      Please create it. See README.md for the required format.")
    sys.exit(1)

config = configparser.ConfigParser(
    # Defined default values directly here for fallback
    defaults={
        'login_path': '/login/index.php',
        'post_login_check_path': '/my/',
        'quiz_id_file_path': 'quiz_ids.txt', # Default file name if not in config or CLI
        'request_delay_seconds': '0.5',       # Note: read as string initially
        'verify_ssl': 'false'                 # Note: read as string initially
    }
)

# Initialize variables with None or default values
moodle_base_url = None
moodle_username = None
moodle_password = None
login_path = None
post_login_check_path = None
quiz_id_file_path_from_config = None
request_delay_seconds = 0.5
verify_ssl = False

try:
    config.read(config_file_path)

    # === Load [Moodle] section (Required) ===
    if 'Moodle' not in config:
        print(f"[!!!] Error: Missing [Moodle] section in config file '{config_file_path}'.")
        sys.exit(1)

    moodle_base_url = config.get('Moodle', 'base_url', fallback=None)
    moodle_username = config.get('Moodle', 'username', fallback=None)
    moodle_password = config.get('Moodle', 'password', fallback=None)

    # Validate required Moodle settings
    if not moodle_base_url: raise ValueError("'base_url' missing or empty in [Moodle] section.")
    if not moodle_username: raise ValueError("'username' missing or empty in [Moodle] section.")
    if moodle_password is None: raise ValueError("'password' missing in [Moodle] section.")

    print(f"[+] Loaded Moodle Base URL: {moodle_base_url}")
    print(f"[+] Loaded Moodle Username: {moodle_username}")

    # === Load [Paths] section (Optional, uses defaults) ===
    login_path = config.get('Paths', 'login_path') # Uses default from ConfigParser constructor if missing
    post_login_check_path = config.get('Paths', 'post_login_check_path')
    quiz_id_file_path_from_config = config.get('Paths', 'quiz_id_file_path')
    print(f"[*] Login path from config/default: {login_path}")
    print(f"[*] Post-login check path from config/default: {post_login_check_path}")
    print(f"[*] Quiz ID file path from config/default: {quiz_id_file_path_from_config}")

    # === Load [Settings] section (Optional, uses defaults) ===
    try:
        request_delay_seconds = config.getfloat('Settings', 'request_delay_seconds')
        print(f"[*] Request delay from config/default: {request_delay_seconds} seconds")
    except ValueError:
        print(f"[!] Warning: Invalid numeric value for 'request_delay_seconds' in [Settings]. Using default: {request_delay_seconds}")

    try:
        verify_ssl = config.getboolean('Settings', 'verify_ssl')
        print(f"[*] SSL verification from config/default: {verify_ssl}")
    except ValueError:
        print(f"[!] Warning: Invalid boolean value for 'verify_ssl' in [Settings]. Using default: {verify_ssl}")

except configparser.Error as e:
    print(f"[!!!] Error reading or parsing config file '{config_file_path}': {e}")
    sys.exit(1)
except ValueError as e:
     print(f"[!!!] Configuration Error in '{config_file_path}': {e}")
     sys.exit(1)
except Exception as e:
     print(f"[!!!] Unexpected error during configuration loading: {e}")
     sys.exit(1)


# --- Determine Final Quiz ID File Path ---
# Command-line argument takes precedence over config file path
if args.quiz_file:
    quiz_id_file_to_use = args.quiz_file
    print(f"[*] Using Quiz ID file specified via command line: {quiz_id_file_to_use}")
else:
    quiz_id_file_to_use = quiz_id_file_path_from_config
    print(f"[*] Using Quiz ID file from config/default: {quiz_id_file_to_use}")


# --- Construct Full URLs ---
# Ensure paths start with '/' and base_url doesn't end with '/' for clean joining
moodle_base_url = moodle_base_url.rstrip('/')
login_path = '/' + login_path.lstrip('/')
post_login_check_path = '/' + post_login_check_path.lstrip('/')

LOGIN_URL = moodle_base_url + login_path
POST_LOGIN_CHECK_URL = moodle_base_url + post_login_check_path

# --- SSL Verification Handling ---
if not verify_ssl:
    print("[!] Warning: Disabling SSL certificate verification based on config. Use only if necessary.")
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
else:
    print("[*] SSL certificate verification is ENABLED based on config.")
VERIFY_SSL = verify_ssl

# --- Helper Functions ---
def read_quiz_ids_from_file(file_path):
    """Reads quiz IDs (CMIDs) from a text file, one ID per line."""
    if not os.path.isfile(file_path):
        print(f"[!!!] Error: Input file not found at '{file_path}'")
        return None

    quiz_ids = []
    print(f"[*] Reading quiz CMIDs from: {file_path}")
    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'): continue
                try:
                    quiz_id = int(line)
                    quiz_ids.append(quiz_id)
                except ValueError:
                    print(f"[!] Warning: Skipping invalid non-numeric value on line {line_num}: '{line}'")
        if not quiz_ids: print("[!] Warning: No valid quiz CMIDs found in the file.")
        else: print(f"[+] Found {len(quiz_ids)} valid quiz CMIDs.")
        return quiz_ids
    except Exception as e:
        print(f"[!!!] Error reading file '{file_path}': {e}")
        return None

# --- Main Script Logic ---
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
})

try:
    # === Stage 1: Login ===
    print(f"[*] Attempting to access login page: {LOGIN_URL}")
    response_get = session.get(LOGIN_URL, verify=VERIFY_SSL)
    response_get.raise_for_status()
    soup_login = BeautifulSoup(response_get.text, 'html.parser')

    logintoken_input = soup_login.find('input', {'name': 'logintoken'})
    logintoken = logintoken_input['value'] if logintoken_input else None
    if logintoken: print(f"[*] Found logintoken: {logintoken}")
    else: print("[*] No logintoken found on login page (this might be okay).")

    login_payload = { 'username': moodle_username, 'password': moodle_password, }
    if logintoken: login_payload['logintoken'] = logintoken

    print(f"[*] Submitting login credentials for user: {moodle_username}")
    response_post = session.post(LOGIN_URL, data=login_payload, verify=VERIFY_SSL, allow_redirects=True)
    response_post.raise_for_status()

    if LOGIN_URL in response_post.url or login_path in response_post.url:
        error_div_soup = BeautifulSoup(response_post.text, 'html.parser')
        error_div = error_div_soup.find('div', {'id': 'loginerrormessage'}) or \
                    error_div_soup.find('div', class_='loginerrors') or \
                    error_div_soup.find('div', class_='alert-danger')
        error_text = error_div.get_text(strip=True) if error_div else "Unknown reason (check credentials/URL in config)"
        print(f"[!!!] Login Failed! Error: {error_text}.")
        sys.exit(1)
    else:
        print(f"[+] Login successful! Current URL: {response_post.url}")

    # === Stage 2: Check Session Cookie ===
    moodle_session_cookie_name = next((n for n in session.cookies.keys() if 'moodlesession' in n.lower()), None)
    if not moodle_session_cookie_name: print("[!!!] Error: Could not find Moodle session cookie after login."); sys.exit(1)
    print(f"[*] Found Session Cookie Name: {moodle_session_cookie_name}")

    # === Stage 3: Read Quiz IDs ===
    quiz_ids = read_quiz_ids_from_file(quiz_id_file_to_use)
    if quiz_ids is None: sys.exit(1)
    if not quiz_ids: print("[*] No quiz CMIDs to process. Exiting."); sys.exit(0)

    # === Stage 4: Visit Statistics Page for Each Quiz ===
    print(f"\n--- Processing {len(quiz_ids)} Quiz CMIDs ---")
    success_count = 0
    failure_count = 0
    session_expired = False

    for i, quiz_id in enumerate(quiz_ids):
        if session_expired:
            print(f"[*] Skipping remaining quizzes due to detected session expiry.")
            failure_count = len(quiz_ids) - i
            break

        stats_url = f"{moodle_base_url}/mod/quiz/report.php?id={quiz_id}&mode=statistics"
        print(f"[*] Processing CMID: {quiz_id} ({i+1}/{len(quiz_ids)}) - Visiting: {stats_url}")

        try:
            response_stats = session.get(stats_url, verify=VERIFY_SSL, timeout=30)

            if LOGIN_URL in response_stats.url or login_path in response_stats.url:
                print(f"[!!!] Error: Session likely expired. Redirected to login page for CMID {quiz_id}.")
                failure_count += 1; session_expired = True; continue

            response_stats.raise_for_status()

            soup_stats = BeautifulSoup(response_stats.text, 'html.parser')
            error_box = soup_stats.find(class_='errorbox') or soup_stats.find(id='page-login-index') or soup_stats.find(class_='errormessage')
            page_title = soup_stats.title.string.lower() if soup_stats.title else ""

            if error_box or "error" in page_title or "notice" in page_title or "invalid course module id" in response_stats.text.lower() or "you do not have permission" in response_stats.text.lower():
                 print(f"[!] Warning: Potential error/permission issue detected on statistics page for CMID {quiz_id}.")

            print(f"[+] Successfully visited stats page for CMID: {quiz_id}")
            success_count += 1

        except requests.exceptions.Timeout: print(f"[!!!] Error: Request timed out for CMID {quiz_id}."); failure_count += 1
        except requests.exceptions.HTTPError as e:
            print(f"[!!!] HTTP Error for CMID {quiz_id}: {e.response.status_code} {e.response.reason}"); failure_count += 1
            if e.response.status_code in [401, 403]: print("[!] Authentication error detected, assuming session expired."); session_expired = True
        except requests.exceptions.RequestException as e: print(f"[!!!] Network Error for CMID {quiz_id}: {e}"); failure_count += 1
        except Exception as e: print(f"[!!!] Unexpected Error processing CMID {quiz_id}: {e}"); failure_count += 1

        if i < len(quiz_ids) - 1: time.sleep(request_delay_seconds)

except requests.exceptions.SSLError as e:
     print(f"[!!!] SSL Error occurred: {e}")
     print(f"      SSL verification is currently {'DISABLED' if not VERIFY_SSL else 'ENABLED'}.")
except requests.exceptions.ConnectionError as e:
    print(f"[!!!] Connection Error: Could not connect to {moodle_base_url}. Check URL in config and network connection.")
    print(f"      Error details: {e}")
except requests.exceptions.RequestException as e:
    print(f"[!!!] An HTTP error occurred during setup or login: {e}")
    if hasattr(e, 'response') and e.response is not None: print(f"Status Code: {e.response.status_code}\nResponse Body (first 500 chars): {e.response.text[:500]}")
except ImportError as e:
    module_name = str(e).split("'")[-2]; print(f"[!!!] Import Error: {e}. Install missing module: pip install {module_name}")
except Exception as e:
    print(f"[!!!] An unexpected error occurred: {e}")
    import traceback; traceback.print_exc()
finally:
    if 'quiz_ids' in locals() and quiz_ids is not None:
        print("\n--- Processing Summary ---")
        total_attempted = success_count + failure_count
        print(f"Total Quiz CMIDs read: {len(quiz_ids)}")
        print(f"Attempted to process:  {total_attempted}")
        print(f"Successfully visited:  {success_count}")
        print(f"Failed/Skipped:        {failure_count}")

    if 'session' in locals() and session: session.close()
    print("\n[*] Script finished.")