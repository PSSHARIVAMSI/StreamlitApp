# assignments_app.py - Streamlit demo app for Assignment 1 & Assignment 2

import streamlit as st
import pandas as pd
import textwrap
import io, requests

st.set_page_config(page_title="Assignments Demo", layout="centered")


def show_assignment_1():
    """Assignment 1: Json to csv flattening, summarization, visualization."""
    st.subheader("Assignment 1 - Json to csv flattening, Data Summarization & Visualization")

    # ---------- sample code to display ----------
    code_a1 = """
#!/usr/bin/env python3
'''
# Assignment 1 - JSON → CSV pipeline with enrichment & parallelism
# ---------------------------------------------------------------
# •  Flatten each infringing URL to its own row
# •  Add 'domain' and 'ip_address' columns
# •  Parallelise IP-look-ups with ≥ 4 CPUs
# •  Produce three summary tables

# Author: Siva Mani Subrahmanya Hari Vamsi
# Date  : 15-07-2025
'''

import json
import csv
import socket
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import pandas as pd
import re, requests

# -------- CONFIG -------------------------------------------------------------
# Google Drive share‑link → file‑ID → direct‑download URL
DRIVE_FILE_ID = "134U6xLIZUZ9sA1BW-X9TLZtUlEYCvQwz"
INPUT_JSON = (                       # we now pass a URL, not a Path
    f"https://drive.google.com/uc?export=download&id={DRIVE_FILE_ID}"
)
OUTPUT_CSV = Path("flattened_infringing_urls.csv")
N_WORKERS  = 8
TIMEOUT_S  = 3
# -----------------------------------------------------------------------------

def load_json(src: str | Path) -> dict:
    '''
    Load a JSON document from either
      • a local file (Path / str)  - existing behaviour, or
      • an http/https URL          - used for the public Google Drive link.
    '''
    src_str = str(src)

    # 1️⃣ Remote file ----------------------------------------------------------
    if src_str.startswith(("http://", "https://")):
        # Google Drive ‘share’ links need converting to the *download* endpoint
        m = re.search(r"/d/([^/]+)/", src_str)
        if m:
            file_id = m.group(1)
            src_str = f"https://drive.google.com/uc?export=download&id={file_id}"

        # small files (<100 MB) download in one go; large files may need a second
        with requests.Session() as sess:
            r = sess.get(src_str, timeout=30, stream=True)
            # If we hit Drive’s virus‑scan / confirm page, grab the token & resend
            if "content-disposition" not in r.headers:
                for k, v in r.cookies.items():
                    if k.startswith("download_warning"):
                        r = sess.get(src_str, params={"confirm": v}, timeout=30)
                        break
            r.raise_for_status()
            return r.json()

    # 2️⃣ Local file -----------------------------------------------------------
    with Path(src_str).open("r", encoding="utf-8") as f:
        return json.load(f)

def flatten_notices(raw: dict) -> list[dict]:
    '''
    Flatten the nested JSON structure so each infringing URL gets its own
    dictionary (future CSV row). Extracts relevant fields from each notice.
    '''
    rows = []
    for notice in raw.get("notices", []):
        base = {
            "notice_id":  notice.get("id"),
            "title":      notice.get("title"),
            "sender":     notice.get("sender_name"),
            "principal":  notice.get("principal_name"),
            "recipient":  notice.get("recipient_name"),
            "date_sent":  notice.get("date_sent"),
        }

        for work in notice.get("works", []):
            description = work.get("description")
            for item in work.get("infringing_urls", []):
                url = item.get("url")
                rows.append(
                    {
                        **base,
                        "description":    description,
                        "infringing_url": url,
                        "domain":         urlparse(url).netloc.lower(),  # Extract domain from URL
                    }
                )
    return rows


def resolve_ip(domain: str) -> str:
    '''
    Return the IPv4 address for a domain.
    Returns 'N/A' if the lookup fails (e.g., DNS error or timeout).
    '''
    try:
        socket.setdefaulttimeout(TIMEOUT_S)
        return socket.gethostbyname(domain)
    except OSError:
        return "N/A"


def enrich_with_ip(rows: list[dict]) -> None:
    '''
    Perform parallel DNS look-ups using a thread pool.
    Adds an 'ip_address' key to each row in-place.
    Caches results so each domain is only looked up once.
    '''
    unique_domains = {row["domain"] for row in rows}
    ip_cache: dict[str, str] = {}

    # Submit DNS lookups in parallel
    with ThreadPoolExecutor(max_workers=N_WORKERS) as pool:
        future_to_domain = {pool.submit(resolve_ip, d): d for d in unique_domains}
        for future in as_completed(future_to_domain):
            dom = future_to_domain[future]
            ip_cache[dom] = future.result()

    # Assign resolved IPs back to each row
    for row in rows:
        row["ip_address"] = ip_cache[row["domain"]]


def write_csv(rows: list[dict], out_path: Path) -> None:
    '''
    Write the list of dictionaries to a CSV file.
    Raises an error if there is no data.
    '''
    if not rows:
        raise ValueError("No data extracted – check input file.")
    fields = list(rows[0].keys())
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def summarise(rows: list[dict]) -> None:
    '''
    Print three summary tables:
    - Top 5 Principals
    - Top 5 Infringing Domains
    - Top 5 Recipients
    '''
    principals = Counter(r["principal"] for r in rows).most_common(5)
    domains    = Counter(r["domain"]   for r in rows).most_common(5)
    recipients = Counter(r["recipient"] for r in rows).most_common(5)

    print("\nTop 5 Principals:")
    for p, n in principals:
        print(f"  {p:<30}  {n:>6}")

    print("\nTop 5 Infringing Domains:")
    for d, n in domains:
        print(f"  {d:<30}  {n:>6}")

    print("\nTop 5 Recipients:")
    for r, n in recipients:
        print(f"  {r:<30}  {n:>6}")

def main() -> None:
    '''
    Main pipeline:
    - Load JSON data
    - Flatten notices to rows
    - Enrich with IP addresses (parallel DNS)
    - Clean/standardize principal and domain names
    - Print summary insights
    - Write output CSV
    '''
    raw   = load_json(INPUT_JSON)
    rows  = flatten_notices(raw)
    enrich_with_ip(rows)

    df = pd.DataFrame(rows)
    def tidy_principal(name: str) -> str:
        '''
        Standardize principal names: lowercase, remove punctuation,
        remove 'inc', collapse whitespace, and title-case.
        '''
        if pd.isna(name):
            return "Unknown"
        n = name.lower()
        n = re.sub(r'[,.\']', '', n)          # remove punctuation
        n = n.replace(' inc', '').strip()
        n = re.sub(r'\s+', ' ', n)
        return n.title()

    df["principal_clean"] = df["principal"].apply(tidy_principal)

    def root_domain(d: str) -> str:
        '''
        Extract the root domain (last two labels) and remove 'www.' prefix.
        '''
        if pd.isna(d):
            return "unknown"
        d = d.lower()
        d = re.sub(r'^www\d*\.', '', d)       # drop www., www2. etc.
        return '.'.join(d.split('.')[-2:])    # keep last two labels

    df["root_domain"] = df["domain"].apply(root_domain)

    print("\n🔸 Top Principals (cleaned):")
    print(df["principal_clean"].value_counts().head(10))

    print("\n🔸 Top Root Domains:")
    print(df["root_domain"].value_counts().head(10))

    # 2a. Notice volume over time (monthly trend)
    df["month"] = pd.to_datetime(df["date_sent"], utc=True).dt.tz_localize(None).dt.to_period("M")

    trend = df.groupby("month").size()
    print("\n🔸 Monthly notice volume (last 12):")
    print(trend.tail(12))

    # 2b. IP addresses hosting many distinct domains
    ip_hosting = (df.groupby("ip_address")["root_domain"]
                    .nunique()
                    .sort_values(ascending=False)
                    .head(10))
    ip_hosting = ip_hosting[ip_hosting.index != "N/A"]

    print("\n🔸 IPs hosting the most *unique* infringing domains:")
    print(ip_hosting)

    # Write the enriched and flattened data to CSV
    write_csv(rows, OUTPUT_CSV)

print(f"\n✅  CSV written to: {OUTPUT_CSV.resolve()}")

if __name__ == "__main__":
    main()
"""
    with st.expander("⬇️ Show Python code"):
        st.code(code_a1, language="python")

    # ---------- execute the code ----------
    import json
    import csv
    import socket
    from pathlib import Path
    from urllib.parse import urlparse
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from collections import Counter
    import pandas as pd
    import re, requests

    # -------- CONFIG -------------------------------------------------------------
    # Google Drive share‑link → file‑ID → direct‑download URL
    DRIVE_FILE_ID = "134U6xLIZUZ9sA1BW-X9TLZtUlEYCvQwz"
    INPUT_JSON = (                       # we now pass a URL, not a Path
        f"https://drive.google.com/uc?export=download&id={DRIVE_FILE_ID}"
    )
    OUTPUT_CSV = Path("flattened_infringing_urls.csv")
    N_WORKERS  = 8
    TIMEOUT_S  = 3
    # -----------------------------------------------------------------------------

    def load_json(src: str | Path) -> dict:
        '''
        Load a JSON document from either
        • a local file (Path / str)  - existing behaviour, or
        • an http/https URL          - used for the public Google Drive link.
        '''
        src_str = str(src)

        # 1️⃣ Remote file ----------------------------------------------------------
        if src_str.startswith(("http://", "https://")):
            # Google Drive ‘share’ links need converting to the *download* endpoint
            m = re.search(r"/d/([^/]+)/", src_str)
            if m:
                file_id = m.group(1)
                src_str = f"https://drive.google.com/uc?export=download&id={file_id}"

            # small files (<100 MB) download in one go; large files may need a second
            with requests.Session() as sess:
                r = sess.get(src_str, timeout=30, stream=True)
                # If we hit Drive’s virus‑scan / confirm page, grab the token & resend
                if "content-disposition" not in r.headers:
                    for k, v in r.cookies.items():
                        if k.startswith("download_warning"):
                            r = sess.get(src_str, params={"confirm": v}, timeout=30)
                            break
                r.raise_for_status()
                return r.json()

        # 2️⃣ Local file -----------------------------------------------------------
        with Path(src_str).open("r", encoding="utf-8") as f:
            return json.load(f)

    def flatten_notices(raw: dict) -> list[dict]:
        '''
        Flatten the nested JSON structure so each infringing URL gets its own
        dictionary (future CSV row). Extracts relevant fields from each notice.
        '''
        rows = []
        for notice in raw.get("notices", []):
            base = {
                "notice_id":  notice.get("id"),
                "title":      notice.get("title"),
                "sender":     notice.get("sender_name"),
                "principal":  notice.get("principal_name"),
                "recipient":  notice.get("recipient_name"),
                "date_sent":  notice.get("date_sent"),
            }

            for work in notice.get("works", []):
                description = work.get("description")
                for item in work.get("infringing_urls", []):
                    url = item.get("url")
                    rows.append(
                        {
                            **base,
                            "description":    description,
                            "infringing_url": url,
                            "domain":         urlparse(url).netloc.lower(),  # Extract domain from URL
                        }
                    )
        return rows


    def resolve_ip(domain: str) -> str:
        '''
        Return the IPv4 address for a domain.
        Returns 'N/A' if the lookup fails (e.g., DNS error or timeout).
        '''
        try:
            socket.setdefaulttimeout(TIMEOUT_S)
            return socket.gethostbyname(domain)
        except OSError:
            return "N/A"


    def enrich_with_ip(rows: list[dict]) -> None:
        '''
        Perform parallel DNS look-ups using a thread pool.
        Adds an 'ip_address' key to each row in-place.
        Caches results so each domain is only looked up once.
        '''
        unique_domains = {row["domain"] for row in rows}
        ip_cache: dict[str, str] = {}

        # Submit DNS lookups in parallel
        with ThreadPoolExecutor(max_workers=N_WORKERS) as pool:
            future_to_domain = {pool.submit(resolve_ip, d): d for d in unique_domains}
            for future in as_completed(future_to_domain):
                dom = future_to_domain[future]
                ip_cache[dom] = future.result()

        # Assign resolved IPs back to each row
        for row in rows:
            row["ip_address"] = ip_cache[row["domain"]]


    def write_csv(rows: list[dict], out_path: Path) -> None:
        '''
        Write the list of dictionaries to a CSV file.
        Raises an error if there is no data.
        '''
        if not rows:
            raise ValueError("No data extracted – check input file.")
        fields = list(rows[0].keys())
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)


    def summarise(rows: list[dict]) -> None:
        '''
        st.write three summary tables:
        - Top 5 Principals
        - Top 5 Infringing Domains
        - Top 5 Recipients
        '''
        principals = Counter(r["principal"] for r in rows).most_common(5)
        domains    = Counter(r["domain"]   for r in rows).most_common(5)
        recipients = Counter(r["recipient"] for r in rows).most_common(5)

        st.write("\nTop 5 Principals:")
        for p, n in principals:
            st.write(f"  {p:<30}  {n:>6}")

        st.write("\nTop 5 Infringing Domains:")
        for d, n in domains:
            st.write(f"  {d:<30}  {n:>6}")

        st.write("\nTop 5 Recipients:")
        for r, n in recipients:
            st.write(f"  {r:<30}  {n:>6}")

    def main() -> None:
        '''
        Main pipeline:
        - Load JSON data
        - Flatten notices to rows
        - Enrich with IP addresses (parallel DNS)
        - Clean/standardize principal and domain names
        - st.ite summary insights
        - Write output CSV
        '''
        raw   = load_json(INPUT_JSON)
        rows  = flatten_notices(raw)
        enrich_with_ip(rows)

        df = pd.DataFrame(rows)
        def tidy_principal(name: str) -> str:
            '''
            Standardize principal names: lowercase, remove punctuation,
            remove 'inc', collapse whitespace, and title-case.
            '''
            if pd.isna(name):
                return "Unknown"
            n = name.lower()
            n = re.sub(r'[,.\']', '', n)          # remove punctuation
            n = n.replace(' inc', '').strip()
            n = re.sub(r'\s+', ' ', n)
            return n.title()

        df["principal_clean"] = df["principal"].apply(tidy_principal)

        def root_domain(d: str) -> str:
            '''
            Extract the root domain (last two labels) and remove 'www.' prefix.
            '''
            if pd.isna(d):
                return "unknown"
            d = d.lower()
            d = re.sub(r'^www\d*\.', '', d)       # drop www., www2. etc.
            return '.'.join(d.split('.')[-2:])    # keep last two labels

        df["root_domain"] = df["domain"].apply(root_domain)
        df_final = pd.DataFrame(rows)          # turn list‑of‑dicts into a DataFrame
        st.subheader("Csv File Preview")     
        st.dataframe(df_final.head(), use_container_width=True)

        csv_bytes = df_final.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download CSV",
            data=csv_bytes,
            file_name="flattened_infringing_urls.csv",
            mime="text/csv",
        )

        st.write("\n🔸 Top Root Domains:")
        st.write(df["root_domain"].value_counts().head(10))
        st.bar_chart(df["root_domain"].value_counts().head(10), x_label="Domain Name", y_label="Count")

        # IP addresses hosting many distinct domains
        ip_hosting = (df.groupby("ip_address")["root_domain"]
                        .nunique()
                        .sort_values(ascending=False)
                        .head(10))
        ip_hosting = ip_hosting[ip_hosting.index != "N/A"]

        st.write("\n🔸 IPs hosting the most *unique* infringing domains:")
        st.write(ip_hosting)
        st.bar_chart(ip_hosting, x_label="Unique Domains Hosted", y_label="IP Address",horizontal=True)

        st.write("\n🔸 Top Principals (cleaned):")
        st.write(df["principal_clean"].value_counts().head(10))

        # Write the enriched and flattened data to CSV
        write_csv(rows, OUTPUT_CSV)
        
        # # Notice volume over time (monthly trend)
        # df["month"] = pd.to_datetime(df["date_sent"], utc=True).dt.tz_localize(None).dt.to_period("M")

        # trend = df.groupby("month").size()
        # st.write("\n🔸 Monthly notice volume (last 12):")
        # st.write(trend.tail(12))

    st.write("Summarizations")
    #st.write(f"\n✅  CSV written to: {OUTPUT_CSV.resolve()}")

    if __name__ == "__main__":
        main()

