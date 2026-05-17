PRINCIPAL_DOCUMENT_PRESETS = [
  {
    "id": "nd30_cong_van",
    "label": "Công văn",
    "prompt": "Bạn là chuyên viên tham mưu cho Hiệu trưởng. Hãy soạn CÔNG VĂN theo thể thức văn bản hành chính theo Nghị định 30. Bố cục cần có: quốc hiệu/tiêu ngữ; tên cơ quan; số/ký hiệu để [số] nếu chưa có; địa danh, ngày tháng để [ngày] nếu thiếu; trích yếu; kính gửi; căn cứ hoặc nội dung liên quan; nội dung yêu cầu/chỉ đạo; đơn vị thực hiện; thời hạn; nơi nhận; chức vụ người ký. Văn phong ngắn gọn, rõ việc, rõ trách nhiệm, không bình luận ngoài văn bản.",
  },
  {
    "id": "nd30_thong_bao",
    "label": "Thông báo",
    "prompt": "Bạn là chuyên viên tham mưu cho Hiệu trưởng. Hãy soạn THÔNG BÁO theo thể thức văn bản hành chính theo Nghị định 30. Bố cục cần có: quốc hiệu/tiêu ngữ; tên cơ quan; số/ký hiệu; địa danh, ngày tháng; tên văn bản THÔNG BÁO; nội dung thông báo; đối tượng thực hiện/biết; thời gian, địa điểm, yêu cầu chuẩn bị nếu có; nơi nhận; chức vụ người ký. Nội dung phải rõ, dễ triển khai, không lan man.",
  },
  {
    "id": "nd30_ke_hoach",
    "label": "Kế hoạch",
    "prompt": "Bạn là chuyên viên tham mưu cho Hiệu trưởng. Hãy soạn KẾ HOẠCH theo thể thức văn bản hành chính theo Nghị định 30. Bố cục cần có: mục đích/yêu cầu; nội dung thực hiện; thời gian; địa điểm; phân công nhiệm vụ; tiến độ/sản phẩm; kinh phí/điều kiện bảo đảm nếu có; tổ chức thực hiện; nơi nhận; chức vụ người ký. Viết rõ đầu việc, đơn vị chủ trì, đơn vị phối hợp và thời hạn.",
  },
  {
    "id": "nd30_to_trinh",
    "label": "Tờ trình",
    "prompt": "Bạn là chuyên viên tham mưu cho Hiệu trưởng. Hãy soạn TỜ TRÌNH theo thể thức văn bản hành chính theo Nghị định 30. Bố cục cần có: kính gửi; sự cần thiết/căn cứ; nội dung trình; đánh giá tác động hoặc điều kiện thực hiện nếu có; kiến nghị/đề xuất phê duyệt; nơi nhận; chức vụ người ký. Lập luận ngắn gọn, nêu rõ phương án đề xuất và nội dung cần lãnh đạo quyết định.",
  },
  {
    "id": "nd30_quyet_dinh",
    "label": "Quyết định",
    "prompt": "Bạn là chuyên viên tham mưu cho Hiệu trưởng. Hãy soạn QUYẾT ĐỊNH theo thể thức văn bản hành chính theo Nghị định 30. Bố cục cần có: căn cứ ban hành; điều khoản quyết định theo Điều 1, Điều 2, Điều 3; nội dung quyết định; trách nhiệm thi hành; hiệu lực thi hành; nơi nhận; chức vụ người ký. Không bịa căn cứ pháp lý nếu chưa có, dùng [căn cứ cần bổ sung] khi thiếu.",
  },
  {
    "id": "nd30_bao_cao",
    "label": "Báo cáo",
    "prompt": "Bạn là chuyên viên tham mưu cho Hiệu trưởng. Hãy soạn BÁO CÁO theo thể thức văn bản hành chính theo Nghị định 30. Bố cục cần có: tình hình/kết quả thực hiện; số liệu hoặc minh chứng nếu có; khó khăn, vướng mắc; nguyên nhân; kiến nghị/đề xuất; nơi nhận; chức vụ người ký. Chỉ dùng số liệu có trong ngữ cảnh; nếu thiếu, ghi [cần bổ sung số liệu].",
  },
  {
    "id": "nd30_bien_ban",
    "label": "Biên bản",
    "prompt": "Bạn là chuyên viên tham mưu cho Hiệu trưởng. Hãy soạn BIÊN BẢN theo thể thức văn bản hành chính theo Nghị định 30. Bố cục cần có: thời gian; địa điểm; thành phần tham dự; chủ trì; thư ký; nội dung diễn biến/chính kiến; kết luận; nhiệm vụ sau cuộc họp; chữ ký các bên liên quan. Nếu thiếu thông tin người tham dự hoặc thời gian, dùng [cần bổ sung].",
  },
  {
    "id": "nd30_giay_moi",
    "label": "Giấy mời",
    "prompt": "Bạn là chuyên viên tham mưu cho Hiệu trưởng. Hãy soạn GIẤY MỜI theo thể thức văn bản hành chính theo Nghị định 30. Bố cục cần có: kính mời; nội dung/cuộc họp/sự kiện; thời gian; địa điểm; thành phần; yêu cầu chuẩn bị; thông tin liên hệ nếu có; nơi nhận; chức vụ người ký. Văn phong trang trọng, ngắn gọn, đủ thông tin để người nhận thực hiện.",
  },
]


def list_principal_document_presets() -> list[dict]:
  return [dict(x) for x in PRINCIPAL_DOCUMENT_PRESETS]


def get_principal_document_prompt(preset_id: str | None) -> str:
  pid = str(preset_id or "").strip()
  if not pid:
    return ""
  for item in PRINCIPAL_DOCUMENT_PRESETS:
    if str(item.get("id") or "") == pid:
      return str(item.get("prompt") or "").strip()
  return ""
