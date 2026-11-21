import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── 컬러 헬퍼 (상단으로 이동 — 탭2에서 먼저 호출되므로) ─────────────────────
def hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

# ─── 한글 폰트 & 커스텀 CSS ───────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}

.stApp {
    background: #f4f7f2;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1b4332 0%, #2d6a4f 100%);
    color: #fff;
}
section[data-testid="stSidebar"] .stTextInput,
section[data-testid="stSidebar"] .stFileUploader {
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.2);
    color: #fff;
}
section[data-testid="stSidebar"] label {
    color: #d8f3dc !important;
}
section[data-testid="stSidebar"] .st-emotion-cache-1v0mbw5 {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.15);
    color: #fff;
}

div[data-testid="stTabs"] button [data-testid="stMarkdownContainer"] p {
    font-weight: 700;
    color: #1b4332;
}

div[data-testid="stMetric"] {
    background: white;
    border-radius: 12px;
    padding: 12px 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border: 1px solid #d8f3dc;
    transition: transform 0.2s;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
}

div[data-testid="stInfo"] {
    background: #d8f3dc;
    border-left: 4px solid #2d6a4f;
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

# ─── 아이콘 헬퍼 ──────────────────────────────────────────────────────────────
def icon(name):
    return f"<span>{name}</span>"

# ─── CSV 읽기 ────────────────────────────────────────────────────────────────
@st.cache_data
def read_csv_bytes(file):
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()

# ─── 열 이름 표준화 ──────────────────────────────────────────────────────────
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

# ─── 학교명 ──────────────────────────────────────────────────────────────────
def school_name(filename):
    if filename is None:
        return "우리 학교"
    base = str(filename).rsplit(".", 1)[0]
    for sep in ("_", "-", " "):
        if sep in base:
            cand = base.split(sep, 1)[0]
            if len(cand) >= 2:
                return cand
    return base

# ─── 추세선 ──────────────────────────────────────────────────────────────────
def add_trendline(fig, x, y, color="#e76f51"):
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

# ─── 공통 그래프 스타일 ──────────────────────────────────────────────────────
def base_layout(fig, height=300, xtitle="", ytitle=""):
    fig.update_layout(
        font=dict(family="Noto Sans KR, Malgun Gothic, Apple SD Gothic Neo, sans-serif", size=12),
        xaxis_title=xtitle,
        yaxis_title=ytitle,
        height=height,
        plot_bgcolor="#fafcfa",
        paper_bgcolor="#fafcfa",
        margin=dict(t=30, b=40, l=40, r=20),
        xaxis=dict(gridcolor="#eef5ee", zerolinecolor="#d8f3dc"),
        yaxis=dict(gridcolor="#eef5ee", zerolinecolor="#d8f3dc"),
    )

# ─── 컬러 팔레트 ─────────────────────────────────────────────────────────────
GREEN_DARK  = "#1b4332"
GREEN_MID   = "#2d6a4f"
GREEN_LIGHT = "#95d5b2"
GREEN_PALE  = "#d8f3dc"
ACCENT      = "#e76f51"

# ─── 사이드바 ────────────────────────────────────────────────────────────────
st.sidebar.title("🌿 데이터 업로드")
st.sidebar.markdown("---")
env_file = st.sidebar.file_uploader("📊 환경 데이터 CSV", type="csv")
growth_file = st.sidebar.file_uploader("🌱 생육 결과 데이터 CSV", type="csv")
st.sidebar.markdown("---")

if env_file or growth_file:
    st.sidebar.caption("✅ 파일이 업로드되었습니다")
else:
    st.sidebar.info("📁 CSV 파일을 올려주세요.\n학교마다 열 이름이 달라도 자동으로 맞춰 읽습니다.")

growth_cols_list = ["잎 수", "지상부 길이", "지하부 길이", "생중량",
                    "지상부 질량", "지하부 질량"]
chosen_col = st.sidebar.selectbox(
    "📏 비교할 생육 지표 선택",
    growth_cols_list,
    index=0,
)

# 데이터 로드
env_df = pd.DataFrame()
growth_df = pd.DataFrame()

if env_file is not None:
    with st.spinner("📊 환경 데이터를 읽는 중..."):
        env_df = std_cols(read_csv_bytes(env_file))
if growth_file is not None:
    with st.spinner("🌱 생육 데이터를 읽는 중..."):
        growth_df = std_cols(read_csv_bytes(growth_file))

sn_env = school_name(env_file.name if env_file else None)
sn_growth = school_name(growth_file.name if growth_file else None)

# ─── 페이지 설정 ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="극지식물 생육 분석", layout="wide")
st.title("🌿 지하부의 무게가 무거울수록 잎의 개수가 많을까?")

if env_file or growth_file:
    parts = []
    if env_file:
        parts.append(f"📊 환경 데이터 · {sn_env}")
    if growth_file:
        parts.append(f"🌱 생육 데이터 · {sn_growth}")
    st.caption(" · ".join(parts))
else:
    st.info("📁 왼쪽 사이드바에서 CSV 파일을 올려주세요.")

st.caption("🔬 같은 스마트팜에서 자란 극지식물 81개체 — 왜 어떤 식물은 크게 자라고, 어떤 식물은 작을까?")
st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# 탭
# ═══════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs([
    "🏠 실험 개요 & 핵심 결과",
    "📈 환경 데이터 변화",
    "🔬 잎 수 vs 생중량 관계 분석",
])

