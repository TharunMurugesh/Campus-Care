const e = React.createElement;

function HeroBanner() {
  return e(
    'section',
    { className: 'hero-banner shadow-lg rounded-4 p-4 mb-4' },
    e('div', { className: 'hero-copy' },
      e('p', { className: 'eyebrow text-uppercase mb-2 text-primary' }, 'CampusCare'),
      e('h1', { className: 'display-6 fw-bold mb-3' }, 'Professional campus issue tracking'),
      e('p', { className: 'lead text-muted mb-0' }, 'A polished blue, marine and white theme for students, staff, and campus administrators.')
    )
  );
}

function App() {
  return e('div', null, e(HeroBanner));
}

const root = document.getElementById('react-shell');
if (root) {
  ReactDOM.createRoot(root).render(e(App));
}
