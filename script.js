// Keep the displayed version aligned with the APK and the GitHub Release.
const version = '0.1.0';
document.querySelectorAll('[data-version]').forEach((node) => { node.textContent = version; });
document.querySelector('#year').textContent = new Date().getFullYear();
