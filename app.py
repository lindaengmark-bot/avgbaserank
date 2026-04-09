import io
import re
import numpy as np
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="SEO Keyword Rank Tracker",
    page_icon="📈",
    layout="wide",
)

DEFAULT_NO_RANK_VALUE = 100
DEFAULT_TEMPLATE_ROWS = 400


def is_blankish(value) -> bool:
    if pd.isna(value):
        return True
    text = str(value).strip().lower()
    return text in {"", "nan", "none", "null", "-"}


def looks_like_month_col(name: str) -> bool:
    text = str(name).strip()
    patterns = [
        r"^\d{4}-\d{2}$",
        r"^\d{4}_\d{2}$",
        r"^\d{4}/\d{2}$",
        r"^\d{4}-\d{2}-\d{2}$",
        r"^[A-Za-z]{3,9}\s+\d{4}$",
        r"^\d{4}\s+[A-Za-z]{3,9}$",
    ]
    return any(re.match(pattern, text) for pattern in patterns)


def transform_long_to_wide(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "Start Date" not in df.columns or "Keyword" not in df.columns:
        return df

    df["Month"] = pd.to_datetime(df["Start Date"], errors="coerce").dt.strftime("%Y-%m")

    rank_candidates = ["Google Base Rank", "Google"]
    rank_col = None
    for candidate in rank_candidates:
        if candidate in df.columns:
            rank_col = candidate
            break

    if rank_col is None:
        raise ValueError("Hittade ingen rankingkolumn. Jag letade efter 'Google Base Rank' eller 'Google'.")

    keep_cols = ["Keyword", "Month", rank_col]
    extra_group_cols = [c for c in ["Market", "Location", "Device"] if c in df.columns]

    work = df[keep_cols + extra_group_cols].copy()
    work = work.rename(columns={rank_col: "Rank"})
    work["Rank"] = pd.to_numeric(work["Rank"], errors="coerce")
    work.loc[work["Rank"] <= 0, "Rank"] = np.nan
    work = work.dropna(subset=["Month"])

    index_cols = ["Keyword"] + extra_group_cols

    wide = (
        work.pivot_table(
            index=index_cols,
            columns="Month",
            values="Rank",
            aggfunc="min"
        )
        .reset_index()
    )

    wide.columns.name = None
    return wide


def infer_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    if df.shape[1] < 2:
        raise ValueError("Filen måste ha minst två kolumner.")

    cols = list(df.columns)
    month_cols = []
    dimension_cols = []

    for i, col in enumerate(cols):
        if i == 0:
            dimension_cols.append(col)
            continue

        series = df[col]
        non_blank = series[~series.apply(is_blankish)]

        if looks_like_month_col(col):
            month_cols.append(col)
            continue

        if len(non_blank) == 0:
            continue

        numeric_share = pd.to_numeric(non_blank, errors="coerce").notna().mean()
        if numeric_share >= 0.8:
            month_cols.append(col)
        else:
            dimension_cols.append(col)

    if not month_cols:
        raise ValueError(
            "Hittade inga månadskolumner. Första kolumnen ska vara keyword, eller filen ska innehålla Start Date + Keyword + rank-kolumn."
        )

    return dimension_cols, month_cols


def clean_positions(df: pd.DataFrame, month_cols: list[str]) -> pd.DataFrame:
    data = df.copy()

    for col in month_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")
        data.loc[data[col] <= 0, col] = np.nan

    return data


def get_active_months(df: pd.DataFrame, month_cols: list[str]) -> list[str]:
    return [col for col in month_cols if df[col].notna().sum() > 0]


def monthly_summary(df: pd.DataFrame, month_cols: list[str], no_rank_value: int) -> pd.DataFrame:
    rows = []

    for col in month_cols:
        s = pd.to_numeric(df[col], errors="coerce")
        if s.notna().sum() == 0:
            continue

        tracked_keywords = len(df)
        ranked = int(s.notna().sum())
        no_rank = int(s.isna().sum())
        effective = s.fillna(no_rank_value)

        rows.append(
            {
                "Month": col,
                "Tracked keywords": tracked_keywords,
                "Ranked keywords": ranked,
                "No-rank keywords": no_rank,
                "Visibility %": round((ranked / tracked_keywords) * 100, 2) if tracked_keywords else 0,
                "Average rank, ranked only": round(float(s.mean()), 2) if ranked else np.nan,
                f"Average rank, incl. no-rank={no_rank_value}": round(float(effective.mean()), 2) if tracked_keywords else np.nan,
                "Top 3": int(((s >= 1) & (s <= 3)).sum()),
                "Top 10": int(((s >= 1) & (s <= 10)).sum()),
                "Top 20": int(((s >= 1) & (s <= 20)).sum()),
                "Top 100": int(((s >= 1) & (s <= 100)).sum()),
            }
        )

    summary = pd.DataFrame(rows)

    if not summary.empty:
        summary["Visibility change vs prev"] = summary["Visibility %"].diff().round(2)
        incl_col = f"Average rank, incl. no-rank={no_rank_value}"
        summary["Avg rank change vs prev"] = summary[incl_col].diff().round(2)

    return summary


def winners_losers(df: pd.DataFrame, month_a: str, month_b: str, dimension_cols: list[str], no_rank_value: int) -> pd.DataFrame:
    work = df[dimension_cols + [month_a, month_b]].copy()
    work["Old"] = pd.to_numeric(work[month_a], errors="coerce").fillna(no_rank_value)
    work["New"] = pd.to_numeric(work[month_b], errors="coerce").fillna(no_rank_value)
    work["Change"] = work["Old"] - work["New"]
    cols = dimension_cols + ["Old", "New", "Change"]
    return work[cols].sort_values("Change", ascending=False)


def build_template(month_names: list[str], rows: int = DEFAULT_TEMPLATE_ROWS) -> pd.DataFrame:
    cols = ["Keyword"] + month_names
    df = pd.DataFrame("", index=range(rows), columns=cols)
    df.index = df.index + 1
    return df


def to_excel_bytes(positions_df: pd.DataFrame, summary_df: pd.DataFrame, no_rank_value: int) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        positions_df.to_excel(writer, sheet_name="Positions", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame({"Setting": ["No-rank value"], "Value": [no_rank_value]}).to_excel(
            writer, sheet_name="Config", index=False
        )
    output.seek(0)
    return output.getvalue()


st.title("📈 SEO Keyword Rank Tracker")
st.caption("Behåller månadsöversikterna från tidigare version, men kan nu också läsa long format från ranking-exporter.")

with st.sidebar:
    st.header("Inställningar")
    no_rank_value = st.number_input(
        "Värde för keywords som inte rankar",
        min_value=1,
        max_value=500,
        value=DEFAULT_NO_RANK_VALUE,
        step=1,
    )

    st.markdown("### Stödda filformat")
    st.markdown(
        "- Wide format: `Keyword`, sedan en kolumn per månad\n"
        "- Long format: `Start Date`, `Keyword`, `Google Base Rank` eller `Google`\n"
        "- Tom cell = ingen ranking\n"
        "- Bara månader med faktisk data kommer med i sammanställningen"
    )

    template_months = st.text_input(
        "Månader i mallfil",
        value="2026-01,2026-02,2026-03",
    )

uploaded = st.file_uploader(
    "Ladda upp rankingfil",
    type=["csv", "xlsx"],
)

col_a, col_b = st.columns(2)

with col_a:
    month_names = [m.strip() for m in template_months.split(",") if m.strip()] or ["2026-01", "2026-02", "2026-03"]
    template_df = build_template(month_names)
    st.download_button(
        "⬇️ Ladda ner CSV-mall",
        data=template_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="seo_keyword_template.csv",
        mime="text/csv",
    )

with col_b:
    example_df = pd.DataFrame(
        {
            "Start Date": ["2026-01-01", "2026-02-01", "2026-01-01", "2026-02-01"],
            "Keyword": ["seo byrå stockholm", "seo byrå stockholm", "teknisk seo", "teknisk seo"],
            "Google Base Rank": [1, 2, 4, None],
            "Market": ["DE", "DE", "DE", "DE"],
            "Device": ["Desktop", "Desktop", "Desktop", "Desktop"],
        }
    )
    st.download_button(
        "⬇️ Ladda ner exempelfil",
        data=example_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="seo_keyword_example_long_format.csv",
        mime="text/csv",
    )

if uploaded is None:
    st.info("Ladda upp en fil för att börja.")
    st.stop()

try:
    raw_df = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
    transformed_df = transform_long_to_wide(raw_df)
    dimension_cols, month_cols = infer_columns(transformed_df)
    data = clean_positions(transformed_df, month_cols)

    first_dim = dimension_cols[0]
    data = data[data[first_dim].notna()].copy()
    data = data[data[first_dim].astype(str).str.strip() != ""]

    active_months = get_active_months(data, month_cols)
    summary = monthly_summary(data, active_months, int(no_rank_value))
except Exception as e:
    st.error(f"Kunde inte tolka filen: {e}")
    st.stop()

if not active_months:
    st.warning("Jag hittade inga månader med data ännu.")
    st.stop()

st.subheader("Aktiva månader")
st.write(", ".join(active_months))

st.subheader("Översikt")
latest = summary.iloc[-1]
prev = summary.iloc[-2] if len(summary) > 1 else None
incl_col = f"Average rank, incl. no-rank={int(no_rank_value)}"

k1, k2, k3, k4 = st.columns(4)
k1.metric("Tracked keywords", int(latest["Tracked keywords"]))
k2.metric(
    "Visibility %",
    f'{latest["Visibility %"]:.2f}%',
    None if prev is None else f'{latest["Visibility %"] - prev["Visibility %"]:.2f} pp',
)
k3.metric(
    "Avg rank, incl. no-rank",
    f'{latest[incl_col]:.2f}',
    None if prev is None else f'{latest[incl_col] - prev[incl_col]:.2f}',
)
k4.metric(
    "Top 10",
    int(latest["Top 10"]),
    None if prev is None else int(latest["Top 10"] - prev["Top 10"]),
)

st.subheader("Månadsutveckling")
chart_option = st.selectbox(
    "Välj graf",
    options=[
        "Visibility %",
        incl_col,
        "Average rank, ranked only",
        "Top 10",
        "Top 3",
        "Top 20",
        "Top 100",
    ],
)
st.line_chart(summary.set_index("Month")[[chart_option]])

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### KPI-tabell")
    st.dataframe(summary, use_container_width=True)

with c2:
    st.markdown("#### Senaste månaden, fördelning")
    dist = pd.DataFrame(
        {
            "Bucket": ["Top 3", "Top 10", "Top 20", "Top 100", "No rank"],
            "Count": [
                int(latest["Top 3"]),
                int(latest["Top 10"]),
                int(latest["Top 20"]),
                int(latest["Top 100"]),
                int(latest["No-rank keywords"]),
            ],
        }
    )
    st.bar_chart(dist.set_index("Bucket"))

if len(active_months) >= 2:
    st.subheader("Vinnare och tappare")
    compare_a = st.selectbox("Jämför från månad", options=active_months[:-1], index=max(0, len(active_months) - 2))
    remaining = [m for m in active_months if m > compare_a] or active_months[1:]
    compare_b = st.selectbox("Till månad", options=remaining, index=len(remaining) - 1)

    changes = winners_losers(data, compare_a, compare_b, dimension_cols, int(no_rank_value))
    left, right = st.columns(2)
    with left:
        st.markdown("#### Största förbättringar")
        st.dataframe(changes.head(15), use_container_width=True)
    with right:
        st.markdown("#### Största tapp")
        st.dataframe(changes.tail(15).sort_values("Change"), use_container_width=True)

st.subheader("Positionsdata")
st.dataframe(data[dimension_cols + active_months], use_container_width=True)

export_bytes = to_excel_bytes(data[dimension_cols + active_months], summary, int(no_rank_value))
st.download_button(
    "⬇️ Ladda ner analys som Excel",
    data=export_bytes,
    file_name="seo_keyword_rank_analysis.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.markdown("---")
st.markdown(
    "**Viktigt:** den här versionen behåller sammanställningarna från den tidigare appen, "
    "men klarar nu också din export med `Start Date` + rankingkolumn."
)