# ═══════════════════════════════════════════════════════════════════════════
# 탭 1 ─ 실험 개요 & 핵심 결과
# ═══════════════════════════════════════════════════════════════════════════
with tab1:
    try:
        # ── 실험 목적 카드 ──────────────────────────────────────────────────
        st.markdown("""
<div style="background: linear-gradient(135deg, #1b4332 0%, #2d6a4f 100%);
            border-radius: 16px; padding: 24px; color: white; margin-bottom: 24px;">
    <h2 style="margin:0 0 12px 0; font-size:1.3em;">🎯 연구 목적</h2>
    <p style="margin:0; line-height:1.7; opacity:0.92;">
        같은 스마트팜에서 함께 자란 극지식물들이 <b>왜 어떤 개체는 크게 자라고, 어떤 개체는 작게 자라는지</b>를
        환경 데이터와 생육 결과를 비교·분석하여 밝히고자 합니다.
        특히 <b>지하부 질량(무게)과 잎 수 사이의 관계</b>를 수치와 그래프로 확인하고,
        향후 재배 개선을 위한 단서를 찾는 것이 목표입니다.
    </p>
</div>
""", unsafe_allow_html=True)

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown(f'<div style="color:{GREEN_DARK};font-weight:700;font-size:1.1em;margin-bottom:8px;">📊 데이터 현황</div>', unsafe_allow_html=True)
            info_cards = st.columns(2)
            if env_file:
                info_cards[0].metric("🌡️ 환경 데이터 행 수", f"{len(env_df):,}")
                if "time" in env_df.columns:
                    td = env_df["time"].dropna()
                    if len(td) >= 2:
                        span = td.max() - td.min()
                        info_cards[0].metric("📅 측정 기간", f"{td.min().strftime('%m/%d')} ~ {td.max().strftime('%m/%d')} ({span.days}일)")
            else:
                info_cards[0].info("⚠️ 환경 CSV 미업로드")
            if growth_file:
                info_cards[1].metric("🌱 생육 데이터 개체 수", f"{len(growth_df)}개체")
            else:
                info_cards[1].info("⚠️ 생육 CSV 미업로드")

            st.markdown("<br>", unsafe_allow_html=True)

            st.markdown(f'<div style="color:{GREEN_DARK};font-weight:700;font-size:1.1em;margin-bottom:8px;">🌡️ 스마트팜 환경 요약 (전체 평균)</div>', unsafe_allow_html=True)
            env_stat_cols = [c for c in ("temperature", "humidity", "ec", "ph", "co2") if c in env_df.columns]
            if env_stat_cols:
                ecols = st.columns(len(env_stat_cols))
                label_map = {
                    "temperature": "🌡️ 온도 (℃)",
                    "humidity": "💧 습도 (%)",
                    "ec": "🧪 EC (mS/cm)",
                    "ph": "🧫 pH",
                    "co2": "🌬️ CO₂ (ppm)",
                }
                for i, cn in enumerate(env_stat_cols):
                    d = env_df[cn].dropna()
                    if len(d) == 0:
                        ecols[i].info(f"⚠️ {cn} 데이터 없음")
                        continue
                    unit = {"temperature": "℃", "humidity": "%", "ec": "mS/cm", "ph": "", "co2": "ppm"}[cn]
                    ecols[i].metric(
                        label=label_map.get(cn, cn),
                        value=f"{d.mean():.1f}{unit}",
                        delta=f"범위 {d.min():.1f} ~ {d.max():.1f}",
                    )
            else:
                st.info("⚠️ 표시할 환경 지표 열이 없어요.")

        with col_b:
            st.markdown(f'<div style="color:{GREEN_DARK};font-weight:700;font-size:1.1em;margin-bottom:8px;">🌱 생육 지표 요약 (81개체 평균)</div>', unsafe_allow_html=True)
            gcols = ["잎 수", "지상부 길이", "지하부 길이", "생중량", "지상부 질량", "지하부 질량"]
            gdata = []
            for col_name in gcols:
                if col_name in growth_df.columns:
                    d = growth_df[col_name].dropna()
                    if len(d) == 0:
                        continue
                    gdata.append((col_name, d.mean(), d.min(), d.max(), d.std()))

            for i in range(0, len(gdata), 2):
                row_cols = st.columns(2)
                for j in range(2):
                    if i + j < len(gdata):
                        cn, mean_v, min_v, max_v, std_v = gdata[i + j]
                        row_cols[j].metric(
                            label=cn,
                            value=f"{mean_v:.2f}",
                            delta=f"범위 {min_v:.2f} ~ {max_v:.2f}  (σ {std_v:.2f})",
                        )
                    else:
                        row_cols[j].empty()

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f'<div style="color:{GREEN_DARK};font-weight:700;font-size:1.1em;margin-bottom:8px;">💡 핵심 발견</div>', unsafe_allow_html=True)

            if "생중량" in growth_df.columns and "잎 수" in growth_df.columns:
                g2 = growth_df[["생중량", "잎 수"]].dropna()
                if len(g2) >= 10:
                    bw = g2["생중량"].median()
                    low = g2[g2["생중량"] <= bw]
                    high = g2[g2["생중량"] > bw]
                    if len(low) >= 3 and len(high) >= 3:
                        diff = high["잎 수"].mean() - low["잎 수"].mean()
                        r = float(g2["생중량"].corr(g2["잎 수"]))
                        r_tag = (
                            "(강한 양의 상관)" if r > 0.5
                            else "(중간 정도의 양의 상관)" if r > 0.3
                            else "(약한 양의 상관)"
                        )
                        st.markdown(
                            f"""
<div style="background:#d8f3dc; border-left:4px solid {GREEN_MID};
            border-radius:8px; padding:12px 16px; line-height:1.8;">
✅ <b>지하부 질량 기준</b>으로 비교했을 때:<br>
• <b>질량이 높은 그룹</b>(평균 생중량 {high["생중량"].mean():.2f}g) → 잎 수 평균 <b>{high["잎 수"].mean():.1f}장</b><br>
• <b>질량이 낮은 그룹</b>(평균 생중량 {low["생중량"].mean():.2f}g) → 잎 수 평균 <b>{low["잎 수"].mean():.1f}장</b><br>
• 두 그룹 간 잎 수 차이: <b>약 {diff:.1f}장</b><br>
• 생중량과 잎 수의 상관계수: <b>r = {r:.3f}</b> {r_tag}
</div>
""",
                            unsafe_allow_html=True,
                        )

            if "생중량" in growth_df.columns:
                g3 = growth_df[["생중량"]].dropna()
                if len(g3) >= 3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown(f'<div style="color:{GREEN_DARK};font-weight:700;font-size:1.1em;margin-bottom:8px;">📊 생중량 분포 — 상위/하위 개체</div>', unsafe_allow_html=True)

                    s = g3["생중량"].dropna().sort_values(ascending=False)
                    top5_ids = set(s.head(5).index)
                    bottom5_ids = set(s.tail(5).index)

                    fig = go.Figure()
                    colors = []
                    labels = []
                    for idx in s.index:
                        if idx in top5_ids:
                            colors.append(ACCENT)
                        elif idx in bottom5_ids:
                            colors.append(GREEN_DARK)
                        else:
                            colors.append(GREEN_LIGHT)
                        if "개체번호" in growth_df.columns:
                            labels.append(str(growth_df["개체번호"].iloc[idx]))
                        else:
                            labels.append(str(idx + 1))
                    fig.add_trace(go.Bar(
                        x=labels,
                        y=s.to_numpy(dtype=float),
                        marker_color=colors,
                        hoverinfo="skip",
                    ))
                    base_layout(fig, height=260, xtitle="개체", ytitle="생중량 (g)")
                    fig.add_vline(x=len(s) / 2, line_dash="dot", line_color="#95d5b2", opacity=0.5)
                    st.plotly_chart(fig, width="stretch")
                    st.caption("🔴 빨강 = 상위 5개체(생중량 큼)  ·  🟢 초록 = 하위 5개체(생중량 작음)  ·  연두 = 나머지")

    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# 탭 2 ─ 환경 데이터 변화
