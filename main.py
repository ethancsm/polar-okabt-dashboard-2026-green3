import os

os.makedirs('/home/user/outputs', exist_ok=True)

main_py = r'''import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ── 한글 폰트 ( Streamlit CSS ) ──────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""",
    unsafe_allow_html=True,
)

# ── 데이터 읽기 ───────────────────────────────────────────────────────────────
@st.cache_data
def read_csv_bytes(file):
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()

# ── 열 이름 표준화 ────────────────────────────────────────────────────────────
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
            parsed[bad] = (
                pd.to_datetime(parts[0], format="%Y%m%d")
                + pd.to_timedelta(parts[1].astype(int), unit="h")
            )
        df["time"] = parsed
    return df

# ── 학교명 ────────────────────────────────────────────────────────────────────
def school_name(filename):
    if filename is None:
        return "우리 학교"
    base = filename.rsplit(".", 1)[0]
    for sep in ("_", "-", " "):
        if sep in base:
            cand = base.split(sep, 1)[0]
            if len(cand) >= 2:
                return cand
    return base

# ── 추세선 ────────────────────────────────────────────────────────────────────
def add_trendline(fig, x, y):
    m = ~x.isna() & ~y.isna()
    if m.sum() < 2:
        return
    a, b = np.polyfit(x[m], y[m], 1)
    fig.add_trace(
        go.Scatter(
            x=[x[m].min(), x[m].max()],
            y=[a * x[m].min() + b, a * x[m].max() + b],
            mode="lines",
            line=dict(color="red", dash="dash"),
            name="추세선",
            hoverinfo="skip",
        )
    )

# ── 사이드바 ───────────────────────────────────────────────────────────────────
st.sidebar.title("📁 데이터 업로드")
env_file    = st.sidebar.file_uploader("환경 데이터 CSV", type="csv")
growth_file = st.sidebar.file_uploader("생육 결과 데이터 CSV", type="csv")
st.sidebar.caption("학교마다 열 이름·시간대 표기가 달라요. 어떤 파일이라도 자동으로 맞춰 읽어요.")

env_df    = pd.DataFrame()
growth_df = pd.DataFrame()
if env_file:
    with st.spinner("환경 데이터를 읽는 중..."):
        env_df = std_cols(read_csv_bytes(env_file))
if growth_file:
    with st.spinner("생육 데이터를 읽는 중..."):
        growth_df = std_cols(read_csv_bytes(growth_file))

sn_env    = school_name(env_file.name if env_file else None)
sn_growth = school_name(growth_file.name if growth_file else None)

# ── 페이지 ─────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="극지식물 생육 대시보드", layout="wide")
st.title("🌿 극지식물 개체별 생육 차이 분석")

if env_file or growth_file:
    parts = []
    if env_file:
        parts.append(f"환경 데이터: {sn_env}")
    if growth_file:
        parts.append(f"생육 데이터: {sn_growth}")
    st.caption(" · ".join(parts))
else:
    st.info("왼쪽 사이드바에서 CSV 파일을 올려주세요.")

# ═════════════════════════════════════════════════════════════════════════════
# 탭
# ═════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(
    ["📈 환경 데이터 분석", "🌱 개체별 생육 비교", "📊 생육 지표 상관·관측정보"]
)

# ═════════════════════════════════════════════════════════════════════════════
# 탭 1 ─ 환경 데이터
# ═════════════════════════════════════════════════════════════════════════════
with tab1:
    try:
        if env_df.empty:
            st.info("⚠️ 환경 데이터 CSV 를 올려주세요.")
        else:
            st.subheader("환경 데이터 시계열")
            if "time" not in env_df.columns:
                st.info("⚠️ time 열이 없어 시계열 그래프를 그릴 수 없어요.")
            else:
                num_cols = [c for c in env_df.columns
                            if c != "time" and pd.api.types.is_numeric_dtype(env_df[c])]
                plot_cols = [c for c in ["temperature","humidity","ec","ph","co2"] if c in num_cols]
                if not plot_cols:
                    st.info("⚠️ temperature, humidity, ec, ph, co2 중 맞는 숫자 열이 없어요.")
                else:
                    n = min(4, len(plot_cols))
                    # 모든 column을 한 번에 생성
                    cols = st.columns(n)
                    for i, col_name in enumerate(plot_cols[:n]):
                        e = env_df[["time", col_name]].dropna()
                        if len(e) < 2:
                            cols[i].info(f"⚠️ {col_name} 데이터가 충분하지 않아요.")
                            continue
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=e["time"].to_numpy(),
                            y=e[col_name].to_numpy(),
                            mode="lines",
                            name=col_name,
                            hovertemplate="%{x|%Y-%m-%d %H:%M}<br>%{y}<extra></extra>",
                        ))
                        fig.update_layout(
                            font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                            xaxis_title=col_name, yaxis_title="값",
                            height=200, showlegend=False,
                            margin=dict(t=20, b=20, l=30, r=10),
                        )
                        cols[i].plotly_chart(fig, width="stretch")

            st.subheader("환경 지표 요약")
            stat_cols = [c for c in ["temperature","humidity","ec","ph","co2"] if c in env_df.columns]
            if stat_cols:
                scols = st.columns(len(stat_cols))
                for i, cn in enumerate(stat_cols):
                    d = env_df[cn].dropna()
                    if len(d) == 0:
                        scols[i].info(f"⚠️ {cn} 데이터 없음")
                        continue
                    scols[i].metric(
                        label=cn,
                        value=f"{d.mean():.2f}",
                        delta=f"범위 {d.min():.2f} ~ {d.max():.2f}  ( 표준편차 {d.std():.2f} )",
                    )
            else:
                st.info("⚠️ 표시할 환경 지표 열이 없어요.")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# 탭 2 ─ 개체별 생육 비교
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    try:
        if growth_df.empty:
            st.info("⚠️ 생육 결과 CSV 를 올려주세요.")
        else:
            gcols_name = [
                "잎 수", "지상부 길이", "지하부 길이", "생중량",
                "지상부 질량", "지하부 질량",
            ]
            growth_cols = [c for c in gcols_name if c in growth_df.columns]
            if not growth_cols:
                st.info("⚠️ 잎 수, 길이, 질량 관련 열 중 맞는 것이 하나도 없어요.")
            else:
                st.subheader("개체별 생육 지표 요약")
                name_disp = {
                    "잎 수": "잎 수", "지상부 길이": "지상부 길이",
                    "지하부 길이": "지하부 길이", "생중량": "생중량",
                    "지상부 질량": "지상부 질량", "지하부 질량": "지하부 질량",
                }
                gscs = st.columns(len(growth_cols))
                for i, col in enumerate(growth_cols):
                    d = growth_df[col].dropna()
                    if len(d) == 0:
                        gscs[i].info(f"⚠️ {col} 데이터 없음")
                        continue
                    gscs[i].metric(
                        label=name_disp.get(col, col),
                        value=f"{d.mean():.2f}",
                        delta=f"범위 {d.min():.2f} ~ {d.max():.2f}  ( 표준편차 {d.std():.2f} )",
                    )

                st.divider()

                if "생중량" in growth_df.columns:
                    st.subheader("생중량 분포")
                    g = growth_df[["생중량"]].dropna()
                    if len(g) >= 3:
                        fig = go.Figure()
                        fig.add_trace(go.Histogram(
                            x=g["생중량"].to_numpy(),
                            nbinsx=max(10, min(30, len(g)//3)),
                            marker_color="#3498db",
                            hovertemplate="%{x:.2f}g<extra></extra>",
                        ))
                        mv = g["생중량"].mean()
                        fig.add_vline(x=mv, line_dash="dash", line_color="red",
                                      annotation_text=f"평균 {mv:.2f}g",
                                      annotation_position="top right")
                        fig.update_layout(
                            font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                            xaxis_title="생중량 (g)", yaxis_title="개체 수",
                            height=260, margin=dict(t=30, b=40, l=40, r=20),
                        )
                        st.plotly_chart(fig, width="stretch")

                bar_cols = [c for c in gcols_name if c in growth_df.columns]
                if bar_cols:
                    choice = st.selectbox("비교할 지표 선택", bar_cols, index=0)
                    st.write(f"### {choice} — 상위 5 개체 (초록) · 하위 5 개체 (빨강)")

                    s = growth_df[choice].dropna()
                    if len(s) >= 3:
                        ids = "개체번호" if "개체번호" in growth_df.columns else None
                        srt = s.sort_values(ascending=False)
                        top_ids    = set(srt.head(5).index)
                        bottom_ids = set(srt.tail(5).index)
                        colors, labels = [], []
                        for idx in srt.index:
                            if idx in top_ids:
                                colors.append("#2ecc71")
                            elif idx in bottom_ids:
                                colors.append("#e74c3c")
                            else:
                                colors.append("#95a5a6")
                            if ids is not None:
                                labels.append(str(growth_df[ids].iloc[idx]))
                            else:
                                labels.append(str(idx))
                        fig = go.Figure()
                        fig.add_trace(go.Bar(
                            x=labels, y=srt.values,
                            marker_color=colors,
                            hovertemplate="%{x} : %{y:.2f}<extra></extra>",
                        ))
                        fig.update_layout(
                            font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                            xaxis_title=choice, yaxis_title=f"{choice} 값",
                            height=320, showlegend=False,
                            margin=dict(t=30, b=40, l=40, r=20),
                        )
                        st.plotly_chart(fig, width="stretch")
                    else:
                        st.info(f"⚠️ '{choice}' 데이터가 충분하지 않아요.")

                # 산점도 행렬
                scatter_cols = [c for c in gcols_name if c in growth_df.columns]
                if len(scatter_cols) >= 2:
                    st.subheader("개체별 생육 지표 산점도 행렬")
                    sc = growth_df[scatter_cols].dropna()
                    if len(sc) >= 5:
                        n2 = min(4, len(scatter_cols))
                        n_plots = n2 * n2
                        # 모든 figure 을 먼저 생성
                        figs = []
                        for ri in range(n2):
                            for ci in range(n2):
                                xcol, ycol = scatter_cols[ci], scatter_cols[ri]
                                d = sc[[xcol, ycol]].dropna()
                                if len(d) < 2:
                                    figs.append(None)
                                    continue
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=d[xcol].to_numpy(dtype=float),
                                    y=d[ycol].to_numpy(dtype=float),
                                    mode="markers",
                                    marker=dict(size=7, color="#2980b9", opacity=0.7),
                                    hovertemplate="%{x:.2f}, %{y:.2f}",
                                    name=f"{xcol}_vs_{ycol}",
                                ))
                                if ri != ci:
                                    add_trendline(fig, d[xcol], d[ycol])
                                fig.update_layout(
                                    font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                                    xaxis_title=xcol, yaxis_title=ycol,
                                    height=200, showlegend=False,
                                    margin=dict(t=18, b=18, l=28, r=8),
                                )
                                figs.append(fig)
                        # 한 번에 모든 column 생성 → 각 cell 에 표시
                        grid_cols = st.columns(n_plots)
                        for i, fig in enumerate(figs):
                            if fig is None:
                                grid_cols[i].info("데이터 부족")
                            else:
                                grid_cols[i].plotly_chart(fig, width="stretch")
                    else:
                        st.info("⚠️ 산점도 행렬을 그리려면 최소 5 개체 이상의 데이터가 필요해요.")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# 탭 3 ─ 상관 분석 및 측정 정보
# ═════════════════════════════════════════════════════════════════════════════
with tab3:
    try:
        if growth_df.empty:
            st.info("⚠️ 생육 결과 CSV 를 올려주세요.")
        else:
            st.subheader("📊 생육 지표 간 상관계수 (Pearson)")
            corr_cols = [c for c in gcols_name if c in growth_df.columns]
            if len(corr_cols) < 2:
                st.info("⚠️ 상관계수를 계산할 지표 열이 2 개 미만이에요.")
            else:
                d = growth_df[corr_cols].dropna()
                if len(d) < 3:
                    st.info("⚠️ 상관계수 계산을 위해 적어도 3 개체 이상의 데이터가 필요해요.")
                else:
                    corr = d.corr(method="pearson")
                    x_lbl = list(dict.fromkeys(corr.columns))
                    y_lbl = list(dict.fromkeys(corr.index))
                    fig = go.Figure(go.Heatmap(
                        z=corr.values,
                        x=x_lbl, y=y_lbl,
                        colorscale="RdBu_r",
                        zmin=-1, zmax=1,
                        text=corr.values.round(2),
                        texttemplate="%{text}",
                        textfont=dict(color="black", size=11),
                        hovertemplate="%{y} vs %{x} : %{z:.2f}<extra></extra>",
                    ))
                    fig.update_layout(
                        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                        margin=dict(t=30, b=40, l=40, r=20),
                    )
                    st.plotly_chart(fig, width="stretch")

            if len(corr_cols) >= 2:
                st.divider()
                st.subheader("생중량과 가장 상관 높은 지표")
                wcol = "생중량" if "생중량" in corr_cols else corr_cols[-1]
                others = [c for c in corr_cols if c != wcol]
                d2 = growth_df[[wcol] + others].dropna()
                if len(d2) >= 3 and others:
                    pairs = [(tc, d2[wcol].corr(d2[tc])) for tc in others]
                    pairs.sort(key=lambda x: abs(x[1]), reverse=True)
                    n_show = min(3, len(pairs))
                    rcs = st.columns(n_show)
                    for i, (tc, v) in enumerate(pairs[:n_show]):
                        direction = (
                            "강한 양의 상관" if v > 0.5
                            else "약한 양의 상관" if v > 0
                            else "약한 음의 상관" if v > -0.5
                            else "강한 음의 상관"
                        )
                        rcs[i].metric(label=f"{tc} 와의 상관계수", value=f"{v:.3f}", delta=direction)

            pred_cols = [c for c in ["잎 수","지상부 길이","지하부 길이"] if c in growth_df.columns]
            if "생중량" in growth_df.columns and pred_cols:
                st.divider()
                st.subheader("📐 생중량 예측식 (선형 근사)")
                d3 = growth_df[["생중량"] + pred_cols].dropna()
                if len(d3) >= len(pred_cols) + 1:
                    X = np.column_stack([np.ones(len(d3)), d3[pred_cols].to_numpy(dtype=float)])
                    y = d3["생중량"].to_numpy(dtype=float)
                    coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
                    intercept = coef[0]
                    terms = " + ".join(f"{coef[i+1]:.4f} \\times {pred_cols[i]}" for i in range(len(pred_cols)))
                    st.latex(f"\\text{{생중량}} \\approx {intercept:.4f} + {terms}")
                    st.caption("※ 이 식은 우리 학교 데이터 범위 안에서만 참고하세요.")
                    y_pred = X @ coef
                    r2 = 1 - np.sum((y - y_pred)**2) / np.sum((y - y.mean())**2)
                    st.metric("결정계수 (R²)", f"{r2:.3f}")
                    st.caption(
                        "R² 가 1 에 가까울수록 예측식이 데이터를 잘 설명해요. "
                        "0 에 가까우면 관계로 설명하기 어려운 다른 요인이 크다는 뜻이에요."
                    )

            st.divider()
            st.subheader("📋 데이터 측정 정보")
            ic = st.columns(2)

            if not env_df.empty:
                ic[0].subheader("환경 데이터")
                ic[0].write(f"• 행 수: {len(env_df)} 행")
                if "time" in env_df.columns:
                    td = env_df["time"].dropna()
                    if len(td) >= 2:
                        span = td.max() - td.min()
                        ic[0].write(
                            f"• 측정 기간: {td.min().strftime('%Y-%m-%d')} ~ "
                            f"{td.max().strftime('%Y-%m-%d')} ({span.days}일)"
                        )
                        ic[0].write(f"• 평균 측정 간격: 약 {span.total_seconds()/(len(td)-1)/3600:.1f}시간")
                num_env = [c for c in env_df.columns if c != "time" and pd.api.types.is_numeric_dtype(env_df[c])]
                ic[0].write(f"• 측정 지표: {', '.join(num_env) if num_env else '없음'}")
            else:
                ic[0].info("⚠️ 환경 데이터가 없어요.")

            if not growth_df.empty:
                ic[1].subheader("생육 데이터")
                ic[1].write(f"• 개체 수: {len(growth_df)} 개체")
                g_meas = [c for c in gcols_name if c in growth_df.columns]
                ic[1].write(f"• 측정 항목: {', '.join(g_meas) if g_meas else '없음'}")
                if "생중량" in growth_df.columns:
                    gv = growth_df["생중량"].dropna()
                    ic[1].write(f"• 생중량 범위: {gv.min():.2f}g ~ {gv.max():.2f}g")

            st.divider()
            if not growth_df.empty:
                st.subheader("📥 생육 데이터 다운로드 ( 한글 깨짐 방지 )")
                csv_bytes = growth_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="생육 데이터 CSV 다운로드",
                    data=csv_bytes,
                    file_name="생육결과_다운로드.csv",
                    mime="text/csv",
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")
'''

with open('/home/user/outputs/main.py', 'w', encoding='utf-8') as f:
    f.write(main_py)

req_txt = """streamlit
pandas
plotly
numpy
scipy
"""
with open('/home/user/outputs/requirements.txt', 'w', encoding='utf-8') as f:
    f.write(req_txt)

print(f"main.py 저장 완료 — {len(main_py)} 자 / {len(main_py.split(chr(10)))} 줄")
print("requirements.txt 저장 완료")
# 문법 체크
import py_compile
try:
    py_compile.compile('/home/user/outputs/main.py', doraise=True)
    print("✅ Python 문법 체크 통과")
except py_compile.PyCompileError as e:
    print(f"❌ 문법 에러: {e}")
