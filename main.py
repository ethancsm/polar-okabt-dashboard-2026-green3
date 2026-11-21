out = pathlib.Path('/home/user/outputs')
out.mkdir(parents=True, exist_ok=True)

MAIN = r'''import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ═══════════════════════════════════════════════════════════════════════════
# 컬러 팔레트 — 송도고 그린 3팀 테마
# ═══════════════════════════════════════════════════════════════════════════
GREEN_DARK  = "#1a3c2a"
GREEN_MID   = "#2d6a4f"
GREEN_LIGHT = "#52b788"
GREEN_PALE  = "#d8f3dc"
GREEN_BG    = "#f0f7f1"
ORANGE      = "#e76f51"

# ═══════════════════════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    background: #f0f7f1;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a3c2a 0%, #2d6a4f 100%) !important;
}
section[data-testid="stSidebar"] .stTextInput,
section[data-testid="stSidebar"] .stFileUploader,
section[data-testid="stSidebar"] .stSelectbox {
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(255,255,255,0.18) !important;
    color: #fff !important;
}
section[data-testid="stSidebar"] label {
    color: #d8f3dc !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] .st-emotion-cache-1v0mbw5 {
    background: rgba(255,255,255,0.08) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    color: #fff !important;
}
section[data-testid="stSidebar"] .st-emotion-cache-ufhbyv {
    border-color: rgba(216,243,220,0.3) !important;
}

div[data-testid="stTabs"] button {
    background: #fff !important;
    border: 1px solid #d8f3dc !important;
    border-radius: 12px 12px 0 0 !important;
    font-weight: 700 !important;
    color: #1a3c2a !important;
    padding: 10px 20px !important;
    transition: all 0.2s;
}
div[data-testid="stTabs"] button:hover {
    background: #d8f3dc !important;
}
div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #2d6a4f, #52b788) !important;
    color: white !important;
    border-color: transparent !important;
}

div[data-testid="stMetric"] {
    background: white;
    border-radius: 12px;
    padding: 14px 18px;
    box-shadow: 0 4px 12px rgba(26,60,42,0.08);
    border: 1px solid #d8f3dc;
    transition: all 0.25s;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 20px rgba(26,60,42,0.12);
    border-color: #52b788;
}

div[data-testid="stInfo"] {
    background: #d8f3dc !important;
    border-left: 4px solid #2d6a4f !important;
    border-radius: 8px !important;
}

div[data-testid="stFileDownloader"] button {
    background: linear-gradient(135deg, #2d6a4f, #52b788) !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
}
div[data-testid="stFileDownloader"] button:hover {
    background: linear-gradient(135deg, #1a3c2a, #2d6a4f) !important;
}

div[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    border: 1px solid #d8f3dc !important;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# 헬퍼 함수
# ═══════════════════════════════════════════════════════════════════════════
def hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def base_layout(fig, height=300, xtitle="", ytitle="", bargap=0.05):
    fig.update_layout(
        font=dict(family="Noto Sans KR, Malgun Gothic, Apple SD Gothic Neo, sans-serif", size=12),
        xaxis_title=xtitle,
        yaxis_title=ytitle,
        height=height,
        plot_bgcolor="#fafcfa",
        paper_bgcolor="#fafcfa",
        bargap=bargap,
        margin=dict(t=30, b=40, l=45, r=20),
        xaxis=dict(gridcolor="#e8f0e5", zerolinecolor="#c8e0c5", tickfont=dict(size=11)),
        yaxis=dict(gridcolor="#e8f0e5", zerolinecolor="#c8e0c5", tickfont=dict(size=11)),
    )

def add_trendline(fig, x, y, color="#e76f51"):
    """np.polyfit 으로 추세선을 직접 그립니다. statsmodels 불필요."""
    m = ~x.isna() & ~y.isna()
    if m.sum() < 2:
        return
    xv, yv = x[m], y[m]
    if xv.nunique() < 2:
        return
    a, b = np.polyfit(xv, yv, 1)
    xlo, xhi = float(xv.min()), float(xv.max())
    fig.add_trace(go.Scatter(
        x=[xlo, xhi],
        y=[a * xlo + b, a * xhi + b],
        mode="lines",
        line=dict(color=color, dash="dash", width=2),
        name="추세선",
        hoverinfo="skip",
    ))

def hero_card(html_content, dark=True):
    # ⚠️ 반드시 '''를 별도 라인에 써서 string literal unterminated 방지
    bg = "linear-gradient(135deg, #1a3c2a 0%, #2d6a4f 100%)" if dark \
         else "linear-gradient(135deg, #f0f7f1, #d8f3dc)"
    txt = "white" if dark else "#1a3c2a"
    return (
        f'<div style="'
        f"background: {bg};"
        f"border-radius:16px; padding:20px 24px; color:{txt};"
        f"margin-bottom:20px; box-shadow:0 4px 16px rgba(26,60,42,0.15);">'
        f"{html_content}"
        f"</div>"
    )

