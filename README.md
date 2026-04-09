# SEO Keyword Rank Tracker, Streamlit

En enkel Streamlit-app för att följa keyword rankings månad för månad.

## Funktioner

- Ladda upp CSV eller Excel
- Tom cell = ingen ranking
- Valbart no-rank-värde, till exempel 100
- KPI:er per månad
- Visibility %
- Average rank, ranked only
- Average rank, incl. no-rank
- Top 3, Top 10, Top 20, Top 100
- Export till Excel

## Filformat

Första kolumnen ska vara keywordnamn. Alla följande kolumner ska vara månader.

Exempel:

| Keyword | 2026-01 | 2026-02 | 2026-03 |
|---|---:|---:|---:|
| seo byrå stockholm | 1 | 1 | 2 |
| teknisk seo | 4 | 3 | |
| content audit | | 12 | 9 |

## Kör lokalt

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Lägg upp på GitHub och Streamlit Community Cloud

1. Skapa ett nytt repo på GitHub
2. Ladda upp `app.py`, `requirements.txt` och `README.md`
3. Gå till Streamlit Community Cloud
4. Välj ditt GitHub-repo
5. Sätt main file path till `app.py`
6. Deploy

Appen använder `st.file_uploader` för filuppladdning och `st.download_button` för export. Streamlit-dokumentationen beskriver båda widgets och den senaste docs-sajten visar att Streamlit v1.55.0 är aktuell. citeturn492982search1turn492982search0turn492982search3
