document.addEventListener('DOMContentLoaded', () => {
  const taskTable = document.querySelector('[data-task-table]');
  const filterButtons = document.querySelectorAll('[data-filter]');

  const applyFilter = (filterValue) => {
    document.querySelectorAll('[data-task-row]').forEach((row) => {
      const rowStatus = row.dataset.taskStatus;
      const dueDate = row.dataset.taskDue;
      const isOverdue = Boolean(dueDate) && new Date(dueDate).setHours(0, 0, 0, 0) < new Date().setHours(0, 0, 0, 0) && rowStatus !== 'Done';

      const shouldShow =
        filterValue === 'all' ||
        (filterValue === 'overdue' && isOverdue) ||
        (filterValue !== 'all' && filterValue !== 'overdue' && rowStatus === filterValue);

      row.style.display = shouldShow ? '' : 'none';
    });
  };

  filterButtons.forEach((button) => {
    button.addEventListener('click', () => {
      filterButtons.forEach((item) => item.classList.remove('active'));
      button.classList.add('active');
      applyFilter(button.dataset.filter);
    });
  });

  if (taskTable) {
    taskTable.addEventListener('change', async (event) => {
      const select = event.target.closest('[data-status-select]');
      if (!select) {
        return;
      }

      const taskId = select.dataset.taskId;
      const row = document.querySelector(`[data-task-row][data-task-id="${taskId}"]`);

      try {
        const response = await fetch(`/api/tasks/${taskId}/status`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'same-origin',
          body: JSON.stringify({ status: select.value }),
        });

        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || 'Unable to update task.');
        }

        if (row) {
          row.dataset.taskStatus = payload.task.status;
          const statusCell = row.querySelector('.status-select');
          if (statusCell) {
            statusCell.value = payload.task.status;
          }
        }
      } catch (error) {
        alert(error.message);
      }
    });

    applyFilter('all');
  }
});