def show_assignment_2():
    """Render Assignment 2 with selectable approaches."""
    st.subheader("Assignment 2 - Web Scraping & Data Extraction")

    approach = st.radio("Select an approach:", ("Approach 1 - Manual", "Approach 2 - Selenium"))
    st.write("The Web Page to scrape is: https://journals.sagepub.com/toc/JMX/current")
    if approach.startswith("Approach 1"):
        _show_approach_1()
    else:
        _show_approach_2()


def _show_approach_1():
    """Manual web scraping using downloaded html in Google Drive"""
    st.write("**Approach 1** - Manual web scraping using downloaded html file in Google Drive")

    code_rf = """
import csv, re, os ,requests
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

def _find_first_publish_date(elem) -> str:
    #Look anywhere inside *elem* for text like First published online November 16, 2024' or 'First Published January 3 2025'
    text = elem.get_text(" ", strip=True)
    # Search for common publish date patterns in the text
    m = re.search(
        r'First\s+published(?:\s+online)?\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        text, re.I
    )
    return m.group(1) if m else ''

def _clean_abstract(raw: str) -> str:
    # Remove site-specific clutter such as 'Show abstract', 'Hide abstract', 'Preview abstract', and a leading 'Abstract:' label.
    # 1) Remove show/hide/preview toggles from abstract text
    txt = re.sub(r'\b(?:Show|Hide|Preview|Full)\s*abstract\b', '', raw, flags=re.I)

    # 2) Remove a leading 'Abstract:' label (sometimes repeated)
    txt = re.sub(r'^\s*Abstract\s*:?\s*', '', txt, flags=re.I)

    # 3) Collapse extra whitespace
    return re.sub(r'\s+', ' ', txt).strip()

def _canonical_doi(href: str) -> str:
    # Return 'https://doi.org/<doi>' if a DOI pattern is present,otherwise return the original href.
    m = re.search(r'(10\.\d{4,9}/[^\s/#?]+)', href)  # DOI core pattern
    return f"https://doi.org/{m.group(1)}" if m else href

def extract_article_data(container):
    # Extract article data from a container element.
    article_data = {
        'title':     '',
        'authors':   '',
        'date':      '',
        'doi':       '',
        'abstract':  ''
    }

    # ----- title ------------------------------------------
    # Try multiple selectors to find the article title
    for selector in [
        'h3.item-title','h4.item-title','h5.item-title','div.art_title',
        'div.hlFld-Title','a.ref.nowrap','.tocHeading',
        'h3','h4','h5','h2','[class*="title"]'
    ]:
        title_elem = container.select_one(selector)
        if title_elem:
            raw = title_elem.get_text(" ", strip=True).replace("\xa0", " ")
            article_data['title'] = re.sub(r'\s+', ' ', raw).strip()
            break

    # ----- authors -----
    # Try multiple selectors to find the authors
    for selector in [
        'div.contrib','div.contributors','div.author','div.authors',
        'span.hlFld-ContribAuthor','div.art_authors',
        '[class*="contrib"]','[class*="author"]'
    ]:
        authors_elem = container.select_one(selector)
        if authors_elem:
            # Separate child nodes with ", " and normalize whitespace
            authors_txt = authors_elem.get_text(", ", strip=True)
            article_data['authors'] = re.sub(r'\s+', ' ', authors_txt).strip(" ,")
            break

    # ----- date ➊: try quick CSS selectors first -----
    # Try to find the publication date using common selectors
    for selector in [
        'div.pub-date','div.published-date','span.pub-date',
        'div.date','[class*="date"]','[class*="publish"]'
    ]:
        date_elem = container.select_one(selector)
        if date_elem and date_elem.get_text(strip=True):
            article_data['date'] = date_elem.get_text(strip=True)
            break

    # ----- date ➋: fallback - scan for “First published online …” -----
    # If no date found, look for a "First published" pattern in the text
    if not article_data['date']:
        article_data['date'] = _find_first_publish_date(container)

    # ---------- DOI ----------
    # Try to find a DOI link in the container
    doi = ''
    doi_elem = container.find('a', href=re.compile(r'doi\.org|/doi/'))
    if doi_elem:
        doi = _canonical_doi(doi_elem.get('href', ''))

    article_data['doi'] = doi

    # ---------- ABSTRACT ----------
    # Try multiple selectors to find the abstract
    abstract = ''
    for selector in [
        'div.abstract' , 'div.abstractSection' , 'div.hlFld-Abstract',
        'p.abstract'   , '[class*="abstract"]'
    ]:
        elem = container.select_one(selector)
        if elem:
            abstract = _clean_abstract(elem.get_text(" ", strip=True))
            if abstract:                               # non-empty after cleaning
                break

    article_data['abstract'] = abstract

    return article_data

def extract_articles_from_soup(soup):
    #Extract articles from BeautifulSoup object with comprehensive selectors
    
    articles = []
    
    # SAGE journal specific selectors for article containers
    article_selectors = [
        'div.issue-item',
        'div.issue-item-container',
        'div.article-list-item',
        'article.item',
        'div.hlFld-Fulltext',
        'div.tocHeading',
        'div.art_title',
        'div[class*="issue-item"]',
        'div[class*="article"]',
        'li.item',
        'div.item'
    ]
    
    article_containers = []
    # Try each selector until articles are found
    for selector in article_selectors:
        containers = soup.select(selector)
        if containers:
            article_containers = containers
            print(f"Found {len(containers)} articles using selector: {selector}")
            break
    
    # If no containers found, try broader search for potential article containers
    if not article_containers:
        # Look for any element that might contain article info
        potential_containers = soup.find_all(['div', 'article', 'li'], 
                                        string=re.compile(r'doi|author|abstract|volume|issue', re.I))
        article_containers = potential_containers[:20]  # Limit to avoid too many false positives
    
    # Extract data from each article container
    for container in article_containers:
        article_data = extract_article_data(container)
        if article_data['title']:  # Only add if we have a title
            articles.append(article_data)
    
    return articles

def process_manual_html(html_file_path):
    # Process manually saved HTML file from the journal page
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        return extract_articles_from_soup(soup)
        
    except Exception as e:
        print(f"Error processing manual HTML file: {e}")
        return []

def save_to_csv(articles, filename='journal_articles.csv'):
    # Save articles to CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['title', 'authors', 'date', 'doi', 'abstract']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for article in articles:
            writer.writerow(article)
    
    print(f"Saved {len(articles)} articles to {filename}")

def _google_drive_id(url: str) -> str:
    # Extract the file-ID from any Google-Drive share link.
    # 1) pattern “.../d/<ID>/view”
    m = re.search(r'/d/([0-9A-Za-z_-]{10,})', url)
    if m:
        return m.group(1)

    # 2) fallback — check ?id=<ID>
    qs = parse_qs(urlparse(url).query)
    return qs.get('id', [''])[0]          # returns '' if 'id' not present

def fetch_html_from_gdrive(url: str) -> str:
    # Download the *raw* file content from a public Google-Drive link. Returns HTML text.
    file_id = _google_drive_id(url)
    if not file_id:
        raise ValueError("❌ Couldn't find a file ID in the provided link.")

    # direct-download endpoint
    dl_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    resp = requests.get(dl_url, headers={'User-Agent': 'Mozilla/5.0'})
    resp.raise_for_status()           # 4xx / 5xx -> exception
    return resp.text                  # HTML string

def main():
    # Main function to orchestrate the scraping and saving process. Looks for HTML file in the Google Drive, extracts articles, and saves them to CSV.

    print("=" * 60)
    print("GOOGLE-DRIVE JOURNAL ARTICLE SCRAPER")
    print("=" * 60)

    gdrive_url = (
        "https://drive.google.com/file/d/1At1Y8CbwlInSQC5fbMvyExklEEKvctli/view?usp=sharing"
    )
    try:
        print("Downloading HTML from Google Drive …")
        html_content = fetch_html_from_gdrive(gdrive_url)

        soup = BeautifulSoup(html_content, 'html.parser')
        articles = extract_articles_from_soup(soup)

        if not articles:
            print("❌ No articles found — did the HTML structure change?")
            return

        print("\nArticle Summary:")
        print("-" * 60)
        for i, article in enumerate(articles, 1):
            print(f"{i}. {article['title']}")
            print(f"   Authors: {article['authors']}")
            print(f"   Date: {article['date']}")
            print(f"   DOI: {article['doi']}")
            abstract_preview = article['abstract'][:150] + "..." if len(article['abstract']) > 150 else article['abstract']
            print(f"   Abstract: {abstract_preview}")
            print()
        
        print(f"✓ SUCCESS: scraped {len(articles)} articles")
        save_to_csv(articles)

    except Exception as exc:
        print(f"Download / parse error: {exc}")

if __name__ == "__main__":
    main()
"""
    with st.expander("⬇️ Show Python code"):
        st.code(code_rf, language="python")

    import csv, re, os ,requests
    from urllib.parse import urlparse, parse_qs
    from bs4 import BeautifulSoup

    def _find_first_publish_date(elem) -> str:
        #Look anywhere inside *elem* for text like First published online November 16, 2024' or 'First Published January 3 2025'
        text = elem.get_text(" ", strip=True)
        # Search for common publish date patterns in the text
        m = re.search(
            r'First\s+published(?:\s+online)?\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
            text, re.I
        )
        return m.group(1) if m else ''

    def _clean_abstract(raw: str) -> str:
        # Remove site-specific clutter such as 'Show abstract', 'Hide abstract', 'Preview abstract', and a leading 'Abstract:' label.
        # 1) Remove show/hide/preview toggles from abstract text
        txt = re.sub(r'\b(?:Show|Hide|Preview|Full)\s*abstract\b', '', raw, flags=re.I)

        # 2) Remove a leading 'Abstract:' label (sometimes repeated)
        txt = re.sub(r'^\s*Abstract\s*:?\s*', '', txt, flags=re.I)

        # 3) Collapse extra whitespace
        return re.sub(r'\s+', ' ', txt).strip()

    def _canonical_doi(href: str) -> str:
        # Return 'https://doi.org/<doi>' if a DOI pattern is present,otherwise return the original href.
        m = re.search(r'(10\.\d{4,9}/[^\s/#?]+)', href)  # DOI core pattern
        return f"https://doi.org/{m.group(1)}" if m else href

    def extract_article_data(container):
        # Extract article data from a container element.
        article_data = {
            'title':     '',
            'authors':   '',
            'date':      '',
            'doi':       '',
            'abstract':  ''
        }

        # ----- title ------------------------------------------
        # Try multiple selectors to find the article title
        for selector in [
            'h3.item-title','h4.item-title','h5.item-title','div.art_title',
            'div.hlFld-Title','a.ref.nowrap','.tocHeading',
            'h3','h4','h5','h2','[class*="title"]'
        ]:
            title_elem = container.select_one(selector)
            if title_elem:
                raw = title_elem.get_text(" ", strip=True).replace("\xa0", " ")
                article_data['title'] = re.sub(r'\s+', ' ', raw).strip()
                break

        # ----- authors -----
        # Try multiple selectors to find the authors
        for selector in [
            'div.contrib','div.contributors','div.author','div.authors',
            'span.hlFld-ContribAuthor','div.art_authors',
            '[class*="contrib"]','[class*="author"]'
        ]:
            authors_elem = container.select_one(selector)
            if authors_elem:
                # Separate child nodes with ", " and normalize whitespace
                authors_txt = authors_elem.get_text(", ", strip=True)
                article_data['authors'] = re.sub(r'\s+', ' ', authors_txt).strip(" ,")
                break

        # ----- date ➊: try quick CSS selectors first -----
        # Try to find the publication date using common selectors
        for selector in [
            'div.pub-date','div.published-date','span.pub-date',
            'div.date','[class*="date"]','[class*="publish"]'
        ]:
            date_elem = container.select_one(selector)
            if date_elem and date_elem.get_text(strip=True):
                article_data['date'] = date_elem.get_text(strip=True)
                break

        # ----- date ➋: fallback - scan for “First published online …” -----
        # If no date found, look for a "First published" pattern in the text
        if not article_data['date']:
            article_data['date'] = _find_first_publish_date(container)

        # ---------- DOI ----------
        # Try to find a DOI link in the container
        doi = ''
        doi_elem = container.find('a', href=re.compile(r'doi\.org|/doi/'))
        if doi_elem:
            doi = _canonical_doi(doi_elem.get('href', ''))

        article_data['doi'] = doi

        # ---------- ABSTRACT ----------
        # Try multiple selectors to find the abstract
        abstract = ''
        for selector in [
            'div.abstract' , 'div.abstractSection' , 'div.hlFld-Abstract',
            'p.abstract'   , '[class*="abstract"]'
        ]:
            elem = container.select_one(selector)
            if elem:
                abstract = _clean_abstract(elem.get_text(" ", strip=True))
                if abstract:                               # non-empty after cleaning
                    break

        article_data['abstract'] = abstract

        return article_data

    def extract_articles_from_soup(soup):
        #Extract articles from BeautifulSoup object with comprehensive selectors
        
        articles = []
        
        # SAGE journal specific selectors for article containers
        article_selectors = [
            'div.issue-item',
            'div.issue-item-container',
            'div.article-list-item',
            'article.item',
            'div.hlFld-Fulltext',
            'div.tocHeading',
            'div.art_title',
            'div[class*="issue-item"]',
            'div[class*="article"]',
            'li.item',
            'div.item'
        ]
        
        article_containers = []
        # Try each selector until articles are found
        for selector in article_selectors:
            containers = soup.select(selector)
            if containers:
                article_containers = containers
                st.write(f"Found {len(containers)} articles using selector: {selector}")
                break
        
        # If no containers found, try broader search for potential article containers
        if not article_containers:
            # Look for any element that might contain article info
            potential_containers = soup.find_all(['div', 'article', 'li'], 
                                            string=re.compile(r'doi|author|abstract|volume|issue', re.I))
            article_containers = potential_containers[:20]  # Limit to avoid too many false positives
        
        # Extract data from each article container
        for container in article_containers:
            article_data = extract_article_data(container)
            if article_data['title']:  # Only add if we have a title
                articles.append(article_data)
        
        return articles

    def process_manual_html(html_file_path):
        # Process manually saved HTML file from the journal page
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            return extract_articles_from_soup(soup)
            
        except Exception as e:
            st.write(f"Error processing manual HTML file: {e}")
            return []

    def save_to_csv(articles, filename='journal_articles.csv'):
        # Save articles to CSV file
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['title', 'authors', 'date', 'doi', 'abstract']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for article in articles:
                writer.writerow(article)
        
        st.write(f"Saved {len(articles)} articles to {filename}")

    def _google_drive_id(url: str) -> str:
        # Extract the file-ID from any Google-Drive share link.
        # 1) pattern “.../d/<ID>/view”
        m = re.search(r'/d/([0-9A-Za-z_-]{10,})', url)
        if m:
            return m.group(1)

        # 2) fallback — check ?id=<ID>
        qs = parse_qs(urlparse(url).query)
        return qs.get('id', [''])[0]          # returns '' if 'id' not present

    def fetch_html_from_gdrive(url: str) -> str:
        # Download the *raw* file content from a public Google-Drive link. Returns HTML text.
        file_id = _google_drive_id(url)
        if not file_id:
            raise ValueError("❌ Couldn't find a file ID in the provided link.")

        # direct-download endpoint
        dl_url = f"https://drive.google.com/uc?export=download&id={file_id}"

        resp = requests.get(dl_url, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()           # 4xx / 5xx -> exception
        return resp.text                  # HTML string

    def main():
        # Main function to orchestrate the scraping and saving process. Looks for HTML file in the Google Drive, extracts articles, and saves them to CSV.

        st.write("=" * 60)
        st.write("GOOGLE-DRIVE JOURNAL ARTICLE SCRAPER")
        st.write("=" * 60)

        gdrive_url = (
            "https://drive.google.com/file/d/1At1Y8CbwlInSQC5fbMvyExklEEKvctli/view?usp=sharing"
        )
        try:
            st.write("Downloading HTML from Google Drive …")
            html_content = fetch_html_from_gdrive(gdrive_url)

            soup = BeautifulSoup(html_content, 'html.parser')
            articles = extract_articles_from_soup(soup)

            if not articles:
                st.write("❌ No articles found — did the HTML structure change?")
                return

            st.write("\nArticle Summary:")
            st.write("-" * 60)
            for i, article in enumerate(articles, 1):
                st.write(f"{i}. {article['title']}")
                st.write(f"   Authors: {article['authors']}")
                st.write(f"   Date: {article['date']}")
                st.write(f"   DOI: {article['doi']}")
                abstract_preview = article['abstract'][:150] + "..." if len(article['abstract']) > 150 else article['abstract']
                st.write(f"   Abstract: {abstract_preview}")
                st.write()
            
            st.write(f"✓ SUCCESS: scraped {len(articles)} articles")
            #save_to_csv(articles)
            df = pd.DataFrame(articles)          # turn list‑of‑dicts into a DataFrame
            st.subheader("Scraped Articles")     
            st.dataframe(df, use_container_width=True)

            csv_bytes = df.to_csv(index=False).encode("utf‑8")
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_bytes,
                file_name="articles.csv",
                mime="text/csv",
            )

        except Exception as exc:
            st.write(f"Download / parse error: {exc}")

    if __name__ == "__main__":
        main()


