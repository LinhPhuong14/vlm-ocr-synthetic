"""
Donut / SynthDoG-VN
MIT License

Chỉ còn ba element mà template hoá đơn dùng. Các element của SynthDoG gốc
(`Content`, `Document`, `Paper`, `TextBox`) và `layouts/` đã bỏ cùng với
`template.py` — chúng chỉ phục vụ template sinh trang wiki đa ngôn ngữ, không
liên quan tới hoá đơn. Cần lại thì lấy từ lịch sử git hoặc từ clovaai/donut.
"""
from elements.background import Background
from elements.receipt import Receipt
from elements.warp import CurlWarp

__all__ = ["Background", "CurlWarp", "Receipt"]