# ═══════════════════════════════════════════════════════════════════════════
with tab2:
    try:
        if env_df.empty:
            st.info("⚠️ 환경 데이터 CSV를 올려주세요.")
        else:
            st.markdown(
                f'<div style="color:{GREEN_DARK};font-weight:700;font-size:1.2em;margin-bottom:12px;">'
                f'📈 {sn_env} 환경 데이터 — 시간에 따른 변화'
                f'</div>',
                unsafe_allow_html=True,
            )

            env_num_cols = [
                c for c in env_df.columns
                if c != "time" and pd.api.types.is_numeric_dtype(env_df[c])
            ]
            plot_targets = [c for c in ("temperature", "humidity", "ec", "ph", "co2") if c in env_num_cols]
            if plot_targets:
                n = min(4, len(plot_targets))
                chart_cols = st.columns(n)
                color_map = {
                    "temperature": "#e76f51",
                    "humidity": "#457b9d",
                    "ec": "#2d6a4f",
                    "ph": "#9b5de5",
                    "co2": "#f15bb5",
                }
                for i, col_name in enumerate(plot_targets[:n]):
                    e = env_df[["time", col_name]].dropna()
                    if len(e) < 2:
                        with chart_cols[i]:
                            st.info(f"⚠️ {col_name} 데이터가 충분하지 않아요.")
                        continue
                    fig = go.Figure()
                    color = color_map.get(col_name, "#2d6a4f")
                    rgb = hex_to_rgb(color)
                    fig.add_trace(go.Scatter(
                        x=e["time"].to_numpy(),
                        y=e[col_name].to_numpy(),
                        mode="lines",
                        fill="tozeroy",
                        fillcolor=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.15)",
                        line=dict(color=color, width=1.5),
                    ))
                    base_layout(fig, height=180, xtitle="", ytitle=col_name)
                    chart_cols[i].plotly_chart(fig, width="stretch")
            else:
                st.info("⚠️ temperature·humidity·ec·ph·co2 중 맞는 숫자 열이 없어요.")

            st.markdown("<br>", unsafe_allow_html=True)

            st.markdown(
                f'<div style="color:{GREEN_DARK};font-weight:700;font-size:1.2em;margin-bottom:8px;">'
                f'📋 {sn_env} 환경 데이터 원본 (처음 50행)'
                f'</div>',
                unsafe_allow_html=True,
            )

            display_cols = ["time"] + env_num_cols[:5]
            show_df = env_df[display_cols].copy()
            if "time" in show_df.columns:
                show_df["time"] = show_df["time"].dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(show_df.head(50), width="stretch", height=320)

            st.markdown("<br>", unsafe_allow_html=True)

            st.markdown(
                f'<div style="color:{GREEN_DARK};font-weight:700;font-size:1.2em;margin-bottom:8px;">'
                f'📊 환경 지표 요약표'
                f'</div>',
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
                    delta=f"최소 {d.min():.2f}  ·  최대 {d.max():.2f}  ·  표준편차 {d.std():.2f}",
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# 탭 3 ─ 잎 수 vs 생중량 관계 분석
# ═══════════════════════════════════════════════════════════════════════════
with tab3:
    try:
        if growth_df.empty:
            st.info("⚠️ 생육 결과 CSV를 올려주세요.")
        else:
            st.markdown("""
<div style="background: linear-gradient(135deg, #2d6a4f 0%, #40916c 100%);
            border-radius: 16px; padding: 20px; color: white; margin-bottom: 24px;">
    <h2 style="margin:0 0 8px 0; font-size:1.2em;">🔬 핵심 질문</h2>
    <p style="margin:0; line-height:1.6; opacity:0.92; font-size:0.95em;">
        <b>지하부의 무게가 무거울수록 잎의 개수가 많을까?</b><br>
        같은 스마트팜에서 키운 81개체 데이터를 낱낱이 비교하여 답을 찾아봅니다.
    </p>
</div>
""", unsafe_allow_html=True)

            if "잎 수" in growth_df.columns and "생중량" in growth_df.columns:
                st.markdown(
                    f'<div style="color:{GREEN_DARK};font-weight:700;font-size:1.1em;margin-bottom:8px;">'
                    f'🌿 잎 수 vs 생중량 — 산점도'
                    f'</div>',
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
                            size=10,
                            color=d["생중량"].to_numpy(dtype=float),
                            colorscale=[[0, GREEN_PALE], [1, ACCENT]],
                            showscale=True,
                            colorbar=dict(title="생중량(g)", thickness=15, xanchor="right"),
                            line=dict(width=1, color="white"),
                        ),
                        hovertemplate="잎 수: %{x:.0f}장<br>생중량: %{y:.2f}g<extra></extra>",
                    ))
                    add_trendline(fig, d["잎 수"], d["생중량"], color=ACCENT)

                    r_val = float(d["잎 수"].corr(d["생중량"]))
                    base_layout(fig, height=380, xtitle="잎 수 (장)", ytitle="생중량 (g)")
                    fig.add_annotation(
                        x=0.95, y=0.95,
                        xref="paper", yref="paper",
                        text=f"상관계수 r = {r_val:.3f}",
                        showarrow=False,
                        bgcolor=GREEN_PALE,
                        bordercolor=GREEN_MID,
                        borderwidth=1,
                        font=dict(color=GREEN_DARK, size=13, weight="bold"),
                    )
                    st.plotly_chart(fig, width="stretch")

                    st.markdown("<br>", unsafe_allow_html=True)

                    r_desc = (
                        "강한 양의 상관 — 잎 수가 많을수록 생중량도 확실히 커지는 경향" if r_val > 0.5
                        else "중간 정도의 양의 상관 — 대체로 잎 수가 많을수록 생중량이 커지는 경향" if r_val > 0.3
                        else "약한 양의 상관 — 잎 수와 생중량 사이에 약한 양의 관계가 보임"
                        if r_val > 0 else "음의 상관 — 잎 수가 많을수록 생중량이 오히려 작아지는 경향"
                    )
                    st.markdown(
                        f"""
<div style="background:#d8f3dc; border-left:4px solid {GREEN_MID};
            border-radius:8px; padding:12px 16px; line-height:1.7;">
📌 <b>상관계수 r = {r_val:.3f}</b><br>
<span style="color:#2d6a4f;">{r_desc}</span><br><br>
💡 <b>상관계수(r)</b>란 두 변수 사이의 선형 관계 강도를 -1 ~ 1 사이의 숫자로 나타낸 것입니다.
1에 가까울수록 함께 증가, -1에 가까울수록 반대로 움직이며, 0에 가까우면 선형 관계가 거의 없습니다.
</div>
""",
                        unsafe_allow_html=True,
                    )

            if "생중량" in growth_df.columns:
                pred_candidates = [c for c in ["잎 수", "지상부 길이", "지하부 길이"] if c in growth_df.columns]
                if pred_candidates:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown(
                        f'<div style="color:{GREEN_DARK};font-weight:700;font-size:1.1em;margin-bottom:8px;">'
                        f'📐 생중량 예측식 (선형 근사)'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    d2 = growth_df[["생중량"] + pred_candidates].dropna()
                    if len(d2) >= len(pred_candidates) + 1:
                        X = np.column_stack([np.ones(len(d2)), d2[pred_candidates].to_numpy(dtype=float)])
                        y = d2["생중량"].to_numpy(dtype=float)
                        coef, *_ = np.linalg.lstsq(X, y, rcond=None)

                        intercept = float(coef[0])
                        terms = " + ".join(
                            f"{coef[i+1]:.4f}×{pred_candidates[i]}"
                            for i in range(len(pred_candidates))
                        )
                        st.markdown(
                            f"""
<div style="background:#d8f3dc; border-left:4px solid {GREEN_MID};
            border-radius:8px; padding:14px 18px; margin-bottom:12px;">
    <div style="font-weight:700; color:{GREEN_DARK}; margin-bottom:6px;">🌱 우리 학교 예측식</div>
    <div style="font-size:1.05em; line-height:1.6;">
        <b>생중량(g) ≈ {intercept:.3f}</b> {terms}
    </div>
    <div style="font-size:0.85em; color:#555; margin-top:6px;">
        ※ 이 식은 우리 학교 81개체 데이터로 계산한 근사식이며, 실제 데이터의 생중량 범위 안에서만 참고하세요.
    </div>
</div>
""",
                            unsafe_allow_html=True,
                        )

                        y_pred = X @ coef
                        total_ss = float(np.sum((y - y.mean()) ** 2))
                        resid_ss = float(np.sum((y - y_pred) ** 2))
                        r2 = 1 - resid_ss / total_ss if total_ss > 0 else 0.0
                        st.metric("결정계수 (R²)", f"{r2:.3f}",
                                  delta="1에 가까울수록 예측식이 데이터를 잘 설명함")

            if chosen_col and chosen_col in growth_df.columns and "생중량" in growth_df.columns:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    f'<div style="color:{GREEN_DARK};font-weight:700;font-size:1.1em;margin-bottom:8px;">'
                    f'🔍 선택한 지표 "{chosen_col}" vs 생중량'
                    f'</div>',
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
                            size=11,
                            color=GREEN_MID,
                            opacity=0.7,
                            line=dict(width=1, color="white"),
                        ),
                        hovertemplate=f"{chosen_col}: %{{x:.1f}}<br>생중량: %{{y:.2f}}g<extra></extra>",
                    ))
                    add_trendline(fig2, d3[chosen_col], d3["생중량"], color=ACCENT)
                    r2_val = float(d3[chosen_col].corr(d3["생중량"]))
                    base_layout(fig2, height=340, xtitle=chosen_col, ytitle="생중량 (g)")
                    fig2.add_annotation(
                        x=0.95, y=0.95,
                        xref="paper", yref="paper",
                        text=f"r = {r2_val:.3f}",
                        showarrow=False,
                        bgcolor=GREEN_PALE,
                        bordercolor=GREEN_MID,
                        borderwidth=1,
                        font=dict(color=GREEN_DARK, size=13, weight="bold"),
                    )
                    st.plotly_chart(fig2, width="stretch")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f'<div style="color:{GREEN_DARK};font-weight:700;font-size:1.1em;margin-bottom:8px;">'
                f'📥 생육 데이터 다운로드'
                f'</div>',
                unsafe_allow_html=True,
            )
            if not growth_df.empty:
                csv_bytes = growth_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="🌱 생육 결과 CSV 다운로드 (한글 깨짐 없음)",
                    data=csv_bytes,
                    file_name="생육결과_다운로드.csv",
                    mime="text/csv",
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")
