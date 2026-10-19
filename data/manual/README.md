# Add your own documents

Drop extra files here and re-run `python run.py`. They are ingested with top priority.

    data/manual/notices/Exam-Schedule-Dec-2026.pdf
    data/manual/hostel/Mess-Menu.txt
    data/manual/fees/Fee-Notice.md

* Sub-folder name = category (admission, academics, hostel, fees, examination, scholarships, contact, notices, general).
  Files in the top level are classified from their file name.
* Supported: .pdf .txt .md .html
* In .txt/.md files, lines starting with `#` are treated as headings.

Typical use: **notices** (the website's announcements page is rendered by JavaScript, so
it cannot be scraped) and any PDF the crawler did not find.
