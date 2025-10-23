import io
import zipfile
from datetime import datetime

import streamlit as st
from pydub import AudioSegment

# ====================== CẤU HÌNH TRANG ======================
st.set_page_config(page_title="MP3 Fade In/Out Zipper", page_icon="🎧", layout="centered")
st.title("🎧 MP3 Fade In/Out → ZIP")
st.caption("Upload nhiều file MP3, đặt thời gian fade in/out, rồi tải về 1 file ZIP.")

# ====================== SIDEBAR: THIẾT LẬP ======================
st.sidebar.header("Thiết lập Fade")
fade_in_ms = int(st.sidebar.number_input("Fade In (ms)", min_value=0, max_value=120_000, value=2000, step=100))
fade_out_ms = int(st.sidebar.number_input("Fade Out (ms)", min_value=0, max_value=120_000, value=3000, step=100))
normalize = st.sidebar.checkbox("Normalize âm lượng (khử peak)", value=True)
target_bitrate = st.sidebar.selectbox("Bitrate xuất", ["128k", "192k", "256k", "320k"], index=3)
prefix_out = st.sidebar.text_input("Prefix tên file xuất", value="faded_")

st.sidebar.markdown("---")
st.sidebar.caption("Gợi ý: nếu file ngắn, hãy giảm thời gian fade để tránh nuốt mất nội dung.")

# ====================== UPLOAD ======================
uploaded_files = st.file_uploader("Chọn các file MP3", type=["mp3"], accept_multiple_files=True)
process_btn = st.button("Xử lý & tạo ZIP", disabled=not uploaded_files)

# ====================== HÀM PHỤ TRỢ ======================
def safe_fade(segment: AudioSegment, fade_in_ms: int, fade_out_ms: int) -> AudioSegment:
    """
    Đảm bảo tổng thời gian fade không vượt quá độ dài track.
    Nếu vượt, tự co ngắn lại để tránh lỗi.
    """
    length = len(segment)
    fi = min(fade_in_ms, max(0, length // 2))
    fo = min(fade_out_ms, max(0, length - fi))
    if fi + fo > length:
        extra = fi + fo - length
        fo = max(0, fo - extra)
        if fi + fo > length:
            fi = max(0, length - fo)
    return segment.fade_in(fi).fade_out(fo)

def normalize_peak(seg: AudioSegment, headroom_db: float = 1.0) -> AudioSegment:
    """
    Giảm gain để peak còn -headroom_db dBFS (tránh clip).
    Không dùng audioop; chỉ dùng pydub.
    """
    try:
        if seg.max_dBFS > -headroom_db:
            change_db = -(seg.max_dBFS + headroom_db)
            return seg.apply_gain(change_db)
    except Exception:
        # Nếu backend không trả max_dBFS hợp lệ, bỏ qua normalize
        pass
    return seg

# ====================== XỬ LÝ ======================
if process_btn:
    if not uploaded_files:
        st.warning("Hãy chọn ít nhất 1 file MP3.")
    else:
        zip_buffer = io.BytesIO()
        errors = []

        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in uploaded_files:
                try:
                    # Đọc mp3
                    src = AudioSegment.from_file(f, format="mp3")

                    # Normalize peak (nếu chọn)
                    if normalize:
                        src = normalize_peak(src, headroom_db=1.0)

                    # Áp fade an toàn
                    processed = safe_fade(src, fade_in_ms=fade_in_ms, fade_out_ms=fade_out_ms)

                    # Xuất ra mp3 vào bộ nhớ
                    out_mp3 = io.BytesIO()
                    processed.export(out_mp3, format="mp3", bitrate=target_bitrate)
                    out_mp3.seek(0)

                    # Tên file trong ZIP
                    name = f.name if f.name.lower().endswith(".mp3") else f.name + ".mp3"
                    out_name = prefix_out + name

                    zf.writestr(out_name, out_mp3.read())

                except Exception as e:
                    errors.append(f"❌ {f.name}: {e}")

        zip_buffer.seek(0)
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"mp3_faded_{now}.zip"

        st.success("Hoàn tất! Bạn có thể tải về file ZIP bên dưới.")
        st.download_button(
            label="⬇️ Tải ZIP",
            data=zip_buffer,
            file_name=zip_name,
            mime="application/zip",
        )

        if errors:
            with st.expander("Chi tiết lỗi (nếu có)"):
                for e in errors:
                    st.write(e)
