const { useEffect } = React;

function HeroBanner() {
  return (
    <section className="hero-banner shadow-sm rounded-4 p-4 mb-4">
      <div className="hero-copy">
        <p className="eyebrow">CampusCare</p>
        <h1>Modern campus issue tracking built for speed and clarity.</h1>
        <p>Beautiful workflows for students, staff and campus managers with a polished navy, marine and fresh white theme.</p>
      </div>
    </section>
  );
}

function ThemeFooter() {
  return (
    <footer className="theme-footer mt-5 py-4 text-center text-muted">
      <p>CampusCare — professional campus ticketing in a crisp blue and marine palette.</p>
    </footer>
  );
}

function App() {
  useEffect(() => {
    document.body.classList.add('react-ready');
  }, []);

  return (
    <>
      <HeroBanner />
      <ThemeFooter />
    </>
  );
}

const rootElement = document.getElementById('react-shell');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(<App />);
}
