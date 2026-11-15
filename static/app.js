// static/app.js

function showToast(text, variant = "info") {
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
  // Показать серверные flash-тосты
  document.querySelectorAll(".toast").forEach((el) => {
    const t = new bootstrap.Toast(el);
    t.show();
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