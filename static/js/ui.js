/**
 * Common UI components and helpers:
 * Toasts, Modals, Theme toggler, Route progress tracker, and Skeletons.
 */

// Toast Notifications
function showToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.setAttribute('role', 'alert');

  const textSpan = document.createElement('span');
  textSpan.textContent = message;

  const closeBtn = document.createElement('button');
  closeBtn.innerHTML = '&times;';
  closeBtn.style.background = 'none';
  closeBtn.style.border = 'none';
  closeBtn.style.fontSize = '1.25rem';
  closeBtn.style.cursor = 'pointer';
  closeBtn.style.color = 'inherit';
  closeBtn.onclick = () => toast.remove();

  toast.appendChild(textSpan);
  toast.appendChild(closeBtn);
  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentElement) {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }
  }, duration);
}

// Modal Dialogs
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    const firstFocusable = modal.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (firstFocusable) firstFocusable.focus();
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
  }
}

// Dark Mode Theme Controller
function initTheme() {
  const saved = localStorage.getItem('rm_theme') || 'light';
  applyTheme(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('rm_theme', theme);
  const themeBtns = document.querySelectorAll('.theme-toggle-btn');
  themeBtns.forEach(btn => {
    btn.innerHTML = theme === 'dark' ? '☀️' : '🌙';
    btn.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
  });
}

// Render Route Progress (S1 .. S5)
function renderRouteProgress(containerId, routeStations, boardingStation, destStation, currentPosition) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const bIdx = routeStations.indexOf(boardingStation);
  const dIdx = routeStations.indexOf(destStation);
  const curIdx = routeStations.indexOf(currentPosition);

  let html = `
    <div class="route-tracker">
      <div class="route-active-line" style="
        left: calc(${(bIdx / (routeStations.length - 1)) * 100}% + 1rem);
        width: calc(${((dIdx - bIdx) / (routeStations.length - 1)) * 100}% - 2rem);
      "></div>
  `;

  routeStations.forEach((st, idx) => {
    const inSegment = (idx >= bIdx && idx <= dIdx);
    const isCurrent = (st === currentPosition);
    html += `
      <div class="route-stop ${inSegment ? 'in-segment' : ''} ${isCurrent ? 'current-pos' : ''}">
        <div class="route-dot" title="${st}">
          ${isCurrent ? '🚂' : idx + 1}
        </div>
        <div class="route-label">${st}</div>
      </div>
    `;
  });

  html += `</div>`;
  container.innerHTML = html;
}

// Status Badges Formatter
function getStatusBadge(status) {
  const map = {
    'PENDING_CONSENT': { cls: 'badge-pending', label: 'Pending Consent' },
    'ACCEPTED_BY_PASSENGER': { cls: 'badge-best', label: 'Accepted (Awaiting TTE)' },
    'TTE_APPROVED': { cls: 'badge-approved', label: 'Approved by TTE' },
    'TTE_REJECTED': { cls: 'badge-rejected', label: 'Rejected by TTE' },
    'DECLINED': { cls: 'badge-declined', label: 'Declined' },
    'CANCELLED': { cls: 'badge-neutral', label: 'Cancelled' },
    'EXPIRED': { cls: 'badge-expired', label: 'Expired' },
    'CLARIFICATION_REQUESTED': { cls: 'badge-possible', label: 'Clarification Needed' }
  };
  const item = map[status] || { cls: 'badge-neutral', label: status };
  return `<span class="badge ${item.cls}">${item.label}</span>`;
}

// Auto-run theme initializer
document.addEventListener('DOMContentLoaded', initTheme);

window.ui = {
  showToast,
  openModal,
  closeModal,
  initTheme,
  toggleTheme,
  renderRouteProgress,
  getStatusBadge
};