def info_card(html_content):
    return (
        '<div style="'
        "background:#d8f3dc; border-left:4px solid #2d6a4f; border-radius:8px;"
        "padding:12px 16px; margin-bottom:12px; line-height:1.7;">'
        f"{html_content}"
        "</div>"
    )

def analysis_card(title_html, body_html, accent="#2d6a4f"):
    return (
        '<div style="'
        "background:white; border-radius:14px; padding:16px 20px;"
        "margin-bottom:16px; box-shadow:0 3px 10px rgba(26,60,42,0.06);"
        f"border-top:3px solid {accent};">'
        f'<div style="font-weight:700; color:#1a3c2a; margin-bottom:8px; font-size:1.05em;">{title_html}</div>'
        f'<div style="line-height:1.7;">{body_html}</div>'
        "</div>"
    )

# ═══════════════════════════════════════════════════════════════════════════
# CSV 읽기 & 표준화
# ═══════════════════════════════════════════════════════════════════════════
@st.cache_data
def read_csv_bytes(file):
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()

def std_cols(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for c in df.columns:
        k = c.lower().replace(" ", "")
        if k in ("time", "categories", "시간", "날짜", "datetime", "date"):
            rename[c] = "time"
        elif k in ("temperature", "온도"):
            rename[c] = "temperature"
        elif k in ("humidity", "습도"):
            rename[c] = "humidity"
        elif c.lower() == "ph":
            rename[c] = "ph"
        elif k == "ec":
            rename[c] = "ec"
        elif "생중량" in k:
            rename[c] = "생중량"
        elif "잎" in k:
            rename[c] = "잎 수"
        elif "지상부" in k and "길이" in k:
            rename[c] = "지상부 길이"
        elif "지하부" in k and "길이" in k:
            rename[c] = "지하부 길이"
        elif "지상부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지상부 질량"
        elif "지하부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지하부 질량"
        elif "개체" in k:
            rename[c] = "개체번호"
    df = df.rename(columns=rename)
    for c in df.columns:
        if c in ("time", "개체번호"):
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            num = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")
            if num.notna().mean() >= 0.5:
                df[c] = num
    if "생중량" not in df.columns and {"지상부 질량", "지하부 질량"} <= set(df.columns):
        df["생중량"] = df["지상부 질량"] + df["지하부 질량"]
    if "time" in df.columns:
        t = df["time"].astype(str).str.strip()
        parsed = pd.to_datetime(t, errors="coerce", format="mixed")
        bad = parsed.isna() & t.str.match(r"^\d{8}_\d{1,2}$")
        if bad.any():
            parts = t[bad].str.split("_", expand=True)
            parsed[bad] = pd.to_datetime(parts[0], format="%Y%m%d") + pd.to_timedelta(parts[1].astype(int), unit="h")
        df["time"] = parsed
    return df

# ═══════════════════════════════════════════════════════════════════════════
# 사이드바
# ═══════════════════════════════════════════════════════════════════════════
st.sidebar.title("🌿 송도고 그린 3팀")
st.sidebar.markdown("---")
st.sidebar.markdown(
    '<div style="color:#d8f3dc; font-size:0.9em; line-height:1.6;">'
    "극지식물 개체별 생육 차이 분석<br>"
    '<span style="opacity:0.7; font-size:0.85em;">'
    "팀원: 천영현 · 윤효승 · 최승민 · 김성빈 &nbsp;|&nbsp; 검수: 이유경 박사"
    "</span>"
    "</div>",
    unsafe_allow_html=True,
)

st.sidebar.markdown("---")
st.sidebar.subheader("📁 데이터 업로드")
env_file = st.sidebar.file_uploader("📊 환경 데이터 CSV", type="csv")
growth_file = st.sidebar.file_uploader("🌱 생육 결과 데이터 CSV", type="csv")

st.sidebar.markdown("---")
st.sidebar.subheader("📏 분석 항목 선택")
growth_cols_options = ["잎 수", "지상부 길이", "지하부 길이", "생중량",
                       "지상부 질량", "지하부 질량"]
chosen_col = st.sidebar.selectbox("비교할 생육 지표", growth_cols_options, index=0)

st.sidebar.markdown("---")
if env_file or growth_file:
    st.sidebar.success("✅ 파일이 준비되었습니다")
    st.sidebar.caption("상단 탭을 눌러 분석을 확인하세요")
else:
    st.sidebar.info("📁 CSV 파일을 올려주세요.\n학교마다 열 이름이 달라도\n자동으로 맞춰 읽습니다.")

# 데이터 로드
env_df = pd.DataFrame()
growth_df = pd.DataFrame()

if env_file is not None:
    with st.spinner("📊 환경 데이터를 읽는 중..."):
        env_df = std_cols(read_csv_bytes(env_file))
if growth_file is not None:
    with st.spinner("🌱 생육 데이터를 읽는 중..."):
        growth_df = std_cols(read_csv_bytes(growth_file))

sn_env = "송도고" if env_file else "환경 데이터"
sn_growth = "송도고" if growth_file else "생육 데이터"

# ═══════════════════════════════════════════════════════════════════════════
# 메인 페이지 상단
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="극지식물 생육 분석 — 송도고 그린 3팀", layout="wide")

