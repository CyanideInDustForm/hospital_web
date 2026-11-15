// static/app.js

// Цвета резервного режима (соответствуют Bootstrap text-bg-*)
const FALLBACK_COLORS = {
  success: "#198754", danger: "#dc3545",
  warning: "#c07c00", info: "#087990",
};

// Статичный цветной блок в правом верхнем углу — замена тоста,
// когда Bootstrap JS/CSS с CDN не загрузился (учебные ПК).
function fallbackAlert(text, variant = "info") {
  const container = document.querySelector(".toast-container");
  if (!container) return null;
  const el = document.createElement("div");
  el.setAttribute("role", "alert");
  el.style.cssText = [
    "display:block", "margin-bottom:8px",
    "min-width:280px", "max-width:380px",
    "padding:12px 40px 12px 16px", "border-radius:6px", "color:#fff",
    "background:" + (FALLBACK_COLORS[variant] || FALLBACK_COLORS.info),
    "box-shadow:0 4px 16px rgba(0,0,0,.25)",
  ].join(";");
  el.textContent = text;
  const close = document.createElement("button");
  close.textContent = "×";
  close.setAttribute("aria-label", "Закрыть");
  close.style.cssText = "position:absolute;top:6px;right:10px;background:none;border:none;color:#fff;font-size:20px;line-height:1;cursor:pointer";
  close.addEventListener("click", () => el.remove());
  el.appendChild(close);
  container.appendChild(el);
  return el;
}

function showToast(text, variant = "info") {
  if (typeof bootstrap === "undefined") {
    // резервный режим без CDN: показываем статичный блок вместо тоста
    fallbackAlert(text, variant);
    return;
  }

  const container = document.querySelector(".toast-container");
  if (!container) return;

  const el = document.createElement("div");
  el.className = `toast align-items-center text-bg-${variant}`;
  el.setAttribute("role", "alert");
  el.setAttribute("aria-live", "assertive");
  el.setAttribute("aria-atomic", "true");
  el.dataset.bsDelay = "5000";

  el.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${text}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto"
              data-bs-dismiss="toast" aria-label="Close"></button>
    </div>
  `;

  container.appendChild(el);
  const toast = new bootstrap.Toast(el);
  toast.show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}

document.addEventListener("DOMContentLoaded", () => {
  // Показать серверные flash-тосты; если Bootstrap JS не загрузился —
  // заменить тосты статичными цветными блоками, чтобы сообщения
  // были видны при любом раскладе
  document.querySelectorAll(".toast").forEach((el) => {
    if (typeof bootstrap === "undefined") {
      const body = el.querySelector(".toast-body");
      const bg = [...el.classList].find((c) => c.startsWith("text-bg-"));
      const variant = bg ? bg.replace("text-bg-", "") : "info";
      const alertEl = fallbackAlert(body ? body.textContent : "", variant);
      if (alertEl) el.replaceWith(alertEl); else el.remove();
    } else {
      const t = new bootstrap.Toast(el);
      t.show();
    }
  });

  // Bootstrap validation helper
  document.querySelectorAll(".needs-validation").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    });
  });

  // Синхронизация «пациент → даты приёмов» в поиске по двум таблицам:
  // при выборе пациента форма отправляется автоматически — сервер возвращает
  // и список дат его приёмов, и сразу результат поиска (замечание преподавателя).
  const cascadePatient = document.getElementById("cascadePatient");
  const cascadeVisit = document.getElementById("cascadeVisit");

  if (cascadePatient) {
    cascadePatient.addEventListener("change", () => {
      if (cascadePatient.value) cascadePatient.form.submit();
    });
  }
  if (cascadeVisit) {
    cascadeVisit.addEventListener("change", () => {
      cascadeVisit.form.submit();
    });
  }
});