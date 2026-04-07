import streamlit as st
import streamlit.components.v1 as components

def render_maturity_model(levels):
    st.markdown("""
    <style>
    .maturity-wrapper { display:flex; flex-direction:column; gap:20px; margin-top:20px; }
    .level { border:1px solid #D1D5DB; border-radius:10px; overflow:hidden; background:white; }
    .level-header {
        background:#2F3E8F; color:white; display:flex; justify-content:space-between;
        padding:12px 16px; font-weight:600; font-size:18px;
    }
    .segments { display:flex; }
    .segment { flex:1; padding:14px; text-align:center; border-right:1px solid #E5E7EB; }
    .segment:last-child { border-right:none; }
    .segment-label { font-size:13px; margin-bottom:6px; }
    .segment-score { font-weight:600; font-size:18px; }
    .arrow { text-align:center; font-size:28px; color:#9CA3AF; }
    </style>
    """, unsafe_allow_html=True)

    html = '<div class="maturity-wrapper">'

    for i, level in enumerate(levels):
        segments_html = ""
        for seg in level["segments"]:
            segments_html += f"""
            <div class="segment" style="background:{seg['color']}">
                <div class="segment-label">{seg['label']}</div>
                <div class="segment-score">{seg['score'] if seg['score'] is not None else "N/A"}%</div>
            </div>
            """

        html += f"""
        <div class="level">
            <div class="level-header">
                <span>{level['label']}</span>
                <span>{level['score'] if level['score'] is not None else "N/A"}%</span>
            </div>
            <div class="segments">{segments_html}</div>
        </div>
        """

        if i < len(levels) - 1:
            html += '<div class="arrow">↓</div>'

    html += "</div>"
    components.html(html, height=220 * max(len(levels), 1), scrolling=False)