st.markdown(
    hero_card(
        '<div style="display:flex; align-items:center; justify-content:space-between;'
        'flex-wrap:wrap; gap:8px;">'
        "<div>"
        '<div style="font-size:0.75em; letter-spacing:3px; opacity:0.75; margin-bottom:4px;">'
        "🔬 송도고등학교 · 스마트팜 연구 프로젝트"
        "</div>"
        "<h1 style='font-size:1.6em; font-weight:900; margin:0; line-height:1.3;'>"
        "지하부의 무게가 무거울수록<br>잎의 개수가 많을까?"
        "</h1>"
        '<div style="font-size:0.85em; opacity:0.8; margin-top:4px;">'
        "같은 스마트팜에서 자란 81개체 극지식물 생육 차이 분석"
        "</div>"
        "</div>"
        "<div style='text-align:right;'>"
        '<div style="font-size:1.1em; font-weight:700;">🌿 송도고 그린 3팀</div>'
        '<div style="font-size:0.75em; opacity:0.7;">천영현 · 윤효승 · 최승민 · 김성빈</div>'
        '<div style="font-size:0.75em; opacity:0.7;">검수: 이유경 박사 (극지연구소)</div>'
        "</div>"
        "</div>",
        dark=True,
    ),
    unsafe_allow_html=True,
)

