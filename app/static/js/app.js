// Vanilla JS utilities for Alpine.js and Tailwind
document.addEventListener('DOMContentLoaded', function () {
  // Enable dismissable flash messages
  const closeButtons = document.querySelectorAll('.flash-message .close-btn');
  closeButtons.forEach(button => {
    button.addEventListener('click', function () {
      const message = this.closest('.flash-message');
      message.style.opacity = '0';
      message.style.transform = 'translateY(-10px)';
      setTimeout(() => message.remove(), 300);
    });
  });

  // Initialize table sorting
  initTableSort();
});

// Table sorting functionality (vanilla JS)
function initTableSort() {
  const sortableTables = document.querySelectorAll('table.sortable');

  sortableTables.forEach(table => {
    const headers = table.querySelectorAll('th[data-sort]');

    headers.forEach(header => {
      header.addEventListener('click', function () {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const columnIndex = Array.from(this.parentNode.children).indexOf(this);
        const isAscending = !this.classList.contains('sorted-asc');

        // Remove sort classes from all headers
        headers.forEach(h => {
          h.classList.remove('sorted-asc', 'sorted-desc');
        });

        // Add appropriate sort class
        this.classList.add(isAscending ? 'sorted-asc' : 'sorted-desc');

        // Sort rows
        rows.sort((a, b) => {
          const aValue = a.children[columnIndex].textContent.trim();
          const bValue = b.children[columnIndex].textContent.trim();

          // Try to parse as numbers
          const aNum = parseFloat(aValue);
          const bNum = parseFloat(bValue);

          if (!isNaN(aNum) && !isNaN(bNum)) {
            return isAscending ? aNum - bNum : bNum - aNum;
          }

          // Sort as strings
          return isAscending
            ? aValue.localeCompare(bValue)
            : bValue.localeCompare(aValue);
        });

        // Reattach sorted rows
        rows.forEach(row => tbody.appendChild(row));
      });
    });
  });
}
