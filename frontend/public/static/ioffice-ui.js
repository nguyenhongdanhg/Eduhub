$(function () {
  const API = "/api/ioffice/ui";
  const FILE_API = "/api/ioffice";
  const $log = $("#logArea");
  const $tbl = $("#tblDocs");
  let table = null;
  let es = null;
  let currentTab = "ALL";
  let currentRole = "";
  let keyword = "";
  let currentPage = null;
  let sessionOk = null;
  let isFetching = false;
  let currentMode = "update";
  let workCategories = [];
  let workFlat = [];

  const $statusBar = $("<div id='runStatus' style='display:inline-block; float:left; margin-right:12px;'>📡 Đang chạy</div>");
  $(".header-actions").prepend($statusBar);

  function toast(type, message) {
    const t = String(type || "info").toLowerCase();
    const cls = t === "success" ? "success" : t === "danger" || t === "error" ? "danger" : t === "warning" ? "warning" : "info";
    const text = String(message || "").trim();
    if (!text) return;
    const $box = $(
      `<div class="alert alert-${cls}" role="alert" style="position:fixed; top:12px; right:12px; z-index:20000; min-width:260px; max-width:420px; box-shadow:0 2px 8px rgba(0,0,0,.18);"></div>`
    );
    $box.text(text);
    $("body").append($box);
    setTimeout(function () {
      try {
        $box.fadeOut(250, function () {
          $box.remove();
        });
      } catch (_) {}
    }, 2800);
  }

  function htmlEscape(s) {
    return String(s || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function toInt(v) {
    const n = Number(v);
    return Number.isFinite(n) ? Math.trunc(n) : 0;
  }

  function buildWorkFlat(categories) {
    const byParent = new Map();
    for (const c of categories || []) {
      const id = toInt(c && c.id);
      if (!id) continue;
      const pid = c && c.parent_id != null ? toInt(c.parent_id) : 0;
      if (!byParent.has(pid)) byParent.set(pid, []);
      byParent.get(pid).push(c);
    }
    for (const [pid, arr] of byParent.entries()) {
      arr.sort(function (a, b) {
        const sa = toInt(a && a.sort_order);
        const sb = toInt(b && b.sort_order);
        if (sa !== sb) return sa - sb;
        return toInt(a && a.id) - toInt(b && b.id);
      });
    }
    const out = [];
    const walk = function (pid, level) {
      const kids = byParent.get(pid) || [];
      kids.forEach(function (c) {
        out.push({ c: c, level: level });
        walk(toInt(c && c.id), level + 1);
      });
    };
    walk(0, 0);
    return out;
  }

  function loadWorkCategories() {
    return $.getJSON(FILE_API + "/categories")
      .done(function (rows) {
        workCategories = Array.isArray(rows) ? rows : [];
        workFlat = buildWorkFlat(workCategories);
      })
      .fail(function () {
        workCategories = [];
        workFlat = [];
      });
  }

  function ensureWorkPicker() {
    if ($("#workPicker").length) return;
    const $picker = $(
      "<div id='workPicker' class='dropdown-menu' style='display:none; position:absolute; z-index:30000; padding:8px; min-width:320px; max-width:420px;'></div>"
    );
    const $search = $("<input id='workPickerSearch' class='form-control input-sm' placeholder='Tìm công việc...' />");
    const $list = $("<div id='workPickerList' style='margin-top:8px; max-height:320px; overflow:auto;'></div>");
    $picker.append($search).append($list);
    $("body").append($picker);
  }

  function getRowByDocRowId(docRowId) {
    if (!table) return null;
    const data = table.rows().data();
    for (let i = 0; i < data.length; i++) {
      const r = data[i];
      if (String(r && r.row_id) === String(docRowId)) return r;
    }
    return null;
  }

  function renderWorkCell(d) {
    const docRowId = String((d && d.row_id) || "").trim();
    const items = Array.isArray(d && d.cong_viec) ? d.cong_viec : [];
    const tags = items
      .map(function (x) {
        const id = String((x && x.id) || "").trim();
        const name = String((x && x.name) || "").trim();
        if (!id || !name) return "";
        return (
          "<span class='label label-info work-tag' style='display:inline-block; margin:0 4px 4px 0; vertical-align:top;' data-doc-row-id='" +
          htmlEscape(docRowId) +
          "' data-cat-id='" +
          htmlEscape(id) +
          "'>" +
          htmlEscape(name) +
          " <a href='#' class='work-remove' data-doc-row-id='" +
          htmlEscape(docRowId) +
          "' data-cat-id='" +
          htmlEscape(id) +
          "' style='color:#fff; text-decoration:none; margin-left:4px'>&times;</a></span>"
        );
      })
      .join("");
    const addBtn =
      "<a href='#' class='work-open' data-doc-row-id='" +
      htmlEscape(docRowId) +
      "' title='Gán công việc' style='display:inline-block; padding:2px 4px; color:#0d6efd;'><i class='fa fa-plus'></i></a>";
    const tagsHtml = tags ? tags : "<span style='color:#777'>—</span>";
    return (
      "<div class='work-cell' data-doc-row-id='" +
      htmlEscape(docRowId) +
      "'>" +
      "<div class='work-actions' style='text-align:right; margin-bottom:4px;'>" +
      addBtn +
      "</div>" +
      "<div class='work-tags'>" +
      tagsHtml +
      "</div>" +
      "</div>"
    );
  }

  function renderWorkPickerList(docRowId) {
    const row = getRowByDocRowId(docRowId) || {};
    const selected = new Set((Array.isArray(row.cong_viec) ? row.cong_viec : []).map(function (x) { return String(x && x.id); }));
    const kw = String($("#workPickerSearch").val() || "")
      .trim()
      .toLowerCase();
    let html = "";
    const list = Array.isArray(workFlat) ? workFlat : [];
    list.forEach(function (it) {
      const c = it.c || {};
      const id = String(c.id || "").trim();
      const name = String(c.name || "").trim();
      if (!id || !name) return;
      const desc = String(c.description || "").trim();
      const hay = (name + " " + desc).toLowerCase();
      if (kw && hay.indexOf(kw) === -1) return;
      const checked = selected.has(id) ? "checked" : "";
      const pad = it.level > 0 ? "padding-left:" + it.level * 14 + "px;" : "";
      html +=
        "<label style='display:block; margin:2px 0; " +
        pad +
        "'>" +
        "<input type='checkbox' class='work-check' data-doc-row-id='" +
        htmlEscape(docRowId) +
        "' data-cat-id='" +
        htmlEscape(id) +
        "' " +
        checked +
        " /> " +
        htmlEscape(name) +
        "</label>";
    });
    if (!html) html = "<div style='color:#777'>Không có công việc phù hợp.</div>";
    $("#workPickerList").html(html);
  }

  function showWorkPicker(anchorEl, docRowId) {
    ensureWorkPicker();
    const $picker = $("#workPicker");
    if (!workFlat.length) loadWorkCategories();
    $("#workPickerSearch").val("");
    renderWorkPickerList(docRowId);
    const $a = $(anchorEl);
    const off = $a.offset() || { top: 0, left: 0 };
    $picker.data("docRowId", docRowId);
    $picker.css({ top: off.top + $a.outerHeight() + 4, left: off.left }).show();
    setTimeout(function () {
      try {
        $("#workPickerSearch").focus();
      } catch (_) {}
    }, 0);
  }

  function hideWorkPicker() {
    $("#workPicker").hide();
  }

  function renderMarkdownLite(raw) {
    const text = String(raw || "");
    const lines = text.replaceAll("\r\n", "\n").replaceAll("\r", "\n").split("\n");
    const nonEmpty = lines.filter((l) => String(l || "").trim() !== "");
    const isList = nonEmpty.length > 0 && nonEmpty.every((l) => /^\s*[-*]\s+/.test(l));

    function renderInline(s) {
      let out = htmlEscape(s);
      out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      return out;
    }

    if (isList) {
      const items = nonEmpty.map((l) => {
        const content = l.replace(/^\s*[-*]\s+/, "");
        return `<li>${renderInline(content)}</li>`;
      });
      return `<ul style="margin:0; padding-left:18px;">${items.join("")}</ul>`;
    }

    const html = lines.map((l) => renderInline(l)).join("<br>");
    return `<div>${html}</div>`;
  }

  function setAiStatus(raw) {
    $("#aiStatus").html(renderMarkdownLite(raw));
  }

  function setTaskContent(raw) {
    $("#taskContent").html(renderMarkdownLite(raw));
  }

  function loadSummaryPrompts() {
    const $sel = $("#promptSelect");
    if (!$sel.length) return;
    $sel.prop("disabled", true);
    $.getJSON(API + "/summary_prompts")
      .done(function (r) {
        const presets = (r && r.presets) || [];
        let html = "";
        if (Array.isArray(presets) && presets.length) {
          presets.forEach(function (p, idx) {
            const id = String((p && p.id) || "").trim();
            const label = String((p && p.label) || id).trim();
            if (!id) return;
            const selected = idx === 0 ? "selected" : "";
            html += `<option value="${htmlEscape(id)}" ${selected}>${htmlEscape(label)}</option>`;
          });
          $sel.html(html);
          $sel.prop("disabled", false);
          return;
        } else {
          toast("warning", "Chưa có prompt tóm tắt. Hãy tạo trong 'Quản lý prompt'.");
          html = `<option value="" selected>Chưa có prompt</option>`;
          $sel.html(html);
          $sel.prop("disabled", true);
          return;
        }
      })
      .fail(function (xhr) {
        toast("danger", readAjaxError(xhr, "Không tải được danh sách prompt."));
        $sel.html(`<option value="" selected>Không tải được prompt</option>`);
        $sel.prop("disabled", true);
      });
  }

  $(document).on("click", function (e) {
    const $picker = $("#workPicker");
    if (!$picker.length || !$picker.is(":visible")) return;
    const $t = $(e.target);
    if ($t.closest("#workPicker").length) return;
    if ($t.closest(".work-open").length) return;
    hideWorkPicker();
  });

  $(document).on("input", "#workPickerSearch", function () {
    const $picker = $("#workPicker");
    const docRowId = String($picker.data("docRowId") || "").trim();
    if (!docRowId) return;
    renderWorkPickerList(docRowId);
  });

  $(document).on("click", ".work-open", function (e) {
    e.preventDefault();
    const docRowId = String($(this).data("doc-row-id") || $(this).data("docRowId") || $(this).attr("data-doc-row-id") || "").trim();
    if (!docRowId) return;
    showWorkPicker(this, docRowId);
  });

  $(document).on("click", ".work-remove", function (e) {
    e.preventDefault();
    const docRowId = String($(this).attr("data-doc-row-id") || "").trim();
    const catId = String($(this).attr("data-cat-id") || "").trim();
    if (!docRowId || !catId) return;
    $.ajax({ url: FILE_API + "/documents/" + encodeURIComponent(docRowId) + "/categories/" + encodeURIComponent(catId), method: "DELETE" })
      .done(function () {
        const row = getRowByDocRowId(docRowId);
        if (row) {
          row.cong_viec = (Array.isArray(row.cong_viec) ? row.cong_viec : []).filter(function (x) { return String(x && x.id) !== String(catId); });
          const $cell = $(".work-cell[data-doc-row-id='" + docRowId + "']").closest("td");
          $cell.html(renderWorkCell(row));
        }
        toast("success", "Đã bỏ gán công việc.");
      })
      .fail(function (xhr) {
        toast("danger", readAjaxError(xhr, "Không bỏ gán được công việc."));
      });
  });

  $(document).on("change", ".work-check", function () {
    const docRowId = String($(this).attr("data-doc-row-id") || "").trim();
    const catId = String($(this).attr("data-cat-id") || "").trim();
    if (!docRowId || !catId) return;
    const checked = $(this).is(":checked");
    const method = checked ? "POST" : "DELETE";
    $.ajax({ url: FILE_API + "/documents/" + encodeURIComponent(docRowId) + "/categories/" + encodeURIComponent(catId), method: method })
      .done(function () {
        const row = getRowByDocRowId(docRowId);
        const cat = (workCategories || []).find(function (c) { return String(c && c.id) === String(catId); }) || {};
        if (row) {
          const cur = Array.isArray(row.cong_viec) ? row.cong_viec : [];
          if (checked) {
            if (!cur.some(function (x) { return String(x && x.id) === String(catId); })) cur.push({ id: toInt(catId), name: cat.name || "", parent_id: cat.parent_id || null });
          } else {
            row.cong_viec = cur.filter(function (x) { return String(x && x.id) !== String(catId); });
          }
          const $cell = $(".work-cell[data-doc-row-id='" + docRowId + "']").closest("td");
          $cell.html(renderWorkCell(row));
        }
        renderWorkPickerList(docRowId);
      })
      .fail(function (xhr) {
        toast("danger", readAjaxError(xhr, checked ? "Không gán được công việc." : "Không bỏ gán được công việc."));
        renderWorkPickerList(docRowId);
      });
  });

  function renderPromptPresetList(items) {
    const list = Array.isArray(items) ? items : [];
    let html = "";
    html += "<table class='table table-bordered table-condensed' style='margin:0'>";
    html += "<thead><tr><th style='width:120px'>ID</th><th style='width:180px'>Tên</th><th style='width:80px'>Bật</th><th style='width:90px'>Thứ tự</th><th>Prompt</th><th style='width:140px'>Thao tác</th></tr></thead>";
    html += "<tbody>";
    list.forEach(function (p) {
      const id = String((p && p.id) || "").trim();
      const label = String((p && p.label) || "").trim();
      const prompt = String((p && p.prompt) || "");
      const enabled = !!(p && p.enabled);
      const sort_order = parseInt((p && p.sort_order) || 0, 10) || 0;
      if (!id) return;
      html += "<tr>";
      html += `<td><input class="form-control pp-id" value="${htmlEscape(id)}" disabled></td>`;
      html += `<td><input class="form-control pp-label" value="${htmlEscape(label)}"></td>`;
      html += `<td style="text-align:center"><input class="pp-enabled" type="checkbox" ${enabled ? "checked" : ""}></td>`;
      html += `<td><input class="form-control pp-sort" type="number" value="${sort_order}"></td>`;
      html += `<td><textarea class="form-control pp-prompt" rows="5" style="min-width:280px">${htmlEscape(prompt)}</textarea></td>`;
      html += `<td style="white-space:nowrap">
        <button class="btn btn-primary btn-sm btnSavePrompt" data-id="${htmlEscape(id)}">Lưu</button>
        <button class="btn btn-danger btn-sm btnDelPrompt" data-id="${htmlEscape(id)}">Xóa</button>
      </td>`;
      html += "</tr>";
    });
    html += "</tbody></table>";
    $("#promptPresetList").html(html);
  }

  function loadPromptPresetsForManage() {
    $("#promptPresetList").html("<div style='color:#777'>Đang tải...</div>");
    $.getJSON(API + "/prompt_presets")
      .done(function (r) {
        const items = (r && r.presets) || [];
        renderPromptPresetList(items);
      })
      .fail(function (xhr) {
        $("#promptPresetList").html("<div style='color:#c00'>" + htmlEscape(readAjaxError(xhr, "Không tải được danh sách prompt.")) + "</div>");
      });
  }

  function renderMarkdownInlineLite(raw) {
    const text = String(raw || "");
    let out = htmlEscape(text);
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    return out;
  }

  function truncateWords(text, maxWords) {
    const t = String(text || "").trim();
    if (!t) return "";
    const parts = t.split(/\s+/);
    if (parts.length <= maxWords) return t;
    return parts.slice(0, maxWords).join(" ") + " ...";
  }

  function truncateSmart(text, maxChars, maxWords) {
    const raw = String(text || "").trim();
    if (!raw) return "";
    let out = raw;
    if (Number.isFinite(maxWords) && maxWords > 0) {
      out = truncateWords(out, maxWords);
    }
    if (Number.isFinite(maxChars) && maxChars > 0 && out.length > maxChars) {
      out = out.slice(0, maxChars).trimEnd() + " ...";
    }
    return out;
  }

  function formatLog(raw) {
    return String(raw || "");
  }

  function trimLog(maxLines) {
    const lines = $log.text().split("\n");
    if (lines.length <= maxLines) return;
    $log.text(lines.slice(lines.length - maxLines).join("\n"));
  }

  function startSSE() {
    if (es) return;
    es = new EventSource(API + "/stream-logs");
    es.onmessage = (e) => {
      if (e.data === "ping") return;
      const raw = e.data || "";
      const line = formatLog(raw);
      $log.append(line + "\n");
      trimLog(200);
      $log.scrollTop($log[0].scrollHeight);
      try {
        const mPageRaw = raw.match(/\[UI_PAGE\]\s+(\d+)/);
        if (mPageRaw) currentPage = parseInt(mPageRaw[1] || "1", 10);
        const mDone = line.match(/=== FETCH COMPLETE ===.*ok=(\d+)/);
        if (mDone) sessionOk = parseInt(mDone[1] || "0", 10);
        const done =
          line.indexOf("=== FETCH COMPLETE ===") !== -1 ||
          line.indexOf("STOP requested") !== -1 ||
          line.indexOf("No more pages") !== -1 ||
          line.indexOf("Reached max_pages") !== -1;
        if (currentPage) $("#runStatus").addClass("runStatusRunning").show().text(`📡 Đang chạy trang ${currentPage}`);
        if (done) {
          $("#runStatus")
            .removeClass("runStatusRunning")
            .show()
            .text(`Hoàn thành — Tổng xử lý: ${sessionOk == null ? "" : sessionOk}`);
          setTimeout(function () {
            $("#runStatus").hide();
          }, 60000);
          loadAll();
        }
      } catch (_) {}
    };
    es.onerror = () => {
      try {
        es.close();
      } catch (_) {}
      es = null;
      setTimeout(startSSE, 1500);
    };
  }

  function encodePath(p) {
    return encodeURIComponent(p || "");
  }

  function roleShortLabel(raw) {
    const s = String(raw || "").trim().toUpperCase();
    if (!s) return { text: "Khác", cls: "label-default" };
    if (s.indexOf("XLC") === 0) return { text: "XLC", cls: "label-danger" };
    if (s.indexOf("PH") === 0) return { text: "PH", cls: "label-primary" };
    return { text: "Khác", cls: "label-default" };
  }

  function initTable() {
    table = $tbl.DataTable({
      dom: "lrtip",
      autoWidth: false,
      language: {
        processing: "Đang xử lý...",
        loadingRecords: "Đang tải...",
        lengthMenu: "Hiển thị _MENU_",
        zeroRecords: "Không tìm thấy dữ liệu phù hợp",
        emptyTable: "Bảng trống",
        info: "Hiển thị _START_–_END_ trên tổng _TOTAL_ mục",
        infoEmpty: "Không có mục để hiển thị",
        infoFiltered: " (lọc từ tổng _MAX_ mục)",
        search: "Tìm kiếm:",
        paginate: { first: "Đầu", previous: "Trước", next: "Sau", last: "Cuối" },
        aria: { sortAscending: ": sắp xếp tăng dần", sortDescending: ": sắp xếp giảm dần" },
      },
      columns: [
        { data: null, width: "4%", orderable: false, className: "dt-left" },
        {
          data: null,
          width: "12%",
          render: function (d) {
            const ht = d.hinh_thuc || "";
            const skh = d.so_ky_hieu || d.ten_file || d.doc_id || "";
            const dv = String(d.don_vi_ban_hanh || "").trim();
            let href = "#";
            if (d.duong_dan_file) href = `${FILE_API}/view-zip?path=${encodePath(d.duong_dan_file)}`;
            else if (d.link_goc) href = d.link_goc;
            const main = (String(ht).trim() || String(skh).trim())
              ? `<div style="font-size:14px;">${htmlEscape(ht)}</div><div style="font-size:14px;"><a href="${href}" target="_blank" class="skh-link">${htmlEscape(skh)}</a></div>`
              : `<div style="font-size:14px; color:#777">—</div>`;
            const dvHtml = dv ? `<div><small style="color:#666">${htmlEscape(truncateWords(dv, 10))}</small></div>` : "";
            return `<div>${main}${dvHtml}</div>`;
          },
        },
        {
          data: null,
          width: "30%",
          render: function (d) {
            const ty = d.trich_yeu || d.tom_tat || d.ten_file || d.so_ky_hieu || "";
            let targetHref = "#";
            if (d.duong_dan_file) targetHref = `${FILE_API}/view-zip?path=${encodePath(d.duong_dan_file)}`;
            else if (d.link_goc) targetHref = d.link_goc;
            if (!String(ty).trim()) return `<div class='trich' style="color:#777">—</div>`;
            const short = truncateSmart(ty, 100, 20);
            return `<div class='trich'><a class="trich-link" target="_blank" href="${targetHref}">${htmlEscape(short)}</a></div>`;
          },
        },
        {
          data: null,
          width: "30%",
          className: "dt-left",
          render: function (d) {
            const raw = String(d.ai_summary || d.tom_tat || "").trim();
            const hasZip = !!(d.duong_dan_file && String(d.duong_dan_file).toLowerCase().endsWith(".zip"));
            if (!raw) {
              if (hasZip) return `<div class='trich'><a href="#" class="btnSumm" data-id='${htmlEscape(d.doc_id)}'>Tóm tắt</a></div>`;
              return `<div class='trich' style="color:#777">Chưa có</div>`;
            }
            const short = truncateSmart(raw, 100, 20);
            const more = `<a href="#" class="btnSummaryMore" data-id='${htmlEscape(d.doc_id)}' data-text="${htmlEscape(raw)}">Xem thêm</a>`;
            const retry = hasZip ? `<a href="#" class="btnSumm" data-id='${htmlEscape(d.doc_id)}'>Tóm tắt lại</a>` : "";
            const audio = `<a href="#" class="btnSummaryAudio" data-id='${htmlEscape(d.doc_id)}' data-text="${htmlEscape(raw)}" title="Nghe tóm tắt"><i class="fa fa-headphones"></i></a>`;
            const actions = retry ? `${more} | ${retry} | ${audio}` : `${more} | ${audio}`;
            const audioArea = `<div class="summary-audio" style="margin-top:4px; text-align:center;"></div>`;
            return `<div class='trich'><div class='summary-text'><small>${renderMarkdownInlineLite(short)}</small></div><div class='summary-actions' style='margin-top:6px; text-align:center;'>${actions}</div>${audioArea}</div>`;
          },
        },
        {
          data: null,
          width: "10%",
          className: "dt-left",
          render: function (d) {
            const role = roleShortLabel(d.vai_tro);
            const vb = d.ngay_van_ban || "";
            const den = d.ngay_den || "";
            const a = vb ? `<div><small>VB: ${htmlEscape(vb)}</small></div>` : "";
            const b = den ? `<div><small>Đến: ${htmlEscape(den)}</small></div>` : "";
            const han = (d.han_xu_ly || "").trim();
            const roleHtml = `<div><span class="label ${role.cls}">${role.text}</span></div>`;
            return `<div title="">${roleHtml}${b}${a}<div><small>T.Hạn: ${htmlEscape(han || "Không")}</small></div></div>`;
          },
        },
        {
          data: null,
          width: "120px",
          className: "dt-left nowrap",
          render: function (d) {
            return renderWorkCell(d);
          },
        },
        {
          data: null,
          width: "4%",
          orderable: false,
          className: "dt-center nowrap",
          render: function (d) {
            const link = d.link_goc || "#";
            const dl = d.duong_dan_file ? `${FILE_API}/download-file/${encodePath(d.duong_dan_file)}` : "#";
            const viewBtn = `<a class='btn btn-xs btn-warning' target='_blank' href='${link}' data-toggle='tooltip' title='Xem văn bản gốc'><i class='fa fa-external-link'></i></a>`;
            const dlBtn = d.duong_dan_file ? `<a class='btn btn-xs btn-default' target='_blank' href='${dl}' data-toggle='tooltip' title='Tải tệp đính kèm'><i class='fa fa-download'></i></a>` : "";
            const delBtn = `<a class='btn btn-xs btn-link text-danger btnDelDoc' href='#' data-id='${htmlEscape(d.doc_id)}' data-toggle='tooltip' title='Xóa văn bản'><i class='fa fa-trash'></i></a>`;
            return `${viewBtn} ${dlBtn} ${delBtn}`;
          },
        },
      ],
      order: [[4, "desc"]],
      rowCallback: function (row, data, index) {
        $("td:eq(0)", row).html(index + 1);
      },
    });
    $(document).tooltip({ selector: "[data-toggle='tooltip']" });
    setTimeout(function () {
      try {
        const $len = $("#tblDocs_length");
        const $mount = $("#dtLengthMount");
        if ($len.length && $mount.length) {
          $len.detach().appendTo($mount);
        }
      } catch (_) {}
    }, 0);
  }

  function loadStats() {
    const params = { vb_tab: currentTab || "ALL" };
    if (currentRole) params.role = currentRole;
    $.getJSON(API + "/stats", params).done(function (r) {
      $("#st_total").text("Tổng: " + (r.total || 0));
      $("#st_xlc").text("XLC: " + (r.xlc || 0));
      $("#st_ph").text("PH: " + (r.ph || 0));
      $("#st_other").text("Khác: " + (r.other || 0));
      $("#st_fail").text("Lỗi: " + (r.fail || 0));
    });
  }

  function loadRecent() {
    const params = { limit: 1000, vb_tab: currentTab || "ALL" };
    if (currentRole) params.role = currentRole;
    if (keyword) params.q = keyword;
    $.getJSON(API + "/recent", params).done(function (rows) {
      table.clear();
      table.rows.add(rows || []);
      table.draw();
    });
  }

  function loadAll() {
    loadStats();
    loadRecent();
  }

  function setBtnIconText($btn, iconClass, text) {
    $btn.html('<i class="' + iconClass + '"></i>');
  }

  function setStartIdleUI() {
    $("#btnFetchIcon").removeClass("btn-danger btn-success").addClass("btn-link").prop("disabled", false);
    setBtnIconText($("#btnFetchIcon"), "fa fa-play-circle", "Chạy");
    $("#btnFetchIcon").attr("title", "Chạy tác vụ");
    $("#runStatus").removeClass("runStatusRunning").hide();
  }

  function setStartRunningUI() {
    $("#btnFetchIcon").removeClass("btn-success btn-danger").addClass("btn-link").prop("disabled", false);
    setBtnIconText($("#btnFetchIcon"), "fa fa-stop-circle", "Dừng");
    $("#btnFetchIcon").attr("title", "Dừng tác vụ");
    $("#runStatus").text("📡 Đang chạy").addClass("runStatusRunning").show();
  }

  function setStartSpinning(text) {
    $("#btnFetchIcon").prop("disabled", true);
    setBtnIconText($("#btnFetchIcon"), "fa fa-spinner fa-spin", text);
    $("#runStatus").text("📡 Đang chạy").addClass("runStatusRunning").show();
  }

  function openAccount() {
    $.getJSON(API + "/config")
      .done(function (r) {
        $("#username").val(r.username || "");
        $("#password").val("");
        $("#acctModal").modal("show");
      })
      .fail(function () {
        alert("Không gọi được backend /api. Hãy mở trang qua http://127.0.0.1:8000/views/management/documents/index.html và đảm bảo backend đang chạy.");
      });
  }

  function saveAccount() {
    const username = $("#username").val() || "";
    const password = $("#password").val() || "";
    $.ajax({
      url: API + "/config",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ username, password }),
    }).done(function () {
      $("#acctModal").modal("hide");
    }).fail(function (xhr) {
      let msg = "Không lưu được cấu hình.";
      try {
        const r = JSON.parse(xhr.responseText || "{}");
        if (r && r.detail) msg = String(r.detail);
      } catch (_) {}
      alert(msg);
    });
  }

  function openStart() {
    $("#startModal").modal("show");
  }

  function doStart(headless) {
    const mode = $("input[name='runMode']:checked").val() || "update";
    currentMode = mode;
    const cat = $("input[name='runCatRad']:checked").val() || "CHO_XU_LY";
    isFetching = true;
    setStartSpinning("Đang chạy...");
    $("#btnLogIcon").trigger("click");
    $.ajax({
      url: API + "/start",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ headless, cats: [cat], mode }),
    })
      .done(function (res) {
        if (res && res.started) {
          $("#startModal").modal("hide");
          setStartRunningUI();
          $log.append("[SYSTEM] Bắt đầu lấy văn bản...\n");
        } else {
          isFetching = false;
          setStartIdleUI();
          $("#startModal").modal("hide");
          if (res && res.reason === "missing_playwright") {
            alert(res.message || "Thiếu playwright. Cài dependencies backend rồi thử lại.");
            return;
          }
          $("#acctModal").modal("show");
        }
      })
      .fail(function () {
        isFetching = false;
        setStartIdleUI();
      });
  }

  function doStop() {
    isFetching = false;
    setStartSpinning("Stopping...");
    $.post(API + "/stop")
      .done(function () {
        $log.append("[SYSTEM] Đã dừng lấy văn bản.\n");
        setStartIdleUI();
      })
      .fail(function () {
        setStartRunningUI();
        isFetching = true;
      });
  }


  $("#btnRefresh").on("click", function () {
    window.location.reload(true);
  });
  $("#homeLink").on("click", function (e) {
    e.preventDefault();
    try {
      $("#btnRefresh").trigger("click");
    } catch (_) {}
  });

  $("#acctIcon").on("click", function () {
    openAccount();
  });
  $("#cfgForm").on("submit", function (e) {
    e.preventDefault();
    saveAccount();
  });
  $("#saveCfg").on("click", function (e) {
    e.preventDefault();
    saveAccount();
  });

  $("#btnFetchIcon").on("click", function () {
    if (isFetching) {
      doStop();
      return;
    }
    $("#optHeadless").prop("checked", true);
    openStart();
  });
  $("#btnBeginStart").on("click", function () {
    const headless = !!$("#optHeadless").prop("checked");
    doStart(headless);
  });

  $("#btnLogIcon").on("click", function () {
    $("#logModal").modal("show");
    startSSE();
  });


  $(".vbTab").on("click", function (e) {
    e.preventDefault();
    const $a = $(this);
    $a.closest("ul").find("li").removeClass("active");
    $a.parent("li").addClass("active");
    currentTab = $a.data("tab") || "ALL";
    loadStats();
    loadRecent();
  });

  $("#filterRole").on("change", function () {
    currentRole = $(this).val() || "";
    loadStats();
    loadRecent();
  });

  let searchTimer = null;
  $("#txtSearch").on("input", function () {
    keyword = $(this).val() || "";
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(loadRecent, 250);
  });

  setInterval(function () {
    if (!$("#logModal").is(":visible")) return;
    $.getJSON(API + "/system_status").done(function (r) {
      if (r && r.ok) {
        const workers = r.workers || [];
        let html = "<table class='table table-condensed table-striped' style='margin-bottom:0; background:#222; color:#fff;'>";
        html += "<thead><tr><th>Worker</th><th>Status</th></tr></thead><tbody>";
        workers.forEach((w) => {
          const st = w.active ? "<span style='color:#0f0'>● Running</span>" : "<span style='color:#777'>○ Idle</span>";
          html += `<tr><td>${htmlEscape(w.name)}</td><td>${st}</td></tr>`;
        });
        html += "</tbody></table>";
        $("#sysStatusArea").html(html);
      }
    });
  }, 2000);

  loadWorkCategories();
  initTable();
  loadAll();
  setStartIdleUI();

  $(document).on("click", ".btnRoleMore", function (e) {
    e.preventDefault();
    const t = $(this).data("task") || "";
    setTaskContent(String(t || ""));
    $("#taskModal").modal("show");
  });

  $(document).on("click", ".btnSummaryMore", function (e) {
    e.preventDefault();
    const txt = $(this).data("text") || "";
    setTaskContent(String(txt || ""));
    $("#taskModal").modal("show");
  });

  function stopAllAudiosExcept(exceptId) {
    try {
      document.querySelectorAll("audio").forEach((a) => {
        if (!exceptId || a.id !== exceptId) {
          try {
            a.pause();
          } catch (_) {}
        }
      });
    } catch (_) {}
  }

  function browserTtsAvailable() {
    try {
      return !!(window.speechSynthesis && window.SpeechSynthesisUtterance);
    } catch (_) {
      return false;
    }
  }

  function browserTtsStop() {
    try {
      if (window.speechSynthesis) window.speechSynthesis.cancel();
    } catch (_) {}
  }

  function browserTtsSpeak(text, opts) {
    const t = String(text || "").trim();
    if (!t) return false;
    if (!browserTtsAvailable()) return false;
    const rate = opts && opts.rate != null ? Number(opts.rate) : 1.2;
    const u = new SpeechSynthesisUtterance(t);
    u.lang = "vi-VN";
    try {
      u.rate = Math.max(0.5, Math.min(2.0, rate || 1.2));
    } catch (_) {}
    try {
      const voices = (window.speechSynthesis.getVoices && window.speechSynthesis.getVoices()) || [];
      const vi = voices.find((v) => String(v.lang || "").toLowerCase().startsWith("vi"));
      if (vi) u.voice = vi;
    } catch (_) {}
    try {
      browserTtsStop();
      window.speechSynthesis.speak(u);
      return true;
    } catch (_) {}
    return false;
  }

  function isLikelyTtsUnavailable(err) {
    const t = String(err || "").trim();
    if (!t) return false;
    const low = t.toLowerCase();
    return (
      low.includes("tts_unavailable") ||
      low.includes("t t s không khả dụng") ||
      low.includes("tts không khả dụng") ||
      low.includes("missing_edge_tts") ||
      low.includes("missing_gtts") ||
      low.includes("missing_pyttsx3") ||
      low.includes("gtts_error:") ||
      low.includes("google_tts_error:") ||
      low.includes("tts_provider_not_configured") ||
      low.includes("missing_openai_api_key")
    );
  }

  $(document).on("click", ".btnSummaryBrowserTts", function (e) {
    e.preventDefault();
    const id = String($(this).data("id") || "").trim();
    if (!id) return;
    if (!browserTtsAvailable()) {
      toast("warning", "Trình duyệt không hỗ trợ đọc văn bản (SpeechSynthesis).");
      return;
    }
    const $btn = $(this);
    const prev = $btn.html();
    $btn.html('<i class="fa fa-spinner fa-spin"></i>').addClass("disabled");
    $.getJSON(API + "/doc_summary", { doc_id: id })
      .done(function (r) {
        const text = String((r && (r.summary_text || r.ai_summary)) || "").trim();
        if (!text) {
          toast("warning", "Chưa có nội dung tóm tắt để đọc.");
          return;
        }
        const ok = browserTtsSpeak(text, { rate: 1.2 });
        if (!ok) toast("danger", "Không đọc được bằng trình duyệt.");
      })
      .fail(function (xhr) {
        toast("danger", readAjaxError(xhr, "Không lấy được nội dung tóm tắt."));
      })
      .always(function () {
        $btn.html(prev).removeClass("disabled");
      });
  });

  function friendlyError(s) {
    const t = String(s || "").trim();
    if (!t) return t;
    const low = t.toLowerCase();
    if (low === "tts_unavailable" || low === "tts_provider_not_configured") {
      return "TTS không khả dụng. Hãy cấu hình EDUAI_TTS_PROVIDER=openai và thêm AI_OPENAI_API_KEY trong Cấu hình hệ thống.";
    }
    if (low === "missing_openai_api_key") {
      return "Thiếu OpenAI API key cho TTS. Hãy thêm AI_OPENAI_API_KEY trong Cấu hình hệ thống.";
    }
    if (low === "missing_google_tts_api_key") {
      return "Thiếu Google TTS API key. Hãy thêm AI_GOOGLE_TTS_API_KEY (hoặc AI_GOOGLE_API_KEY) trong Cấu hình hệ thống.";
    }
    if (low === "missing_summary_text" || low === "missing_summary") {
      return "Chưa có nội dung tóm tắt để đọc.";
    }
    return t;
  }

  function readAjaxError(xhr, fallback) {
    let msg = fallback || "Lỗi.";
    try {
      if (xhr && xhr.responseJSON) {
        const r = xhr.responseJSON;
        if (r && r.detail != null) {
          if (typeof r.detail === "string") return friendlyError(r.detail);
          if (Array.isArray(r.detail)) {
            const msgs = r.detail.map((x) => (x && x.msg ? String(x.msg) : "")).filter(Boolean);
            if (msgs.length) return friendlyError(msgs.join("; "));
          }
          return friendlyError(JSON.stringify(r.detail));
        }
        if (r && r.error != null) {
          if (typeof r.error === "string") return friendlyError(r.error);
          return friendlyError(JSON.stringify(r.error));
        }
        return friendlyError(JSON.stringify(r));
      }
    } catch (_) {}
    try {
      const raw = (xhr && xhr.responseText) || "";
      if (!raw) return msg;
      const r2 = JSON.parse(raw);
      if (r2 && r2.detail != null) {
        if (typeof r2.detail === "string") return friendlyError(r2.detail);
        if (Array.isArray(r2.detail)) {
          const msgs = r2.detail.map((x) => (x && x.msg ? String(x.msg) : "")).filter(Boolean);
          if (msgs.length) return friendlyError(msgs.join("; "));
        }
        return friendlyError(JSON.stringify(r2.detail));
      }
      if (r2 && r2.error != null) {
        if (typeof r2.error === "string") return friendlyError(r2.error);
        return friendlyError(JSON.stringify(r2.error));
      }
      return friendlyError(JSON.stringify(r2));
    } catch (_) {}
    return msg;
  }

  $(document).on("click", ".btnDelDoc", function (e) {
    e.preventDefault();
    const id = String($(this).data("id") || "").trim();
    if (!id) return;
    $("#deleteDocModal").data("doc", id);
    $("#deleteDocName").text(id);
    $("#deleteDocModal").modal("show");
  });

  $("#btnConfirmDeleteDoc").on("click", function () {
    const id = String($("#deleteDocModal").data("doc") || "").trim();
    if (!id) return;
    $.ajax({
      url: API + "/documents/" + encodeURIComponent(id),
      method: "DELETE",
    })
      .done(function () {
        $("#deleteDocModal").modal("hide");
        toast("success", "Đã xóa văn bản.");
        loadAll();
      })
      .fail(function (xhr) {
        toast("danger", readAjaxError(xhr, "Không xóa được văn bản."));
      });
  });

  $(document).on("click", ".btnSummaryAudio", function (e) {
    e.preventDefault();
    const id = String($(this).data("id") || "").trim();
    if (!id) return;
    const $btn = $(this);
    const prevHtml = $btn.html();
    $btn.html('<i class="fa fa-spinner fa-spin"></i>').addClass("disabled");
    const $cell = $btn.closest(".trich");
    const $audioArea = $cell.find(".summary-audio");
    $audioArea.html("<span>Đang tạo audio...</span>");

    $.ajax({
      url: API + "/audio_doc",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ doc_id: String(id) }),
    })
      .done(function (r) {
        if (r && r.ok === false) {
          $audioArea.html("<span style='color:#c00'>Lỗi: " + htmlEscape(r.error || "") + "</span>");
          $btn.html(prevHtml).removeClass("disabled");
          return;
        }
        let waited = 0;
        const timer = setInterval(function () {
          $.getJSON(API + "/audio_status", { doc_id: id }).done(function (st) {
            if (!st || !st.ok) return;
            const s = String(st.audio_status || "").toLowerCase();
            if (s === "ready" && st.audio_path) {
              const pid = `audioSummary_${id}`;
              const bust = encodeURIComponent(st.audio_updated_at || new Date().toISOString());
              const src = `${FILE_API}/download-audio/${encodeURIComponent(st.audio_path)}?t=${bust}`;
              $audioArea.html(`<audio id="${pid}" controls src="${src}" style="width:100%"></audio>`);
              setTimeout(function () {
                try {
                  stopAllAudiosExcept(pid);
                  browserTtsStop();
                  const el = document.getElementById(pid);
                  el.playbackRate = 1.5;
                  el.play();
                } catch (_) {}
              }, 200);
              clearInterval(timer);
              $btn.html(prevHtml).removeClass("disabled");
            } else if (s === "failed") {
              const rawErr = String(st.audio_error || "").trim();
              const msg = friendlyError(rawErr);
              let extra = "";
              if (isLikelyTtsUnavailable(rawErr)) {
                extra =
                  "<div style='margin-top:6px'>" +
                  `<a href=\"#\" class=\"btnSummaryBrowserTts\" data-id=\"${htmlEscape(id)}\">Nghe bằng trình duyệt</a>` +
                  "</div>";
              }
              $audioArea.html("<span style='color:#c00'>Lỗi: " + htmlEscape(msg || rawErr || "") + "</span>" + extra);
              clearInterval(timer);
              $btn.html(prevHtml).removeClass("disabled");
            }
          });
          waited += 2;
          if (waited >= 70) {
            $audioArea.html("<span style='color:#c00'>Quá thời gian chờ. Kiểm tra cấu hình TTS.</span>");
            clearInterval(timer);
            $btn.html(prevHtml).removeClass("disabled");
          }
        }, 2000);
      })
      .fail(function (xhr) {
        const msg = readAjaxError(xhr, "Không gọi được API audio.");
        $audioArea.html("<span style='color:#c00'>" + htmlEscape(msg) + "</span>");
        $btn.html(prevHtml).removeClass("disabled");
      });
  });

  function loadAiProviders() {
    return $.getJSON(API + "/ai_providers").done(function (r) {
      const $sel = $("#modelSelect");
      $sel.empty();
      $sel.append(`<option value="">Tự động</option>`);
      try {
        const enabled = !!(r && r.enabled);
        const provider = (r && r.provider) ? String(r.provider) : "fallback";
        if (!enabled) $("#aiMeta").text("LLM: fallback (chưa cấu hình OpenAI key/provider) | Provider: " + provider);
        else $("#aiMeta").text("LLM: on | Provider: " + provider);
      } catch (_) {}
      const models = (r && r.models) || [];
      models.forEach((m) => {
        if (!m || typeof m !== "object") return;
        const v = m.value == null ? "" : String(m.value);
        const label = m.label == null ? v : String(m.label);
        if (v === "") return;
        $sel.append(`<option value="${htmlEscape(v)}">${htmlEscape(label)}</option>`);
      });
    });
  }

  function renderMemberList(members) {
    const exts = [".txt", ".md", ".html", ".htm", ".docx", ".pdf"];
    let html = "";
    (members || []).forEach((m, idx) => {
      const name = String(m || "");
      const low = name.toLowerCase();
      const checked = exts.some((x) => low.endsWith(x)) ? "checked" : "";
      html += `<div class="checkbox" style="margin:4px 0;"><label><input class="memChk" type="checkbox" value="${htmlEscape(name)}" ${checked}> ${htmlEscape(name)}</label></div>`;
    });
    $("#memberList").html(html || "<div style='color:#777'>Không có file trong ZIP</div>");
  }

  $(document).on("click", ".btnSumm", function (e) {
    e.preventDefault();
    const id = $(this).data("id") || "";
    if (!id) return;
    $("#summaryModal").data("doc", String(id));
    setAiStatus("");
    $("#aiMeta").text("");
    $("#summaryInfo").text("Đang tải danh sách file...");
    $("#memberList").html("");
    $("#summaryModal").modal("show");
    loadSummaryPrompts();
    $.getJSON(API + "/zip_members", { doc_id: id })
      .done(function (r) {
        $("#summaryInfo").text(`[${r.so_ky_hieu || ""}] ${r.trich_yeu || ""}`);
        renderMemberList(r.members || []);
      })
      .fail(function () {
        $("#summaryInfo").text("Không đọc được danh sách file ZIP");
      });
    loadAiProviders();
  });

  $("#btnStartAI").on("click", function () {
    const id = $("#summaryModal").data("doc");
    const members = [];
    $(".memChk:checked").each(function () {
      members.push($(this).val());
    });
    const model = $("#modelSelect").val() || "";
    const prompt_mode = String($("#promptSelect").val() || "").trim() || String($("input[name='promptMode']:checked").val() || "").trim();
    if (!prompt_mode) {
      toast("warning", "Chưa chọn prompt tóm tắt. Hãy tạo prompt trong 'Quản lý prompt'.");
      return;
    }
    const $btn = $("#btnStartAI");
    const prevHtml = $btn.html();
    $btn.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Đang chạy...');
    $.ajax({
      url: API + "/ai_summary",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ doc_id: id, selected_members: members, model, prompt_mode }),
    })
      .done(function () {
        const label = String(model || "").trim() ? model : "Tự động";
        setAiStatus("Đang tóm tắt bằng: " + label + "...");
        const timer = setInterval(function () {
          $.getJSON(API + "/ai_result", { doc_id: id }).done(function (r) {
            if (!r || !r.ok) return;
            const st = String(r.ai_status || "").toUpperCase();
            if (st === "READY") {
              const md = String(r.ai_model || "").trim() || "fallback";
              $("#aiMeta").text("Model: " + md);
              setAiStatus(String(r.ai_summary || ""));
              clearInterval(timer);
              $btn.prop("disabled", false).html(prevHtml);
              loadRecent();
            } else if (st === "FAILED") {
              $("#aiMeta").text("Model: " + (String(r.ai_model || "").trim() || "—"));
              setAiStatus("Lỗi: " + (r.ai_error || ""));
              clearInterval(timer);
              $btn.prop("disabled", false).html(prevHtml);
            } else {
              setAiStatus("Đang xử lý...");
            }
          });
        }, 2000);
      })
      .fail(function (xhr) {
        const msg = (xhr && xhr.responseText) || "Lỗi gọi AI";
        setAiStatus(msg);
        $btn.prop("disabled", false).html(prevHtml);
      });
  });

  $("#btnReadDoc").on("click", function () {
    const id = $("#summaryModal").data("doc");
    const members = [];
    $(".memChk:checked").each(function () {
      members.push($(this).val());
    });
    $("#readDocInfo").text("Đang đọc nội dung...");
    $("#readDocText").text("");
    $("#readDocModal").modal("show");
    $.ajax({
      url: API + "/doc_text",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ doc_id: id, members, max_chars: 50000 }),
    })
      .done(function (r) {
        const txt = (r && r.text) || "";
        $("#readDocInfo").text((r && r.truncated) ? "Nội dung (đã cắt bớt do quá dài)" : "Nội dung");
        $("#readDocText").text(String(txt || ""));
      })
      .fail(function (xhr) {
        let msg = "Không đọc được nội dung.";
        try {
          const r = JSON.parse(xhr.responseText || "{}");
          if (r && r.detail) msg = String(r.detail);
        } catch (_) {}
        $("#readDocInfo").text("Lỗi");
        $("#readDocText").text(msg);
      });
  });

  $("#btnManagePrompts").on("click", function () {
    $("#promptManageModal").modal("show");
    loadPromptPresetsForManage();
  });

  $("#btnReloadPromptPresets").on("click", function () {
    loadPromptPresetsForManage();
  });

  $("#btnAddPromptPreset").on("click", function () {
    const now = new Date();
    const pid = "p" + now.getFullYear() + String(now.getMonth() + 1).padStart(2, "0") + String(now.getDate()).padStart(2, "0") + "_" + String(now.getHours()).padStart(2, "0") + String(now.getMinutes()).padStart(2, "0") + String(now.getSeconds()).padStart(2, "0");
    const body = { id: pid, label: "Prompt mới", prompt: "Bạn là trợ lý tóm tắt văn bản hành chính. Trả lời tiếng Việt.", enabled: true, sort_order: 50 };
    $.ajax({
      url: API + "/prompt_presets",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify(body),
    })
      .done(function () {
        toast("success", "Đã thêm prompt.");
        loadPromptPresetsForManage();
        loadSummaryPrompts();
      })
      .fail(function (xhr) {
        toast("danger", readAjaxError(xhr, "Không thêm được prompt."));
      });
  });

  $(document).on("click", ".btnSavePrompt", function (e) {
    e.preventDefault();
    const id = String($(this).data("id") || "").trim();
    if (!id) return;
    const $tr = $(this).closest("tr");
    const label = $tr.find(".pp-label").val() || "";
    const prompt = $tr.find(".pp-prompt").val() || "";
    const enabled = $tr.find(".pp-enabled").is(":checked");
    const sort_order = parseInt($tr.find(".pp-sort").val() || "0", 10) || 0;
    $.ajax({
      url: API + "/prompt_presets",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ id, label, prompt, enabled, sort_order }),
    })
      .done(function () {
        toast("success", "Đã lưu prompt.");
        loadPromptPresetsForManage();
        loadSummaryPrompts();
      })
      .fail(function (xhr) {
        toast("danger", readAjaxError(xhr, "Không lưu được prompt."));
      });
  });

  $(document).on("change", ".pp-enabled, .pp-sort", function () {
    const $tr = $(this).closest("tr");
    const id = String($tr.find(".pp-id").val() || "").trim();
    if (!id) return;
    const label = $tr.find(".pp-label").val() || "";
    const prompt = $tr.find(".pp-prompt").val() || "";
    const enabled = $tr.find(".pp-enabled").is(":checked");
    const sort_order = parseInt($tr.find(".pp-sort").val() || "0", 10) || 0;
    $.ajax({
      url: API + "/prompt_presets",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ id, label, prompt, enabled, sort_order }),
    })
      .done(function () {
        toast("success", "Đã cập nhật prompt.");
        loadPromptPresetsForManage();
        loadSummaryPrompts();
      })
      .fail(function (xhr) {
        toast("danger", readAjaxError(xhr, "Không cập nhật được prompt."));
      });
  });

  $(document).on("click", ".btnDelPrompt", function (e) {
    e.preventDefault();
    const id = String($(this).data("id") || "").trim();
    if (!id) return;
    if (!confirm("Xóa prompt '" + id + "'?")) return;
    $.ajax({
      url: API + "/prompt_presets/" + encodeURIComponent(id),
      method: "DELETE",
    })
      .done(function () {
        toast("success", "Đã xóa prompt.");
        loadPromptPresetsForManage();
        loadSummaryPrompts();
      })
      .fail(function (xhr) {
        toast("danger", readAjaxError(xhr, "Không xóa được prompt."));
      });
  });
});
