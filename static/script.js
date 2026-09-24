// Simple JavaScript helpers (no libraries used)

// Show / hide the sidebar on small screens
function toggleSidebar() {
  document.getElementById("sidebar").classList.toggle("open");
}

// Ask before deleting a record
function confirmDelete() {
  return confirm("Are you sure you want to delete this record?");
}

// --- Validation helpers -----------------------------------------------

// Show a small red error message right under a field, and highlight the field
function showFieldError(field, message) {
  clearFieldError(field);
  const error = document.createElement("small");
  error.className = "field-error";
  error.style.color = "#d33";
  error.style.display = "block";
  error.style.marginTop = "4px";
  error.textContent = message;
  field.insertAdjacentElement("afterend", error);
  field.classList.add("invalid-field");
  field.style.borderColor = "#d33";
  field.style.boxShadow = "0 0 0 2px rgba(221, 51, 51, 0.15)";
}

// Remove any existing error message for a field and reset its highlight
function clearFieldError(field) {
  field.classList.remove("invalid-field");
  field.style.borderColor = "";
  field.style.boxShadow = "";
  const next = field.nextElementSibling;
  if (next && next.classList.contains("field-error")) {
    next.remove();
  }
}

// Basic per-field rules, applied only if the field is present in the form
function validateField(field) {
  const name = field.name;
  const value = field.value.trim();

  // Required check (applies to any field marked required)
  if (field.hasAttribute("required") && value === "") {
    showFieldError(field, "This field is required.");
    return false;
  }

  // Dropdowns (customer_id, vehicle_id) must have a real value selected
  if (field.tagName === "SELECT" && field.hasAttribute("required") && value === "") {
    showFieldError(field, "Please make a selection.");
    return false;
  }

  // If field is optional and empty, nothing more to check
  if (value === "") {
    clearFieldError(field);
    return true;
  }

  // Name: letters, spaces, apostrophes and hyphens only, at least 2 characters
  if (name === "name") {
    if (!/^[A-Za-z\s'-]{2,}$/.test(value)) {
      showFieldError(field, "Enter a valid name (letters only, at least 2 characters).");
      return false;
    }
  }

  // Phone: digits only, exactly 10 digits
  if (name === "phone") {
    if (!/^[0-9]{10}$/.test(value)) {
      showFieldError(field, "Enter a valid 10-digit phone number.");
      return false;
    }
  }

  // Email: standard format check (field is optional, only checked if filled)
  if (name === "email") {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      showFieldError(field, "Enter a valid email address.");
      return false;
    }
  }

  // Address: reasonable max length
  if (name === "address") {
    if (value.length > 150) {
      showFieldError(field, "Address is too long (max 150 characters).");
      return false;
    }
  }

  // Vehicle number: letters, numbers, spaces and hyphens only, 4-15 characters
  if (name === "vehicle_number") {
    if (!/^[A-Za-z0-9\s-]{4,15}$/.test(value)) {
      showFieldError(field, "Vehicle number should be 4-15 characters: letters, numbers, spaces or hyphens only.");
      return false;
    }
  }

  // Model: letters, numbers and spaces only
  if (name === "model") {
    if (!/^[A-Za-z0-9\s.\-]{1,50}$/.test(value)) {
      showFieldError(field, "Model can contain only letters, numbers, spaces, dots and hyphens.");
      return false;
    }
  }

  // Service type: letters, numbers and spaces, at least 3 characters
  if (name === "service_type") {
    if (!/^[A-Za-z0-9\s&,.()\/-]{3,100}$/.test(value)) {
      showFieldError(field, "Enter a valid service type (at least 3 characters).");
      return false;
    }
  }

  // Service date: must be a real, valid date
  if (name === "service_date") {
    const date = new Date(value);
    if (isNaN(date.getTime())) {
      showFieldError(field, "Enter a valid date.");
      return false;
    }
  }

  // Cost: must be a valid, non-negative number (reasonable upper limit too)
  if (name === "cost") {
    const num = parseFloat(value);
    if (isNaN(num) || num < 0) {
      showFieldError(field, "Cost must be a valid positive number.");
      return false;
    }
    if (num > 1000000) {
      showFieldError(field, "Cost seems too high, please check the value.");
      return false;
    }
  }

  clearFieldError(field);
  return true;
}

// Full form validation: checks every relevant field, shows all errors at once
function validateForm(form) {
  let isValid = true;
  const fields = form.querySelectorAll("input, select, textarea");

  fields.forEach((field) => {
    if (!validateField(field)) {
      isValid = false;
    }
  });

  if (!isValid) {
    const firstError = form.querySelector(".invalid-field");
    if (firstError) {
      firstError.focus();
      firstError.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  return isValid;
}

// Re-check a field as soon as the user edits it (clears the error once fixed)
document.addEventListener("input", function (e) {
  if (e.target.matches("input, select, textarea")) {
    validateField(e.target);
  }
});

// Also check a field as soon as the user leaves it (catches empty/invalid
// fields even before the form is submitted for the first time)
document.addEventListener(
  "blur",
  function (e) {
    if (e.target.matches("input, select, textarea") && e.target.closest("form")) {
      validateField(e.target);
    }
  },
  true
);

// Hide flash messages: success after 3 seconds, errors after 8 seconds
// (error messages are longer, e.g. "Cannot delete: ...", so they stay longer)
window.addEventListener("load", function () {
  document.querySelectorAll(".flash").forEach(function (m) {
    const delay = m.classList.contains("error") ? 8000 : 3000;
    setTimeout(function () {
      m.style.display = "none";
    }, delay);
  });
});
