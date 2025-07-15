# assignments_app.py - Streamlit demo app for Assignment 1 & Assignment 2

import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

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
        save_to_csv(articles)

    except Exception as exc:
        st.write(f"Download / parse error: {exc}")

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
    st.subheader("Approach 2 - Parametric Sine-Squared Plot")

    code_plot = """
code comes here
"""
    with st.expander("⬇️ Show Python code"):
        st.code(code_plot, language="python")

def main():
    """App entry-point."""
    selection = st.sidebar.radio("Choose an assignment:", ("Assignment 1", "Assignment 2"))

    if selection == "Assignment 1":
        show_assignment_1()
    else:
        show_assignment_2()


if __name__ == "__main__":
    main()
