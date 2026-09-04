"""Kiểm tra font có vẽ được đủ chữ tiếng Việt không.

    generators/html/.venv/bin/python tools/check_fonts.py fonts/mono

Thêm một font mà không kiểm tra là rủi ro lớn nhất của kho này: font thiếu
glyph vẫn chạy bình thường, chỉ là ảnh hiện ô vuông ▯ trong khi nhãn vẫn ghi
đúng chữ — dữ liệu bẩn mà không có lỗi nào báo ra. Trình duyệt còn tệ hơn
renderer lưới ký tự ở chỗ này: nó **thay font khác** cho ký tự thiếu, nên trang
trông vẫn đọc được mà nét chữ đổi giữa dòng.

Gốc của file là `tools/check_fonts.py` của SynthDoG-VN (MIT), theo backend lưới
ký tự khi backend ấy còn. Nó ở lại vì phép kiểm tra không thuộc về backend nào:
nó hỏi file font, không hỏi renderer. Chỉ cần `fontTools`, thứ môi trường của
renderer HTML đã có sẵn.
"""
import argparse
import os
import sys

from fontTools.ttLib import TTFont

# nguyên âm có dấu + đ/Đ, phần mà font Latin phổ thông hay thiếu
VI_CHARS = (
    "ĂÂĐÊÔƠƯăâđêôơư"
    "ẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼẾỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴỶỸ"
    "ạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ"
    "áàãéèíìóòúùýÁÀÃÉÈÍÌÓÒÚÙÝ"
)


def coverage(path):
    cmap = TTFont(path, fontNumber=0).getBestCmap()
    return [c for c in VI_CHARS if ord(c) not in cmap]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="file font hoặc thư mục chứa font")
    args = ap.parse_args()

    fonts = []
    for path in args.paths:
        if os.path.isdir(path):
            fonts += [
                os.path.join(path, n)
                for n in sorted(os.listdir(path))
                if n.lower().endswith((".ttf", ".otf"))
            ]
        else:
            fonts.append(path)

    if not fonts:
        print("Không tìm thấy font nào.")
        return 1

    failed = 0
    for path in fonts:
        try:
            missing = coverage(path)
        except Exception as exc:  # font hỏng cũng phải báo, không được nuốt
            print(f"[LỖI ] {os.path.basename(path)}: {exc}")
            failed += 1
            continue
        if missing:
            failed += 1
            print(f"[THIẾU] {os.path.basename(path)}: {len(missing)} ký tự -> {''.join(missing[:24])}")
        else:
            print(f"[OK   ] {os.path.basename(path)}")

    print(f"\n{len(fonts) - failed}/{len(fonts)} font dùng được cho tiếng Việt.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
