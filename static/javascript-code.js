document.addEventListener("DOMContentLoaded", function () {
  const navToggle = document.createElement("button");
  navToggle.classList.add("nav-toggle");
  navToggle.innerHTML = '<i class="fas fa-bars"></i>';

  const nav = document.querySelector("nav");
  const navLinks = document.querySelector(".nav-links");

  if (nav && navLinks) {
    nav.insertBefore(navToggle, navLinks);

    navToggle.addEventListener("click", function () {
      navLinks.classList.toggle("active");
    });
  }

  const forms = document.querySelectorAll("form");

  forms.forEach((form) => {
    form.addEventListener("submit", function (event) {
      let isValid = true;

      const emailInput = form.querySelector('input[type="email"]');
      if (emailInput) {
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailPattern.test(emailInput.value)) {
          showError(emailInput, "Please enter a valid email address");
          isValid = false;
        } else {
          removeError(emailInput);
        }
      }

      const passwordInput = form.querySelector('input[type="password"]');
      if (passwordInput && passwordInput.value.length < 6) {
        showError(passwordInput, "Password must be at least 6 characters");
        isValid = false;
      } else if (passwordInput) {
        removeError(passwordInput);
      }

      const phoneInput = form.querySelector('input[name="phone"]');
      if (phoneInput) {
        const phonePattern = /^\d{10}$|^\d{3}[-\s]\d{3}[-\s]\d{4}$/;
        if (!phonePattern.test(phoneInput.value.replace(/[\s()+-]/g, ""))) {
          showError(phoneInput, "Please enter a valid phone number");
          isValid = false;
        } else {
          removeError(phoneInput);
        }
      }

      const requiredInputs = form.querySelectorAll("[required]");
      requiredInputs.forEach((input) => {
        if (!input.value.trim()) {
          showError(input, "This field is required");
          isValid = false;
        } else {
          removeError(input);
        }
      });

      if (!isValid) {
        event.preventDefault();
      }
    });
  });

  function showError(input, message) {
    const formGroup = input.parentElement;
    let errorElement = formGroup.querySelector(".error-message");

    if (!errorElement) {
      errorElement = document.createElement("div");
      errorElement.className = "error-message";
      formGroup.appendChild(errorElement);
    }

    errorElement.textContent = message;
    input.classList.add("error-input");
  }

  function removeError(input) {
    const formGroup = input.parentElement;
    const errorElement = formGroup.querySelector(".error-message");

    if (errorElement) {
      formGroup.removeChild(errorElement);
    }

    input.classList.remove("error-input");
  }

  const flashMessages = document.querySelectorAll(".alert");

  flashMessages.forEach((message) => {
    setTimeout(() => {
      message.style.opacity = "0";
      setTimeout(() => {
        message.style.display = "none";
      }, 500);
    }, 5000);
  });

  const orderForm = document.getElementById("order-form");

  if (orderForm) {
    const fuelTypeSelect = document.getElementById("fuel-type");
    const quantityInput = document.getElementById("quantity");
    const priceDisplay = document.getElementById("price-display");

    const prices = {
      Petrol: 3.5,
      diesel: 3.75,
      propane: 2.9,
    };

    function updatePrice() {
      const fuelType = fuelTypeSelect.value;
      const quantity = parseFloat(quantityInput.value) || 0;

      if (fuelType && prices[fuelType] && quantity > 0) {
        const totalPrice = (prices[fuelType] * quantity).toFixed(2);
        priceDisplay.textContent = `$${totalPrice}`;
      } else {
        priceDisplay.textContent = "$0.00";
      }
    }

    fuelTypeSelect.addEventListener("change", updatePrice);
    quantityInput.addEventListener("input", updatePrice);

    updatePrice();
  }

  const statusForms = document.querySelectorAll(".admin-status-form");

  statusForms.forEach((form) => {
    form.addEventListener("submit", function (event) {
      const status = form.querySelector('select[name="status"]').value;
      const currentStatus = form.querySelector(
        'input[name="current_status"]'
      ).value;

      if (
        status === "cancelled" &&
        !confirm("Are you sure you want to cancel this order?")
      ) {
        event.preventDefault();
      } else if (
        status !== currentStatus &&
        !confirm(`Change status to ${status.replace("_", " ")}?`)
      ) {
        event.preventDefault();
      }
    });
  });
});
