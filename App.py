# assignments_app.py - Streamlit demo app for Assignment 1 & Assignment 2

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Assignments Demo", layout="centered")


def show_assignment_1():
    """Assignment 1: Json to csv flattening, summarization, visualization."""
    st.subheader("Assignment 1 - Json to csv flattening, Data Summarization & Visualization")

    # ---------- sample code to display ----------
    code_a1 = """
Code Comes here
"""
    with st.expander("⬇️ Show Python code"):
        st.code(code_a1, language="python")

    # ---------- execute the code ----------


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

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from bs4 import BeautifulSoup
    import csv
    import re
    import time

    def setup_driver():
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")        # headless for Chrome ≥109
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # keep these two anti‑bot switches; they don't disable JS
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

        chrome_options.binary_location = "/usr/bin/chromium"
        service = Service("/usr/bin/chromedriver")           # version‑matched driver
        return webdriver.Chrome(service=service, options=chrome_options)

    def setup_driver_old():
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

    # from selenium.webdriver.chrome.service import Service
    # from webdriver_manager.chrome import ChromeDriverManager
   
    # def setup_driver():
    #     chrome_options = Options()
    #     chrome_options.add_argument("--headless=new")
    #     chrome_options.add_argument("--no-sandbox")
    #     chrome_options.add_argument("--disable-dev-shm-usage")

    #     # Force driver version that matches the browser (120.*)
    #     driver_path = ChromeDriverManager(version="120.0.6099.224").install()
    #     service = Service(driver_path)
    #     return webdriver.Chrome(service=service, options=chrome_options)

    #     # chrome_options = Options()
    #     # chrome_options.add_argument("--headless=new")      # ≥ Chrome 109
    #     # chrome_options.add_argument("--no-sandbox")
    #     # chrome_options.add_argument("--disable-dev-shm-usage")
    #     # chrome_options.binary_location = "/usr/bin/chromium"      # ← Debian path
    #     # chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    #     # chrome_options.add_argument("--disable-extensions")
    #     # chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    #     # chrome_options.add_experimental_option("useAutomationExtension", False)

    #     # # service = Service(ChromeDriverManager().install())
    #     # service = Service("/usr/bin/chromedriver")                # ← Matches v120
    #     # return webdriver.Chrome(service=service, options=chrome_options)

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
                st.write(f"Found {len(containers)} articles using selector: {selector}")
                break
        
        # If no containers found, try broader search
        if not article_containers:
            # Look for any element that might contain article info
            potential_containers = soup.find_all(['div', 'article', 'li'], 
                                            string=re.compile(r'doi|author|abstract|volume|issue', re.I))
            article_containers = potential_containers[:20]  # Limit to avoid too many false positives
            st.write(f"Using broader search, found {len(article_containers)} potential containers")
        
        for container in article_containers:
            article_data = extract_article_data(container)
            if article_data['title']:  # Only add if we have a title
                articles.append(article_data)
        
        return articles

    def scrape_with_selenium(url):
        # Use Selenium to scrape the journal page
        
        driver = None
        try:
            st.write(f"Setting up Chrome driver...")
            driver = setup_driver()
            
            st.write(f"Navigating to: {url}")
            driver.get(url)

            # ➊ Dismiss OneTrust cookie banner if it appears.
            try:
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
                ).click()
            except Exception:
                pass  # banner not present – fine

            # ➋ Wait until at least one article card is in the DOM
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.issue-item, div.issue-item-container"))
            )

            # Additional wait for dynamic content
            time.sleep(3)
            
            st.write("Page loaded successfully. Extracting content...")
            
            # Get page source
            html_content = driver.page_source
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract articles
            articles = extract_articles_from_soup(soup)
            
            return articles
            
        except Exception as e:
            st.write(f"Selenium error: {e}")
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
        
        st.write(f"Saved {len(articles)} articles to {filename}")

    def main():
        url = "https://journals.sagepub.com/toc/JMX/current"
        
        st.write("=" * 60)
        st.write("SELENIUM JOURNAL ARTICLE SCRAPER")
        st.write("=" * 60)
        st.write(f"Target URL: {url}")
        st.write()
        
        # Scrape using Selenium
        articles = scrape_with_selenium(url)
        
        if articles:
            st.write(f"\n✓ SUCCESS: Found {len(articles)} articles")
            save_to_csv(articles)
            
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
            
            st.write(f"✓ Data saved to: journal_articles_sel.csv")
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
            
        else:
            st.write("\n❌ NO ARTICLES FOUND")
            st.write("=" * 60)
            st.write("Possible issues:")
            st.write("1. ChromeDriver not installed or not in PATH")
            st.write("2. Website structure changed")
            st.write("3. Anti-bot protection still blocking")
            st.write()
            st.write("Solutions:")
            st.write("1. Make sure ChromeDriver is installed:")
            st.write("   - Download from: https://chromedriver.chromium.org/")
            st.write("   - Add to PATH or place in same directory as script")
            st.write("2. Try removing --headless flag to see what's happening")
            st.write("3. Try the manual HTML approach instead")
            st.write("=" * 60)

    if __name__ == "__main__":
        main()

def main():
    """App entry-point."""
    selection = st.sidebar.radio("Choose an assignment:", ("Assignment 1", "Assignment 2"))

    if selection == "Assignment 1":
        show_assignment_1()
    else:
        show_assignment_2()


if __name__ == "__main__":
    main()
