// Airport autocomplete: called by the onmousedown handler rendered in
// components/airport_options.html when the user picks a suggestion.
function selectAirport(field, code, label) {
  const hidden = document.getElementById(field + '_code');
  const visible = document.getElementById(field + '_query');
  const dropdown = document.getElementById(field + '_dropdown');
  if (hidden) hidden.value = code;
  if (visible) visible.value = label;
  if (dropdown) dropdown.innerHTML = '';
}

// Hidden inputs are excluded from native HTML validation, so make sure the
// user actually picked an airport (not just typed free text) before submit.
document.addEventListener('submit', function (event) {
  const form = event.target;
  const airportInputs = form.querySelectorAll('[data-airport-input]');
  for (const input of airportInputs) {
    const field = input.dataset.airportInput;
    const hidden = document.getElementById(field + '_code');
    if (hidden && !hidden.value) {
      event.preventDefault();
      input.focus();
      input.reportValidity && input.setCustomValidity('Pick an airport from the list.');
      input.reportValidity && input.reportValidity();
      window.setTimeout(function () { input.setCustomValidity(''); }, 2000);
      return;
    }
  }
});

// Close a dropdown when the user clicks/tabs away from its input.
document.addEventListener('focusout', function (event) {
  const input = event.target.closest('[data-airport-input]');
  if (!input) return;
  const field = input.dataset.airportInput;
  window.setTimeout(function () {
    const dropdown = document.getElementById(field + '_dropdown');
    if (dropdown) dropdown.innerHTML = '';
  }, 150);
});