def _show_approach_2():
    """Parametric sine-squared curve as a quick demo."""
    st.subheader("Approach 2 - Using Selenium for Web Scraping")

    code_plot = """
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import csv
import re
import time

def setup_driver():
    # Set up Chrome driver with options to bypass anti-bot detection
    chrome_options = Options()
    
    # Anti-detection options
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_argument("--disable-javascript")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # User agent
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Comment out the next line if you want to see the browser window
    chrome_options.add_argument("--headless")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Execute script to hide webdriver property
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def _find_first_publish_date(elem) -> str:
    #Look anywhere inside *elem* for text like First published online November 16, 2024' or 'First Published January 3 2025'
    text = elem.get_text(" ", strip=True)
    # Search for common publish date patterns in the text
    m = re.search(
        r'First\s+published(?:\s+online)?\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        text, re.I
    )
    return m.group(1) if m else ''

def _clean_abstract(raw: str) -> str:
    # Remove site-specific clutter such as 'Show abstract', 'Hide abstract', 'Preview abstract', and a leading 'Abstract:' label.
    # 1) Remove show/hide/preview toggles from abstract text
    txt = re.sub(r'\b(?:Show|Hide|Preview|Full)\s*abstract\b', '', raw, flags=re.I)

    # 2) Remove a leading 'Abstract:' label (sometimes repeated)
    txt = re.sub(r'^\s*Abstract\s*:?\s*', '', txt, flags=re.I)

    # 3) Collapse extra whitespace
    return re.sub(r'\s+', ' ', txt).strip()

def _canonical_doi(href: str) -> str:
    # Return 'https://doi.org/<doi>' if a DOI pattern is present,otherwise return the original href.
    m = re.search(r'(10\.\d{4,9}/[^\s/#?]+)', href)  # DOI core pattern
    return f"https://doi.org/{m.group(1)}" if m else href

def extract_article_data(container):
    #Extract article data from a container element with SAGE-specific selectors
    article_data = {
        'title': '',
        'authors': '',
        'date': '',
        'doi': '',
        'abstract': ''
    }
    
    # Title extraction - SAGE specific
    title_selectors = [
        'h3.item-title',
        'h4.item-title', 
        'h5.item-title',
        'div.art_title',
        'div.hlFld-Title',
        'a.ref.nowrap',
        '.tocHeading',
        'h3', 'h4', 'h5', 'h2',
        '[class*="title"]'
    ]
    
    for selector in title_selectors:
        title_elem = container.select_one(selector)
        if title_elem:
            article_data['title'] = title_elem.get_text(strip=True)
            break
    
    # ----- authors -----
    # Try multiple selectors to find the authors
    for selector in [
        'div.contrib','div.contributors','div.author','div.authors',
        'span.hlFld-ContribAuthor','div.art_authors',
        '[class*="contrib"]','[class*="author"]'
    ]:
        authors_elem = container.select_one(selector)
        if authors_elem:
            # Separate child nodes with ", " and normalize whitespace
            authors_txt = authors_elem.get_text(", ", strip=True)
            article_data['authors'] = re.sub(r'\s+', ' ', authors_txt).strip(" ,")
            break
    
    # ----- date ➊: try quick CSS selectors first -----
    # Try to find the publication date using common selectors
    for selector in [
        'div.pub-date','div.published-date','span.pub-date',
        'div.date','[class*="date"]','[class*="publish"]'
    ]:
        date_elem = container.select_one(selector)
        if date_elem and date_elem.get_text(strip=True):
            article_data['date'] = date_elem.get_text(strip=True)
            break

    # ----- date ➋: fallback - scan for “First published online …” -----
    # If no date found, look for a "First published" pattern in the text
    if not article_data['date']:
        article_data['date'] = _find_first_publish_date(container)

    # ---------- DOI ----------
    # Try to find a DOI link in the container
    doi = ''
    doi_elem = container.find('a', href=re.compile(r'doi\.org|/doi/'))
    if doi_elem:
        doi = _canonical_doi(doi_elem.get('href', ''))

    article_data['doi'] = doi
    
  # ---------- ABSTRACT ----------
    # Try multiple selectors to find the abstract
    abstract = ''
    for selector in [
        'div.abstract' , 'div.abstractSection' , 'div.hlFld-Abstract',
        'p.abstract'   , '[class*="abstract"]'
    ]:
        elem = container.select_one(selector)
        if elem:
            abstract = _clean_abstract(elem.get_text(" ", strip=True))
            if abstract:                               # non-empty after cleaning
                break

    article_data['abstract'] = abstract
    
    return article_data

def extract_articles_from_soup(soup):
    # Extract articles from BeautifulSoup object with comprehensive selectors
    articles = []
    
    # SAGE journal specific selectors
    article_selectors = [
        'div.issue-item',
        'div.issue-item-container',
        'div.article-list-item',
        'article.item',
        'div.hlFld-Fulltext',
        'div.tocHeading',
        'div.art_title',
        'div[class*="issue-item"]',
        'div[class*="article"]',
        'li.item',
        'div.item'
    ]
    
    article_containers = []
    for selector in article_selectors:
        containers = soup.select(selector)
        if containers:
            article_containers = containers
            print(f"Found {len(containers)} articles using selector: {selector}")
            break
    
    # If no containers found, try broader search
    if not article_containers:
        # Look for any element that might contain article info
        potential_containers = soup.find_all(['div', 'article', 'li'], 
                                           string=re.compile(r'doi|author|abstract|volume|issue', re.I))
        article_containers = potential_containers[:20]  # Limit to avoid too many false positives
        print(f"Using broader search, found {len(article_containers)} potential containers")
    
    for container in article_containers:
        article_data = extract_article_data(container)
        if article_data['title']:  # Only add if we have a title
            articles.append(article_data)
    
    return articles

def scrape_with_selenium(url):
    # Use Selenium to scrape the journal page
    
    driver = None
    try:
        print(f"Setting up Chrome driver...")
        driver = setup_driver()
        
        print(f"Navigating to: {url}")
        driver.get(url)
        
        # Wait for page to load
        print("Waiting for page to load...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Additional wait for dynamic content
        time.sleep(3)
        
        print("Page loaded successfully. Extracting content...")
        
        # Get page source
        html_content = driver.page_source
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract articles
        articles = extract_articles_from_soup(soup)
        
        return articles
        
    except Exception as e:
        print(f"Selenium error: {e}")
        return []
    finally:
        if driver:
            driver.quit()

def save_to_csv(articles, filename='journal_articles_sel.csv'):
    # Save articles to CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['title', 'authors', 'date', 'doi', 'abstract']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for article in articles:
            writer.writerow(article)
    
    print(f"Saved {len(articles)} articles to {filename}")

def main():
    url = "https://journals.sagepub.com/toc/JMX/current"
    
    print("=" * 60)
    print("SELENIUM JOURNAL ARTICLE SCRAPER")
    print("=" * 60)
    print(f"Target URL: {url}")
    print()
    
    # Scrape using Selenium
    articles = scrape_with_selenium(url)
    
    if articles:
        print(f"\n✓ SUCCESS: Found {len(articles)} articles")
        save_to_csv(articles)
        
        print("\nArticle Summary:")
        print("-" * 60)
        for i, article in enumerate(articles, 1):
            print(f"{i}. {article['title']}")
            print(f"   Authors: {article['authors']}")
            print(f"   Date: {article['date']}")
            print(f"   DOI: {article['doi']}")
            abstract_preview = article['abstract'][:150] + "..." if len(article['abstract']) > 150 else article['abstract']
            print(f"   Abstract: {abstract_preview}")
            print()
        
        print(f"✓ Data saved to: journal_articles_sel.csv")
        
    else:
        print("\n❌ NO ARTICLES FOUND")
        print("=" * 60)
        print("Possible issues:")
        print("1. ChromeDriver not installed or not in PATH")
        print("2. Website structure changed")
        print("3. Anti-bot protection still blocking")
        print()
        print("Solutions:")
        print("1. Make sure ChromeDriver is installed:")
        print("   - Download from: https://chromedriver.chromium.org/")
        print("   - Add to PATH or place in same directory as script")
        print("2. Try removing --headless flag to see what's happening")
        print("3. Try the manual HTML approach instead")
        print("=" * 60)

if __name__ == "__main__":
    main()
"""
    with st.expander("⬇️ Show Python code"):
        st.code(code_plot, language="python")

    LOG_TEXT = textwrap.dedent(r"""
                           ============================================================
SELENIUM JOURNAL ARTICLE SCRAPER
============================================================
Target URL: https://journals.sagepub.com/toc/JMX/current

Setting up Chrome driver...

DevTools listening on ws://127.0.0.1:51886/devtools/browser/0403aab4-8b12-46e2-b42c-115d4ef1e36e
Navigating to: https://journals.sagepub.com/toc/JMX/current
Waiting for page to load...
[36112:10560:0715/135615.923:ERROR:net\socket\ssl_client_socket_impl.cc:896] handshake failed; returned -1, SSL error code 1, net_error -200
Page loaded successfully. Extracting content...
Found 8 articles using selector: div.issue-item
WARNING: All log messages before absl::InitializeLog() is called are written to STDERR
I0000 00:00:1752602180.039289   35664 voice_transcription.cc:58] Registering VoiceTranscriptionCapability

✓ SUCCESS: Found 8 articles
Saved 8 articles to journal_articles_sel.csv

Article Summary:
------------------------------------------------------------
1. Conceptual Research: Multidisciplinary Insights for Marketing
   Authors: Irina V. Kozlenkova, Caleb Warren, Suresh Kotha, Reihane Boghrati, Robert W. Palmatier
   Date: November 16, 2024
   DOI: https://doi.org/10.1177/00222429241302814
   Abstract: Conceptual research is fundamental to advancing theory and, thus, science. Conceptual articles launch new research streams, resolve conflicting findin...

2. Fixing Onlies Versus Advancing Multiples: Number of Children and Parents’ Preferences
                        for Educational Products
   Authors: Phyllis Xue Wang, Ce Liang, Qiyuan Wang
   Date: December 11, 2024
   DOI: https://doi.org/10.1177/00222429241306009
   Abstract: Due to a continuous decline in fertility rates in recent decades, the number of one-child families has been increasing in both developing and develope...

3. Retailer Differentiation in Social Media: An Investigation of Firm-Generated Content
                        on Twitter
   Authors: Mikhail Lysyakov, P.K. Kannan, Siva Viswanathan, Kunpeng Zhang
   Date: February 11, 2025
   DOI: https://doi.org/10.1177/00222429241298654
   Abstract: Social media platforms have been used by firms for a variety of purposes: building firms’ brand image, increasing customer engagement, and providing c...

4. Cardio with Mr. Treadmill: How Anthropomorphizing the Means of Goal Pursuit Increases
                        Motivation
   Authors: Lili Wang, Maferima Touré-Tillery
   Date: November 22, 2024
   DOI: https://doi.org/10.1177/00222429241303387
   Abstract: This article examines the motivational consequences of anthropomorphizing the means of goal pursuit. Eight studies show that consumers are more motiva...

5. The Impact of App Crashes on Consumer Engagement
   Authors: Savannah Wei Shi, Seoungwoo Lee, Kirthi Kalyanam, Michel Wedel
   Date: November 22, 2024
   DOI: https://doi.org/10.1177/00222429241304322
   Abstract: The authors develop and test a theoretical framework to examine the impact of app crashes on app engagement. The framework predicts that consumers inc...

6. Beyond the Pair: Media Archetypes and Complex Channel Synergies in Advertising
   Authors: J. Jason Bell, Felipe Thomaz, Andrew T. Stephen
   Date: February 26, 2025
   DOI: https://doi.org/10.1177/00222429241302808
   Abstract: Prior research on advertising media mixes has mostly focused on single channels (e.g., television), pairwise cross-elasticities, or budget optimizatio...

7. Color Me Effective: The Impact of Color Saturation on Perceptions of Potency and Product
                        Efficacy
   Authors: Lauren I. Labrecque, Stefanie Sohn, Barbara Seegebarth, Christy Ashley
   Date: January 31, 2025
   DOI: https://doi.org/10.1177/00222429241296392
   Abstract: Consumers use observable cues, like color, to help them evaluate products. This research establishes that consumers infer greater product efficacy fro...

8. Racial Inequity in Donation-Based Crowdfunding Platforms: The Role of Facial Emotional
                        Expressiveness
   Authors: Elham Yazdani, Anindita Chakravarty, Jeffrey Inman
   Date: February 24, 2025
   DOI: https://doi.org/10.1177/00222429241300320
   Abstract: Donation-based crowdfunding platforms often claim to pursue equitable outcomes for all beneficiaries, yet many face criticism for failing to do so acr...

✓ Data saved to: journal_articles_sel.csv
""").strip()
    st.text(LOG_TEXT)

    # ------------------------------------------------------------
    # 1.  Build the direct‐download URL from your share link
    # ------------------------------------------------------------
    FILE_ID   = "10fOujQHjw1SxhfK7vQHL44JJKE_-3-8D"   # <- from the link you pasted
    GDRIVE_TXT = f"https://drive.google.com/uc?export=download&id={FILE_ID}"

    @st.cache_data(show_spinner="Fetching CSV")
    def load_csv(url: str) -> pd.DataFrame:
        resp = requests.get(url)
        resp.raise_for_status()               # fail fast on bad link
        return pd.read_csv(io.BytesIO(resp.content))

    df = load_csv(GDRIVE_TXT)

    # ------------------------------------------------------------
    # 2.  Display the data
    # ------------------------------------------------------------
    st.subheader("Scraped Articles")
    st.dataframe(df, use_container_width=True)

    # ------------------------------------------------------------
    # 3.  Let users download exactly this CSV
    # ------------------------------------------------------------
    csv_bytes = df.to_csv(index=False).encode("utf‑8")
    st.download_button(
        label="⬇️  Download CSV",
        data=csv_bytes,
        file_name="journal_articles.csv",
        mime="text/csv",
    )


def main():
    """App entry-point."""
    selection = st.sidebar.radio("Choose an assignment:", ("Assignment 1", "Assignment 2"))
    st.sidebar.markdown("**Author:** Siva Mani Subrahmanya Hari Vamsi Pullipudi")
    st.sidebar.markdown("**GMU ID:** G01505434")
    st.sidebar.markdown("**Date:** 15th July 2025")
    if selection == "Assignment 1":
        show_assignment_1()
    else:
        show_assignment_2()


if __name__ == "__main__":
    main()
