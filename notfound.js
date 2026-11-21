const missingPath = document.getElementById("path");

try {
  missingPath.textContent = decodeURIComponent(location.pathname + location.search);
} catch (error) {
  missingPath.textContent = location.pathname;
}