if env_file or growth_file:
    st.markdown(
        info_card(
            "<b>📌 사용 방법:</b> 왼쪽 사이드바에서 CSV 파일을 올리면 자동으로 분석 결과가 표시됩니다.<br>"
            "학교마다 열 이름이 달라도 표준화하여 읽으며, 탭을 눌러 환경·생육·관계 분석을 확인할 수 있습니다."
        ),
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        info_card(
            "<b>📌 CSV 파일을 아직 올리지 않으셨나요?</b> 왼쪽 사이드바에서 환경 데이터와 생육 결과 데이터를 업로드하면"
            "자동으로 분석 결과가 표시됩니다."
        ),
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs([
    "🏠 실험 개요 · 핵심 결과",
    "📈 환경 데이터 변화",
    "🔬 잎 수 vs 생중량 관계 분석",
])

# ═══════════════════════════════════════════════════════════════════════════
# 탭 1 — 실험 개요 & 핵심 결과
# ═══════════════════════════════════════════════════════════════════════════
with tab1:
    try:
        st.markdown(
            hero_card(
                '<div style="display:flex; gap:16px; align-items:flex-start;">'
                '<div style="font-size:2.2em; line-height:1;">🎯</div>'
                "<div>"
                '<div style="font-weight:700; font-size:1.1em; margin-bottom:4px;">연구 목적</div>'
                "<p style='margin:0; line-height:1.7; opacity:0.92; font-size:0.95em;'>"
                "같은 스마트팜에서 함께 자란 극지식물들이"
                "<b>왜 어떤 개체는 크게 자라고, 어떤 개체는 작게 자라는지</b>를"
                "환경 데이터와 생육 결과를 비교·분석하여 밝힙니다."
                "특히 <b>지하부 질량(무게)과 잎 수 사이의 관계</b>를 수치와 그래프로 확인하고,"
                "향후 재배 개선을 위한 단서를 찾는 것이 목표입니다."
                "</p>"
                "</div>"
                "</div>",
                dark=True,
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div style="color:#1a3c2a;font-weight:700;font-size:1em;margin-bottom:10px;">'
            "📊 데이터 현황 한눈에"
            "</div>",
            unsafe_allow_html=True,
        )
        hc1, hc2, hc3, hc4 = st.columns(4)

        with hc1:
            if env_file:
                st.metric("📊 환경 데이터", f"{len(env_df):,}행", delta=f"출처: {sn_env}")
            else:
                st.info("⚠️ 환경 CSV 미업로드")
        with hc2:
            if "time" in env_df.columns:
                td = env_df["time"].dropna()
                if len(td) >= 2:
                    span = td.max() - td.min()
                    st.metric("⏱️ 측정 기간", f"{span.days}일",
                              delta=f"{td.min().strftime('%m/%d')} ~ {td.max().strftime('%m/%d')}")
                else:
                    st.metric("⏱️ 측정 기간", "확인 중")
            else:
                st.metric("⏱️ 측정 기간", "time 열 없음")
        with hc3:
            if growth_file:
                st.metric("🌱 생육 개체 수", f"{len(growth_df)}개체", delta=sn_growth)
            else:
                st.info("⚠️ 생육 CSV 미업로드")
        with hc4:
            if "생중량" in growth_df.columns:
                gv = growth_df["생중량"].dropna()
                st.metric("⚖️ 생중량 범위", f"{gv.min():.2f} ~ {gv.max():.2f} g",
                          delta=f"평균 {gv.mean():.2f}g (σ {gv.std():.2f})")
            else:
                st.metric("⚖️ 생중량", "열 없음")

        st.markdown("---", unsafe_allow_html=True)

        st.markdown(
            '<div style="color:#1a3c2a;font-weight:700;font-size:1em;margin-bottom:10px;">'
            "🌱 생육 지표 요약 (81개체 전체)"
            "</div>",
            unsafe_allow_html=True,
        )
        gcols = ["잎 수", "지상부 길이", "지하부 길이", "생중량", "지상부 질량", "지하부 질량"]
        growth_summary = []
        for col_name in gcols:
            if col_name in growth_df.columns:
                d = growth_df[col_name].dropna()
                if len(d) == 0:
                    continue
                growth_summary.append((col_name, d.mean(), d.min(), d.max(), d.std()))

        for i in range(0, len(growth_summary), 3):
            row_cols = st.columns(3)
            for j in range(3):
                if i + j < len(growth_summary):
                    cn, mean_v, min_v, max_v, std_v = growth_summary[i + j]
                    row_cols[j].metric(label=cn, value=f"{mean_v:.2f}",
                                        delta=f"범위 {min_v:.2f} ~ {max_v:.2f}  (σ {std_v:.2f})")
                else:
                    row_cols[j].empty()

        st.markdown("---", unsafe_allow_html=True)

        st.markdown(
            '<div style="color:#1a3c2a;font-weight:700;font-size:1em;margin-bottom:10px;">'
            "🔎 핵심 발견 — 지하부 질량과 잎 수의 관계"
            "</div>",
            unsafe_allow_html=True,
        )

        if "생중량" in growth_df.columns and "잎 수" in growth_df.columns:
            g2 = growth_df[["생중량", "잎 수"]].dropna()
            if len(g2) >= 10:
                bw = g2["생중량"].median()
                high = g2[g2["생중량"] > bw]
                low = g2[g2["생중량"] <= bw]
                if len(high) >= 3 and len(low) >= 3:
                    r_val = float(g2["생중량"].corr(g2["잎 수"]))
                    diff = high["잎 수"].mean() - low["잎 수"].mean()
                    r_tag = ("강한 양의 상관" if r_val > 0.5 else "중간 양의 상관"
                             if r_val > 0.3 else "약한 양의 상관" if r_val > 0 else "음의 상관")

                    st.markdown(
                        info_card(
                            '<div style="display:flex; gap:12px; align-items:flex-start;">'
                            f'<div style="font-size:1.6em; line-height:1; color:{GREEN_MID};">✅</div>'
                            "<div style='flex:1;'>"
                            f'<div style="font-weight:700; font-size:1.05em; margin-bottom:6px; color:{GREEN_DARK};">'
                            "지하부 질량(무게) 기준 그룹 비교 결과"
                            "</div>"
                            "<table style='width:100%; border-collapse:collapse; font-size:0.92em;'>"
                            "<tr>"
                            '<td style="padding:4px 8px; border-bottom:1px solid #b7e0c5; color:#888; font-size:0.82em;">평균 생중량</td>'
                            f'<td style="padding:4px 8px; border-bottom:1px solid #b7e0c5; font-weight:700; color:{GREEN_MID};">{high["생중량"].mean():.2f}g</td>'
                            "<td style='padding:4px 8px;'></td>"
                            '<td style="padding:4px 8px; border-bottom:1px solid #b7e0c5; font-weight:700; color:#888;">{low["생중량"].mean():.2f}g</td>'
                            "</tr>"
                            "<tr>"
                            '<td style="padding:4px 8px; color:#888; font-size:0.82em;">잎 수 평균</td>'
                            f'<td style="padding:4px 8px; font-weight:700; color:{GREEN_MID};">{high["잎 수"].mean():.1f}장</td>'
                            "<td style='padding:4px 8px;'></td>"
                            '<td style="padding:4px 8px; font-weight:700; color:#888;">{low["잎 수"].mean():.1f}장</td>'
                            "</tr>"
                            "</table>"
                            '<div style="margin-top:8px; padding-top:8px; border-top:1px dashed #b7e0c5; line-height:1.6;">'
                            f"🔹 두 그룹 간 잎 수 차이: <b>약 {diff:.1f}장</b><br>"
                            f"🔹 생중량과 잎 수의 상관계수: <b style='font-size:1.1em;'>r = {r_val:.3f}</b>"
                            f'<span style="background:#fff; padding:2px 8px; border-radius:4px; font-size:0.82em;">{r_tag}</span>'
                            "</div>"
                            "</div>"
                            "</div>",
                        ),
                        unsafe_allow_html=True,
                    )

        if "생중량" in growth_df.columns:
            g3 = growth_df[["생중량"]].dropna()
            if len(g3) >= 3:
                st.markdown(
                    '<div style="color:#1a3c2a;font-weight:700;font-size:1em;margin:16px 0 8px 0;">'
                    "📊 생중량 분포 — 상위 5 vs 하위 5 (송도고 그린 3팀 분석)"
                    "</div>",
                    unsafe_allow_html=True,
                )
                s = g3["생중량"].dropna().sort_values(ascending=False)
                top5_idx_set = set(s.head(5).index)
                bot5_idx_set = set(s.tail(5).index)
                fig = go.Figure()
                bar_colors = []
                bar_labels = []
                for idx in s.index:
                    if idx in top5_idx_set:
                        bar_colors.append(ORANGE)
                    elif idx in bot5_idx_set:
                        bar_colors.append(GREEN_DARK)
                    else:
                        bar_colors.append(GREEN_LIGHT)
                    if "개체번호" in growth_df.columns:
                        bar_labels.append(str(growth_df["개체번호"].iloc[idx]))
                    else:
                        bar_labels.append(str(idx + 1))
                fig.add_trace(go.Bar(
                    x=bar_labels,
                    y=s.to_numpy(dtype=float),
                    marker_color=bar_colors,
                    hovertemplate="개체 %{x} : 생중량 %{y:.2f}g<extra></extra>",
                ))
                base_layout(fig, height=280, xtitle="개체 번호", ytitle="생중량 (g)")
                fig.add_vline(x=len(s) * 0.5, line_dash="dot", line_color="#c8e0c5", opacity=0.6)
                fig.add_annotation(
                    x=0.01, y=1.0, xref="paper", yref="paper",
                    text="🔴 상위 5개체  ·  🟢 하위 5개체  ·  연두 = 나머지",
                    showarrow=False, bgcolor="white", bordercolor="#b7e0c5", borderwidth=1,
                    font=dict(size=10, color=GREEN_DARK), xanchor="left", yanchor="top",
                )
                st.plotly_chart(fig, width="stretch")
                st.caption(
                    "같은 스마트팜에서 자랐지만 생중량은 최대 250배 차이 — 어떤 요인이 이걸 만들었을까?"
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# 탭 2 — 환경 데이터 변화
# ═══════════════════════════════════════════════════════════════════════════
with tab2:
    try:
        if env_df.empty:
            st.info("⚠️ 환경 데이터 CSV를 올려주세요.")
        else:
            st.markdown(
                hero_card(
                    '<div style="display:flex; align-items:center; gap:12px;">'
                    '<div style="font-size:1.6em;">📈</div>'
                    "<div>"
                    f'<div style="font-weight:700; font-size:1.1em;">{sn_env} 환경 데이터 — 시간에 따른 변화</div>'
                    '<div style="font-size:0.85em; opacity:0.8;">'
                    "약 128일간 1시간 간격으로 측정된 온도·습도·EC·pH·CO₂의 추이"
                    "</div>"
                    "</div>"
                    "</div>",
                ),
                unsafe_allow_html=True,
            )

            env_num_cols = [
                c for c in env_df.columns
                if c != "time" and pd.api.types.is_numeric_dtype(env_df[c])
            ]
            plot_targets = [
                c for c in ("temperature", "humidity", "ec", "ph", "co2")
                if c in env_num_cols
            ]
            color_map = {
                "temperature": "#e76f51", "humidity": "#457b9d",
                "ec": "#2d6a4f", "ph": "#9b5de5", "co2": "#f15bb5",
            }

            if plot_targets:
                n = min(4, len(plot_targets))
                chart_cols = st.columns(n)
                for i, col_name in enumerate(plot_targets[:n]):
                    e = env_df[["time", col_name]].dropna()
                    if len(e) < 2:
                        with chart_cols[i]:
                            st.info(f"⚠️ {col_name} 데이터가 충분하지 않아요.")
                        continue
                    color = color_map.get(col_name, "#2d6a4f")
                    rgb = hex_to_rgb(color)
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=e["time"].to_numpy(),
                        y=e[col_name].to_numpy(),
                        mode="lines",
                        fill="tozeroy",
                        fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.18)",
                        line=dict(color=color, width=1.8),
                    ))
                    base_layout(fig, height=180, xtitle="", ytitle=col_name)
                    chart_cols[i].plotly_chart(fig, width="stretch")
            else:
                st.info("⚠️ temperature·humidity·ec·ph·co2 중 맞는 숫자 열이 없어요.")

            st.markdown("<br>", unsafe_allow_html=True)

            st.markdown(
                hero_card(
                    '<div style="display:flex; align-items:center; gap:12px;">'
                    '<div style="font-size:1.4em;">📋</div>'
                    "<div>"
                    f'<div style="font-weight:700; font-size:1.05em;">{sn_env} 환경 데이터 원본 (처음 50행)</div>'
                    '<div style="font-size:0.8em; opacity:0.75;">'
                    "time 열 포함 지표 · 스크롤하여 전체 확인 가능"
                    "</div>"
                    "</div>"
                    "</div>",
                ),
                unsafe_allow_html=True,
            )

            display_cols = ["time"] + [c for c in env_num_cols if c != "time"][:5]
            show_df = env_df[display_cols].copy()
            if "time" in show_df.columns:
                show_df["time"] = show_df["time"].dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(show_df.head(50), width="stretch", height=300)

            st.markdown("<br>", unsafe_allow_html=True)

            st.markdown(
                hero_card(
                    '<div style="display:flex; align-items:center; gap:12px;">'
                    '<div style="font-size:1.4em;">📊</div>'
                    "<div>"
                    f'<div style="font-weight:700; font-size:1.05em;">{sn_env} 환경 지표 요약표</div>'
                    '<div style="font-size:0.8em; opacity:0.75;">'
                    "각 지표의 평균·최소·최대·표준편차 (결측값 제외)"
                    "</div>"
                    "</div>"
                    "</div>",
                ),
                unsafe_allow_html=True,
            )

            sum_cols = st.columns(len(env_num_cols))
            for i, cn in enumerate(env_num_cols):
                d = env_df[cn].dropna()
                if len(d) == 0:
                    sum_cols[i].info(f"⚠️ {cn} 데이터 없음")
                    continue
                sum_cols[i].metric(
                    label=cn,
                    value=f"{d.mean():.2f}",
                    delta=f"최소 {d.min():.2f}  ·  최대 {d.max():.2f}  ·  σ {d.std():.2f}",
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# 탭 3 — 잎 수 vs 생중량 관계 분석
# ═══════════════════════════════════════════════════════════════════════════
with tab3:
    try:
        if growth_df.empty:
            st.info("⚠️ 생육 결과 CSV를 올려주세요.")
        else:
            st.markdown(
                hero_card(
                    '<div style="display:flex; gap:16px; align-items:flex-start;">'
                    '<div style="font-size:2em; line-height:1;">🔬</div>'
                    "<div>"
                    '<div style="font-weight:700; font-size:1.1em;">잎 수 vs 생중량 — 핵심 관계 분석</div>'
                    '<div style="font-size:0.85em; opacity:0.85;">'
                    "송도고 그린 3팀의 핵심 질문: <b>지하부 무게가 무거울수록 잎의 개수가 많을까?</b><br>"
                    "같은 스마트팜에서 키운 81개체 데이터를 낱낱이 비교합니다."
                    "</div>"
                    "</div>"
                    "</div>",
                    dark=True,
                ),
                unsafe_allow_html=True,
            )

            if "잎 수" in growth_df.columns and "생중량" in growth_df.columns:
                st.markdown(
                    '<div style="color:#1a3c2a;font-weight:700;font-size:1.05em;margin:16px 0 6px 0;">'
                    "🌿 잎 수 vs 생중량 — 산점도 (점 색상 = 생중량 크기)"
                    "</div>",
                    unsafe_allow_html=True,
                )
                d = growth_df[["잎 수", "생중량"]].dropna()
                if len(d) >= 5:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=d["잎 수"].to_numpy(dtype=float),
                        y=d["생중량"].to_numpy(dtype=float),
                        mode="markers",
                        marker=dict(
                            size=11,
                            color=d["생중량"].to_numpy(dtype=float),
                            colorscale=[[0, GREEN_PALE], [0.5, GREEN_LIGHT], [1, ORANGE]],
                            showscale=True,
                            colorbar=dict(title="생중량(g)", thickness=16, xanchor="right",
                                          tickfont=dict(size=11)),
                            line=dict(width=1.2, color="white"),
                        ),
                        hovertemplate="🌿 잎 수: %{x:.0f}장<br>⚖️ 생중량: %{y:.2f}g<extra></extra>",
                    ))
                    add_trendline(fig, d["잎 수"], d["생중량"], color=ORANGE)
                    r_val = float(d["잎 수"].corr(d["생중량"]))
                    base_layout(fig, height=400, xtitle="🌿 잎 수 (장)", ytitle="⚖️ 생중량 (g)")
                    fig.add_annotation(
                        x=0.96, y=0.97, xref="paper", yref="paper",
                        text=f"상관계수<br>r = {r_val:.3f}",
                        showarrow=False, bgcolor=GREEN_PALE, bordercolor=GREEN_MID,
                        borderwidth=1.5, borderpad=6,
                        font=dict(color=GREEN_DARK, size=14, weight="bold"),
                    )
                    st.plotly_chart(fig, width="stretch")

                    st.markdown("<br>", unsafe_allow_html=True)

                    r_desc = (
                        f"<span style='color:{ORANGE};font-weight:600;'>강한 양의 상관</span>"
                        " — 잎 수가 많을수록 생중량도 확실히 커지는 경향이 뚜렷합니다."
                        if r_val > 0.5
                        else f"<span style='color:{GREEN_MID};font-weight:600;'>중간 정도의 양의 상관</span>"
                        " — 대체로 잎 수가 많을수록 생중량이 커지는 경향이 있습니다."
                        if r_val > 0.3
                        else "<span style='color:#888;'>약한 양의 상관</span>"
                        " — 잎 수와 생중량 사이에 약한 양의 관계가 보입니다."
                        if r_val > 0
                        else "<span style='color:#888;'>음의 상관</span>"
                        " — 잎 수가 많을수록 생중량이 오히려 작아지는 경향입니다."
                    )

                    st.markdown(
                        info_card(
                            f"<b>📌 상관계수 r = {r_val:.3f}</b><br>"
                            f"{r_desc}<br><br>"
                            "<b>💡 상관계수(r)</b>란 두 변수 사이의 선형 관계 강도를 -1 ~ 1 사이 숫자로 나타낸 것입니다."
                            "1에 가까울수록 함께 증가하고, -1에 가까울수록 반대로 움직이며,"
                            "0에 가까우면 선형 관계가 거의 없습니다."
                            "이 수치는 <b>인과관계를 뜻하는 것은 아니며</b>, 단순히 '함께 움직이는 정도'를 나타냅니다."
                        ),
                        unsafe_allow_html=True,
                    )

            if "생중량" in growth_df.columns:
                pred_candidates = [
                    c for c in ["잎 수", "지상부 길이", "지하부 길이"]
                    if c in growth_df.columns
                ]
                if pred_candidates:
                    st.markdown(
                        '<div style="color:#1a3c2a;font-weight:700;font-size:1.05em;margin:16px 0 6px 0;">'
                        "📐 생중량 예측식 (선형 근사) — 송도고 그린 3팀 계산"
                        "</div>",
                        unsafe_allow_html=True,
                    )
                    d2 = growth_df[["생중량"] + pred_candidates].dropna()
                    if len(d2) >= len(pred_candidates) + 1:
                        X = np.column_stack(
                            [np.ones(len(d2)), d2[pred_candidates].to_numpy(dtype=float)]
                        )
                        y = d2["생중량"].to_numpy(dtype=float)
                        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
                        intercept = float(coef[0])
                        terms = " + ".join(
                            f"{coef[i+1]:.4f}×{pred_candidates[i]}"
                            for i in range(len(pred_candidates))
                        )
                        st.markdown(
                            analysis_card(
                                "🌱 우리 학교 데이터 기반 예측식",
                                (
                                    '<div style="font-size:1.05em; line-height:1.7;'
                                    "font-family:'Courier New',monospace;"
                                    "background:#f4f7f2; padding:10px 14px; border-radius:6px;"
                                    f"border-left:3px solid {GREEN_MID};">"
                                    f"<b>생중량(g) ≈ {intercept:.3f}</b> {terms}"
                                    "</div>"
                                    '<div style="font-size:0.82em; color:#888; margin-top:6px;">'
                                    "※ 이 식은 우리 학교 81개체 데이터로 계산한 근사식이며,"
                                    "실제 데이터의 생중량 범위 안에서만 참고하세요."
                                    "</div>"
                                ),
                                accent=GREEN_MID,
                            ),
                            unsafe_allow_html=True,
                        )
                        y_pred = X @ coef
                        total_ss = float(np.sum((y - y.mean()) ** 2))
                        resid_ss = float(np.sum((y - y_pred) ** 2))
                        r2 = 1 - resid_ss / total_ss if total_ss > 0 else 0.0
                        st.metric(
                            "결정계수 (R²)",
                            f"{r2:.3f}",
                            delta="1에 가까울수록 예측식이 데이터를 잘 설명함",
                        )
                        st.caption(
                            "R²가 1에 가까우면 예측식이 데이터 패턴을 잘 반영한다는 뜻입니다."
                        )

            if chosen_col and chosen_col in growth_df.columns and "생중량" in growth_df.columns:
                st.markdown(
                    '<div style="color:#1a3c2a;font-weight:700;font-size:1.05em;margin:16px 0 6px 0;">'
                    f'🔍 선택 지표 "{chosen_col}" vs 생중량 — 상세 비교'
                    "</div>",
                    unsafe_allow_html=True,
                )
                d3 = growth_df[[chosen_col, "생중량"]].dropna()
                if len(d3) >= 5:
                    fig2 = go.Figure()
                    fig2.add_trace(go.Scatter(
                        x=d3[chosen_col].to_numpy(dtype=float),
                        y=d3["생중량"].to_numpy(dtype=float),
                        mode="markers",
                        marker=dict(
                            size=13, color=GREEN_MID, opacity=0.75,
                            line=dict(width=1.5, color="white"),
                        ),
                        hovertemplate=(
                            f"🌿 {chosen_col}: %{{x:.1f}}<br>⚖️ 생중량: %{{y:.2f}}g<extra></extra>"
                        ),
                    ))
                    add_trendline(fig2, d3[chosen_col], d3["생중량"], color=ORANGE)
                    r2_val = float(d3[chosen_col].corr(d3["생중량"]))
                    base_layout(fig2, height=360, xtitle=f"🌿 {chosen_col}", ytitle="⚖️ 생중량 (g)")
                    fig2.add_annotation(
                        x=0.96, y=0.97, xref="paper", yref="paper",
                        text=f"r = {r2_val:.3f}",
                        showarrow=False, bgcolor=GREEN_PALE, bordercolor=GREEN_MID,
                        borderwidth=1.5, borderpad=6,
                        font=dict(color=GREEN_DARK, size=14, weight="bold"),
                    )
                    st.plotly_chart(fig2, width="stretch")

            if "생중량" in growth_df.columns:
                st.markdown(
                    '<div style="color:#1a3c2a;font-weight:700;font-size:1.05em;margin:16px 0 6px 0;">'
                    "📊 생중량 히스토그램 — 81개체 분포"
                    "</div>",
                    unsafe_allow_html=True,
                )
                g4 = growth_df[["생중량"]].dropna()
                if len(g4) >= 3:
                    fig3 = go.Figure()
                    fig3.add_trace(go.Histogram(
                        x=g4["생중량"].to_numpy(),
                        nbinsx=max(8, min(30, len(g4) // 3)),
                        marker_color=GREEN_MID,
                        marker=dict(line=dict(color="white", width=1)),
                    ))
                    mv = float(g4["생중량"].mean())
                    base_layout(fig3, height=250, xtitle="생중량 (g)", ytitle="개체 수")
                    fig3.add_vline(
                        x=mv, line_dash="dash", line_color=ORANGE, line_width=2,
                        annotation_text=f"평균 {mv:.2f}g", annotation_position="top right",
                    )
                    st.plotly_chart(fig3, width="stretch")
                    st.caption(
                        "생중량 분포는 오른쪽으로 치우쳐 있어 — 소수 개체가 매우 크고 대부분은 작은 편입니다."
                    )

            st.markdown(
                '<div style="color:#1a3c2a;font-weight:700;font-size:1.05em;margin:16px 0 6px 0;">'
                "📥 생육 데이터 다운로드 (한글 깨짐 방지)"
                "</div>",
                unsafe_allow_html=True,
            )
            if not growth_df.empty:
                csv_bytes = growth_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="🌱 생육 결과 CSV 다운로드",
                    data=csv_bytes,
                    file_name="송도고_그린3팀_생육결과.csv",
                    mime="text/csv",
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")
'''

out_file = out / 'main.py'
out_file.write_text(MAIN, encoding='utf-8')

# ── 문법 검증 ──────────────────────────────────────────────────────────────
import ast
try:
    ast.parse(MAIN)
    print("✅ ast.parse 통과 — SyntaxError 없음")
except SyntaxError as e:
    print(f"❌ SyntaxError: {e.msg} | line {e.lineno}")
    print(f"   행: {MAIN.splitlines()[e.lineno-1][:120]}")

import py_compile
try:
    py_compile.compile(str(out_file), doraise=True)
    print("✅ py_compile 통과")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile 에러: {e}")

# ── 필수 함수 존재 확인 ──────────────────────────────────────────────────────
tree = ast.parse(MAIN)
funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
required = ['hex_to_rgb','base_layout','add_trendline','hero_card','info_card','analysis_card',
            'read_csv_bytes','std_cols']
missing = [f for f in required if f not in funcs]
print(f"\n정의된 함수: {sorted(funcs)}")
print(f"필수 함수 누락: {missing if missing else '✓ 없음'}")

# st.info + unsafe_allow_html 검사
bad = [(i+1, l.strip()[:80]) for i, l in enumerate(MAIN.splitlines())
       if 'st.info(' in l and 'unsafe_allow_html' in l]
print(f"\nst.info()에 unsafe_allow_html: {len(bad)}곳")
for ln, t in bad:
    print(f"  {ln}: {t}")

print(f"\nmain.py 저장: {out_file} / {len(MAIN)}자 / {len(MAIN.splitlines())}줄")
