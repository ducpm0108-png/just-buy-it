"""Just Buy It? — công cụ đánh giá một khoản mua trước khi xuống tiền.

Toàn bộ logic tính toán nằm trong package này và chỉ dùng thư viện chuẩn
của Python, không phụ thuộc Streamlit. Nhờ vậy:

- kiểm thử được bằng pytest mà không cần chạy giao diện
- script gửi email nhắc dùng lại được y nguyên
- muốn đổi giao diện sang thứ khác thì phần tính toán không phải sửa

Giao diện nằm ở app.py ngoài package.
"""

__version__ = "0.1.0"
