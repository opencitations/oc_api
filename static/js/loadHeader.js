async function initActiveNav() {
    // Get current subdomain in lowercase
    const currentSubdomain = window.location.host.split(".")[0].toLowerCase();

    // Use more efficient querySelector when possible
    const navLinks = document.querySelectorAll(".navbar-nav .nav-link");

    navLinks.forEach((link) => {
        // Convert to lowercase for case-insensitive comparison
        if (link.href.toLowerCase().includes(`${currentSubdomain}.opencitations.net`)) {
            // Remove active class from other links and add to current
            document.querySelector(".nav-link.active")?.classList.remove("active");
            link.classList.add("active");
        }
    });
}

async function loadHeader() {
    try {
        const response = await fetch('/static/header.html');
        const html = await response.text();
        document.getElementById('header-container').innerHTML = html;
        
        // Initialize active nav only after header is loaded
        setTimeout(200)
        initActiveNav();
    } catch (error) {
        console.error('Error loading header:', error);
    }
}

window.addEventListener('load', loadHeader);