/* =========================================================================
   Travelers Exchange — Frontend JavaScript
   ========================================================================= */

(function () {
    "use strict";

    /* ------------------------------------------------------------------
       Copy to Clipboard
       ------------------------------------------------------------------ */
    window.copyToClipboard = function (text, btnElement) {
        navigator.clipboard.writeText(text).then(function () {
            if (btnElement) {
                var original = btnElement.textContent;
                btnElement.textContent = "Copied!";
                btnElement.classList.add("copied");
                setTimeout(function () {
                    btnElement.textContent = original;
                    btnElement.classList.remove("copied");
                }, 2000);
            }
        }).catch(function () {
            // Fallback for older browsers
            var textarea = document.createElement("textarea");
            textarea.value = text;
            textarea.style.position = "fixed";
            textarea.style.opacity = "0";
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand("copy");
            document.body.removeChild(textarea);

            if (btnElement) {
                var original = btnElement.textContent;
                btnElement.textContent = "Copied!";
                btnElement.classList.add("copied");
                setTimeout(function () {
                    btnElement.textContent = original;
                    btnElement.classList.remove("copied");
                }, 2000);
            }
        });
    };

    /* ------------------------------------------------------------------
       Flash Message Auto-Dismiss
       ------------------------------------------------------------------ */
    function initFlashMessages() {
        var alerts = document.querySelectorAll(".alert[data-auto-dismiss]");
        alerts.forEach(function (alert) {
            setTimeout(function () {
                alert.style.opacity = "0";
                alert.style.transform = "translateY(-10px)";
                alert.style.transition = "opacity 0.3s ease, transform 0.3s ease";
                setTimeout(function () {
                    alert.remove();
                }, 300);
            }, 5000);
        });

        // Close buttons
        document.querySelectorAll(".alert-close").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var alert = btn.closest(".alert");
                if (alert) {
                    alert.style.opacity = "0";
                    alert.style.transform = "translateY(-10px)";
                    alert.style.transition = "opacity 0.3s ease, transform 0.3s ease";
                    setTimeout(function () {
                        alert.remove();
                    }, 300);
                }
            });
        });
    }

    /* ------------------------------------------------------------------
       Flash Messages from URL Query Params
       ------------------------------------------------------------------ */
    function showFlashFromURL() {
        var params = new URLSearchParams(window.location.search);
        var container = document.getElementById("flash-container");
        if (!container) return;

        var success = params.get("success");
        var error = params.get("error");
        var info = params.get("info");

        if (success) {
            showAlert(container, "success", success);
        }
        if (error) {
            showAlert(container, "error", error);
        }
        if (info) {
            showAlert(container, "info", info);
        }

        // Clean URL without reloading
        if (success || error || info) {
            var url = new URL(window.location);
            url.searchParams.delete("success");
            url.searchParams.delete("error");
            url.searchParams.delete("info");
            window.history.replaceState({}, "", url);
        }
    }

    function showAlert(container, type, message) {
        var div = document.createElement("div");
        div.className = "alert alert-" + type;
        div.setAttribute("data-auto-dismiss", "true");
        div.innerHTML =
            '<span>' + escapeHTML(message) + '</span>' +
            '<button class="alert-close" aria-label="Close">&times;</button>';
        container.appendChild(div);

        // Re-init close handler for new alert
        div.querySelector(".alert-close").addEventListener("click", function () {
            div.style.opacity = "0";
            div.style.transform = "translateY(-10px)";
            div.style.transition = "opacity 0.3s ease, transform 0.3s ease";
            setTimeout(function () {
                div.remove();
            }, 300);
        });

        // Auto-dismiss
        setTimeout(function () {
            if (div.parentNode) {
                div.style.opacity = "0";
                div.style.transform = "translateY(-10px)";
                div.style.transition = "opacity 0.3s ease, transform 0.3s ease";
                setTimeout(function () {
                    if (div.parentNode) div.remove();
                }, 300);
            }
        }, 5000);
    }

    function escapeHTML(str) {
        var div = document.createElement("div");
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    /* ------------------------------------------------------------------
       Login Form Handler
       ------------------------------------------------------------------ */
    function initLoginForm() {
        var form = document.getElementById("login-form");
        if (!form) return;

        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var errorDiv = document.getElementById("login-error");
            var submitBtn = form.querySelector('button[type="submit"]');
            var originalText = submitBtn.textContent;

            errorDiv.classList.remove("visible");
            submitBtn.disabled = true;
            submitBtn.textContent = "Signing in...";

            var formData = new FormData(form);

            fetch("/api/auth/login", {
                method: "POST",
                body: formData,
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.success) {
                        window.location.href = "/dashboard";
                    } else {
                        errorDiv.textContent = data.error || "Login failed.";
                        errorDiv.classList.add("visible");
                        submitBtn.disabled = false;
                        submitBtn.textContent = originalText;
                    }
                })
                .catch(function () {
                    errorDiv.textContent = "Network error. Please try again.";
                    errorDiv.classList.add("visible");
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                });
        });
    }

    /* ------------------------------------------------------------------
       Register Form Handler
       ------------------------------------------------------------------ */
    function initRegisterForm() {
        var form = document.getElementById("register-form");
        if (!form) return;

        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var errorDiv = document.getElementById("register-error");
            var submitBtn = form.querySelector('button[type="submit"]');
            var originalText = submitBtn.textContent;

            errorDiv.classList.remove("visible");

            // Client-side validation
            var password = form.querySelector('[name="password"]').value;
            var confirmPassword = form.querySelector('[name="confirm_password"]').value;

            if (password.length < 8) {
                errorDiv.textContent = "Password must be at least 8 characters.";
                errorDiv.classList.add("visible");
                return;
            }

            if (password !== confirmPassword) {
                errorDiv.textContent = "Passwords do not match.";
                errorDiv.classList.add("visible");
                return;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = "Creating account...";

            var formData = new FormData(form);

            fetch("/api/auth/register", {
                method: "POST",
                body: formData,
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.success) {
                        // Show wallet address reveal
                        var formSection = document.getElementById("register-form-section");
                        var successSection = document.getElementById("register-success");
                        var walletDisplay = document.getElementById("new-wallet-address");

                        formSection.classList.add("hidden");
                        successSection.classList.remove("hidden");
                        walletDisplay.textContent = data.wallet_address;

                        // Auto-redirect after 5 seconds
                        setTimeout(function () {
                            window.location.href = "/dashboard";
                        }, 5000);
                    } else {
                        errorDiv.textContent = data.error || "Registration failed.";
                        errorDiv.classList.add("visible");
                        submitBtn.disabled = false;
                        submitBtn.textContent = originalText;
                    }
                })
                .catch(function () {
                    errorDiv.textContent = "Network error. Please try again.";
                    errorDiv.classList.add("visible");
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                });
        });
    }

    /* ------------------------------------------------------------------
       Logout Handler
       ------------------------------------------------------------------ */
    function initLogout() {
        var logoutBtns = document.querySelectorAll(".logout-btn");
        logoutBtns.forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                fetch("/api/auth/logout", {
                    method: "POST",
                })
                    .then(function () {
                        window.location.href = "/login?success=Logged+out+successfully";
                    })
                    .catch(function () {
                        window.location.href = "/login";
                    });
            });
        });
    }

    /* ------------------------------------------------------------------
       Confirm Dialogs
       ------------------------------------------------------------------ */
    function initConfirmDialogs() {
        document.querySelectorAll("form[data-confirm]").forEach(function (form) {
            form.addEventListener("submit", function (e) {
                var message = form.getAttribute("data-confirm");
                if (!confirm(message)) {
                    e.preventDefault();
                }
            });
        });
    }

    /* ------------------------------------------------------------------
       Mobile Nav Toggle
       ------------------------------------------------------------------ */
    function initMobileNav() {
        var toggle = document.querySelector(".nav-toggle");
        var navLinks = document.querySelector(".nav-links");

        if (toggle && navLinks) {
            toggle.addEventListener("click", function () {
                navLinks.classList.toggle("open");
                var isOpen = navLinks.classList.contains("open");
                toggle.setAttribute("aria-expanded", isOpen);
                toggle.innerHTML = isOpen ? "&times;" : "&#9776;";
            });

            // Close nav when clicking a link (mobile)
            navLinks.querySelectorAll("a").forEach(function (link) {
                link.addEventListener("click", function () {
                    navLinks.classList.remove("open");
                    toggle.setAttribute("aria-expanded", "false");
                    toggle.innerHTML = "&#9776;";
                });
            });
        }
    }

    /* ------------------------------------------------------------------
       Send Form — Recipient Name Resolution (AJAX)
       ------------------------------------------------------------------ */
    function initSendFormRecipientResolve() {
        var addressInput = document.getElementById("to_address");
        var hintEl = document.getElementById("recipient-name-hint");
        if (!addressInput || !hintEl) return;

        var debounceTimer = null;

        addressInput.addEventListener("input", function () {
            clearTimeout(debounceTimer);
            var val = addressInput.value.trim();
            hintEl.textContent = "";
            hintEl.style.color = "";

            if (val.length < 4) return;

            debounceTimer = setTimeout(function () {
                fetch("/api/wallet/" + encodeURIComponent(val))
                    .then(function (res) {
                        if (!res.ok) return null;
                        return res.json();
                    })
                    .then(function (data) {
                        if (!data) {
                            hintEl.textContent = "";
                            return;
                        }
                        var name = data.display_name || null;
                        if (name) {
                            hintEl.textContent = "Sending to: " + name;
                            hintEl.style.color = "var(--success)";
                        } else {
                            hintEl.textContent = "Valid address";
                            hintEl.style.color = "var(--text-muted)";
                        }
                    })
                    .catch(function () {
                        hintEl.textContent = "";
                    });
            }, 400);
        });

        // Trigger on page load if prefilled
        if (addressInput.value.trim().length >= 4) {
            addressInput.dispatchEvent(new Event("input"));
        }
    }

    /* ------------------------------------------------------------------
       Send Form — Autocomplete Dropdown
       ------------------------------------------------------------------ */
    function initSendFormAutocomplete() {
        var addressInput = document.getElementById("to_address");
        if (!addressInput) return;

        // Create dropdown container
        var dropdown = document.createElement("ul");
        dropdown.id = "address-suggestions";
        dropdown.className = "autocomplete-dropdown";
        var wrapper = addressInput.parentNode;
        wrapper.style.position = "relative";
        wrapper.appendChild(dropdown);

        var debounceTimer = null;
        var currentFocus = -1;

        addressInput.addEventListener("input", function () {
            clearTimeout(debounceTimer);
            var q = addressInput.value.trim();
            dropdown.style.display = "none";
            dropdown.innerHTML = "";
            currentFocus = -1;

            // Only search if it looks like a username (not a full TRV- address)
            if (q.length < 2 || q.startsWith("TRV-")) return;

            debounceTimer = setTimeout(function () {
                fetch("/api/wallet/search?q=" + encodeURIComponent(q))
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        dropdown.innerHTML = "";
                        if (!data.results || data.results.length === 0) return;
                        data.results.forEach(function (item) {
                            var li = document.createElement("li");
                            li.className = "autocomplete-item";
                            var label = item.display_name || item.username || item.address;
                            var sub = item.address;
                            li.innerHTML = '<span style="font-weight:600;">' + escapeHTML(label) + '</span>' +
                                '<br><span style="font-size:0.8rem;color:var(--text-muted);font-family:var(--font-mono);">' + escapeHTML(sub) + '</span>';
                            li.addEventListener("mousedown", function (e) {
                                e.preventDefault();
                                addressInput.value = item.address;
                                dropdown.style.display = "none";
                                // Trigger name resolution
                                addressInput.dispatchEvent(new Event("input"));
                            });
                            dropdown.appendChild(li);
                        });
                        dropdown.style.display = "block";
                    })
                    .catch(function () {});
            }, 250);
        });

        // Keyboard navigation
        addressInput.addEventListener("keydown", function (e) {
            var items = dropdown.querySelectorAll("li");
            if (!items.length) return;
            if (e.key === "ArrowDown") {
                e.preventDefault();
                currentFocus = Math.min(currentFocus + 1, items.length - 1);
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                currentFocus = Math.max(currentFocus - 1, 0);
            } else if (e.key === "Enter" && currentFocus >= 0) {
                e.preventDefault();
                items[currentFocus].dispatchEvent(new MouseEvent("mousedown"));
                return;
            } else if (e.key === "Escape") {
                dropdown.style.display = "none";
                return;
            } else {
                return;
            }
            items.forEach(function (li, i) {
                li.classList.toggle("active", i === currentFocus);
            });
        });

        // Close dropdown when clicking outside
        document.addEventListener("click", function (e) {
            if (!wrapper.contains(e.target)) {
                dropdown.style.display = "none";
            }
        });
    }

    /* ------------------------------------------------------------------
       Marketplace Filters — Price Range Validation
       ------------------------------------------------------------------ */
    function initMarketFilters() {
        var minPrice = document.getElementById("min_price");
        var maxPrice = document.getElementById("max_price");
        if (!minPrice || !maxPrice) return;

        function validatePriceRange() {
            var min = parseInt(minPrice.value, 10);
            var max = parseInt(maxPrice.value, 10);

            if (minPrice.value && min < 0) {
                minPrice.value = 0;
            }
            if (maxPrice.value && max < 0) {
                maxPrice.value = 0;
            }
            if (minPrice.value && maxPrice.value && min > max) {
                maxPrice.value = minPrice.value;
            }
        }

        minPrice.addEventListener("change", validatePriceRange);
        maxPrice.addEventListener("change", validatePriceRange);
    }

    /* ------------------------------------------------------------------
       Exchange Trade — Dynamic Total Calculation
       ------------------------------------------------------------------ */
    function initExchangeTrade() {
        var buyInput = document.getElementById("buy-shares");
        var sellInput = document.getElementById("sell-shares");
        var buyTotal = document.getElementById("buy-total");
        var sellTotal = document.getElementById("sell-total");

        function updateTotal(input, totalEl) {
            if (!input || !totalEl) return;
            var price = parseInt(input.getAttribute("data-price"), 10) || 0;
            var shares = parseInt(input.value, 10) || 0;
            if (shares < 1) shares = 1;
            var total = price * shares;
            totalEl.textContent = total.toLocaleString() + " HM";
        }

        if (buyInput && buyTotal) {
            buyInput.addEventListener("input", function () {
                updateTotal(buyInput, buyTotal);
            });
        }
        if (sellInput && sellTotal) {
            sellInput.addEventListener("input", function () {
                updateTotal(sellInput, sellTotal);
            });
        }
    }

    /* ------------------------------------------------------------------
       IPO Form — Dynamic Total Calculation
       ------------------------------------------------------------------ */
    function initIPOForm() {
        var sharesInput = document.getElementById("num_shares");
        var totalEl = document.getElementById("ipo-total");
        if (!sharesInput || !totalEl) return;

        sharesInput.addEventListener("input", function () {
            var shares = parseInt(sharesInput.value, 10) || 0;
            if (shares < 100) shares = 100;
            var total = 5 * shares;
            totalEl.textContent = total.toLocaleString() + " HM";
        });
    }

    /* ------------------------------------------------------------------
       Initialise on DOM Ready
       ------------------------------------------------------------------ */
    document.addEventListener("DOMContentLoaded", function () {
        showFlashFromURL();
        initFlashMessages();
        initLoginForm();
        initRegisterForm();
        initLogout();
        initConfirmDialogs();
        initMobileNav();
        initSendFormRecipientResolve();
        initSendFormAutocomplete();
        initMarketFilters();
        initExchangeTrade();
        initIPOForm();
    });
})();
