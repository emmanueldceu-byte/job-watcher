const els = {
  appName: document.querySelector('#app-name'),
  jobCount: document.querySelector('#job-count'),
  updatedAt: document.querySelector('#updated-at'),
  search: document.querySelector('#search'),
  company: document.querySelector('#company'),
  location: document.querySelector('#location'),
  newOnly: document.querySelector('#new-only'),
  jobs: document.querySelector('#jobs'),
  empty: document.querySelector('#empty'),
  notice: document.querySelector('#notice')
};

let allJobs = [];

function escapeHtml(value = '') {
  return value.replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#039;','"':'&quot;'}[c]));
}

function niceDate(value) {
  if (!value) return 'Waiting for first scan';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return `Updated ${d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}`;
}

function populateSelect(select, values, defaultLabel) {
  const current = select.value;
  select.innerHTML = `<option value="">${defaultLabel}</option>` +
    [...new Set(values.filter(Boolean))].sort().map(v => `<option>${escapeHtml(v)}</option>`).join('');
  select.value = current;
}

function card(job) {
  const chips = [...(job.matched_titles || []), ...(job.matched_keywords || [])];
  const excerpt = (job.description || '').slice(0, 280);
  return `
    <article class="job-card">
      <div class="job-top">
        <div>
          <p class="company">${escapeHtml(job.company || '')}</p>
          <h2>${escapeHtml(job.title || '')}</h2>
        </div>
        ${job.is_new ? '<span class="badge">NEW</span>' : ''}
      </div>
      <div class="meta">
        ${job.location_category ? `<span>⭐ ${escapeHtml(job.location_category)}</span>` : ''}
        ${job.location ? `<span>📍 ${escapeHtml(job.location)}</span>` : ''}
        ${job.date_posted ? `<span>🗓 ${escapeHtml(job.date_posted)}</span>` : ''}
        ${job.source ? `<span>↗ ${escapeHtml(job.source)}</span>` : ''}
      </div>
      ${excerpt ? `<p class="description">${escapeHtml(excerpt)}${job.description.length > 280 ? '…' : ''}</p>` : ''}
      ${chips.length ? `<div class="match-row">${chips.map(x => `<span class="chip">${escapeHtml(x)}</span>`).join('')}</div>` : ''}
      <a class="apply" href="${escapeHtml(job.url)}" target="_blank" rel="noopener noreferrer">View & apply</a>
    </article>`;
}

function render() {
  const q = els.search.value.trim().toLowerCase();
  const company = els.company.value;
  const location = els.location.value;
  const newOnly = els.newOnly.checked;

  const filtered = allJobs.filter(job => {
    const text = [job.title, job.company, job.location, job.description, ...(job.matched_titles || []), ...(job.matched_keywords || [])].join(' ').toLowerCase();
    return (!q || text.includes(q)) &&
      (!company || job.company === company) &&
      (!location || job.location === location) &&
      (!newOnly || job.is_new);
  });

  els.jobCount.textContent = `${filtered.length} match${filtered.length === 1 ? '' : 'es'}`;
  els.jobs.innerHTML = filtered.map(card).join('');
  els.empty.classList.toggle('hidden', filtered.length !== 0);
}

async function boot() {
  try {
    const response = await fetch(`jobs.json?v=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error('Could not load jobs.json');
    const data = await response.json();
    allJobs = data.jobs || [];
    els.appName.textContent = data.app_name || 'Daily Job Watcher';
    document.title = data.app_name || 'Daily Job Watcher';
    els.updatedAt.textContent = niceDate(data.updated_at);
    populateSelect(els.company, allJobs.map(j => j.company), 'All companies');
    populateSelect(els.location, allJobs.map(j => j.location), 'All locations');
    if ((data.errors || []).length) {
      els.notice.textContent = `Some sources could not be checked today: ${data.errors.map(e => e.company).join(', ')}.`;
      els.notice.classList.remove('hidden');
    }
    render();
  } catch (err) {
    els.notice.textContent = `The job data could not be loaded: ${err.message}`;
    els.notice.classList.remove('hidden');
    render();
  }
}

[els.search, els.company, els.location, els.newOnly].forEach(el => el.addEventListener('input', render));
boot();
