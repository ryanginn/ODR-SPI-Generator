// Applies the saved colour theme before first paint (the CSP forbids inline scripts).
try {
  const t = localStorage.getItem("odrspi.theme");
  if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
} catch (e) { /* storage unavailable: follow the system theme */ }
