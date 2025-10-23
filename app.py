import io
import zipfile
from datetime import datetime

import streamlit as st
from pydub import AudioSegment

# =============== CẤU HÌNH & STATE ===============
st.set_page_config(page_title="MP3 Fade In/Out Zipper", page_icon="🎧", layout="centered")

if "processing" not in st.session_state:
    st.session_state.processing = False  # đang xử lý hay không

st.title("🎧 MP3 Fade In/Out → ZIP")
st.caption("Upload nhiều file MP3, đặt thời gian fade in/out, rồi tải về 1 file ZIP.")

# =============== SIDEBAR: THIẾT LẬP ===============
st.sidebar.header("Thiết lập Fade")
fade_in_ms = int(st.sidebar.number_input("Fade In (ms)", min_value=0, max_value=120_000, value=2000, step=100))
fade_out_ms = int(st.sidebar.number_input("Fade Out (ms)", min_value=0, max_value=120_000, value=3000, step=100))
normalize = st.sidebar.checkbox("Normalize âm lượng (khử peak)", value=True)
target_bitrate = st.sidebar.selectbox("Bitrate xuất", ["128k", "192k", "256k", "320k"], index=3)
prefix_out = st.sidebar.text_input("Prefix tên file xuất", value="faded_")

st.sidebar.markdown("---")
st.sidebar.caption("upload toàn bộ file lên, bấm xử lý và file zip. Sau đó download")

# =============== UPLOAD ===============
uploaded_files = st.file_uploader("Chọn các file MP3", type=["mp3"], accept_multiple_files=True)

# Nút xử lý: bị disable khi chưa có file hoặc đang xử lý
process_clicked = st.button(
    "Xử lý & tạo ZIP",
    disabled=(not uploaded_files) or st.session_state.processing,
)

# =============== HÀM PHỤ TRỢ ===============
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
    Hạ gain để peak còn ~ -headroom_db dBFS, tránh clip.
    """
    try:
        if seg.max_dBFS > -headroom_db:
            change_db = -(seg.max_dBFS + headroom_db)
            return seg.apply_gain(change_db)
    except Exception:
        pass
    return seg

# =============== XỬ LÝ ===============
if process_clicked:
    st.session_state.processing = True  # khóa nút ngay khi click

if st.session_state.processing:
    if not uploaded_files:
        st.warning("Hãy chọn ít nhất 1 file MP3.")
        st.session_state.processing = False
    else:
        zip_buffer = io.BytesIO()
        errors = []
        progress = st.progress(0, text="Đang xử lý...")
        log_area = st.empty()

        try:
            with st.spinner("Đang xử lý & nén ZIP..."):
                total = len(uploaded_files)
                with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for idx, f in enumerate(uploaded_files, start=1):
                        try:
                            src = AudioSegment.from_file(f, format="mp3")
                            if normalize:
                                src = normalize_peak(src, headroom_db=1.0)
                            processed = safe_fade(src, fade_in_ms=fade_in_ms, fade_out_ms=fade_out_ms)

                            out_mp3 = io.BytesIO()
                            processed.export(out_mp3, format="mp3", bitrate=target_bitrate)
                            out_mp3.seek(0)

                            name = f.name if f.name.lower().endswith(".mp3") else f.name + ".mp3"
                            out_name = prefix_out + name
                            zf.writestr(out_name, out_mp3.read())

                            log_area.write(f"✔ Xong: {f.name}")
                        except Exception as e:
                            err = f"❌ {f.name}: {e}"
                            errors.append(err)
                            log_area.write(err)

                        progress.progress(idx / total, text=f"Đang xử lý... ({idx}/{total})")

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

        finally:
            # luôn mở khóa dù có lỗi
            st.session_state.processing = False
            progress.empty()
