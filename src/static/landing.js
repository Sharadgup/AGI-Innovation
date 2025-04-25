// Landing Page JavaScript

document.addEventListener('DOMContentLoaded', () => {
    console.log('Landing page JS loaded.');

    // --- Smooth Scrolling (for internal # links) --- 
    // Note: CSS scroll-behavior:smooth handles basic cases
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const targetId = this.getAttribute('href');
            // Check if it's more than just '#' (i.e., a section link)
            if (targetId.length > 1 && targetId.startsWith('#')) { 
                const targetElement = document.querySelector(targetId);
                if(targetElement) {
                    e.preventDefault(); // Prevent default jump only for section links
                    // Calculate scroll position considering fixed header height
                    const header = document.querySelector('.landing-header');
                    const headerHeight = header ? header.offsetHeight : 0;
                    const elementPosition = targetElement.getBoundingClientRect().top + window.pageYOffset;
                    const offsetPosition = elementPosition - headerHeight - 20; // Adjust offset (e.g., 20px spacing)

                    window.scrollTo({
                        top: offsetPosition,
                        behavior: 'smooth'
                    });
                }
            }
            // Let other links (like login) behave normally
        });
    });

    // --- Intersection Observer for Scroll Animations (Example) ---
    const sections = document.querySelectorAll('.content-section'); // Select elements to animate

    const observerOptions = {
        root: null, // relative to document viewport 
        rootMargin: '0px',
        threshold: 0.15 // Trigger slightly later (15% visible)
    };

    const observerCallback = (entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                // Optional: Unobserve after animation to save resources
                observer.unobserve(entry.target);
            } else {
                // Optional: Remove class if you want animation to repeat on scroll up
                // entry.target.classList.remove('visible');
            }
        });
    };

    const observer = new IntersectionObserver(observerCallback, observerOptions);

    sections.forEach(section => {
        observer.observe(section);
    });

    // --- Hide Header on Scroll Down --- 
    const header = document.querySelector('.landing-header');
    if (header) { // Check if header exists
        let lastScrollTop = 0;
        const delta = 10; // Trigger distance (higher value = less sensitive)
        const headerHeight = header.offsetHeight;
        let didScroll;

        window.addEventListener('scroll', function() {
            didScroll = true;
        });

        // Use setInterval for performance optimization
        setInterval(function() {
            if (didScroll) {
                hasScrolled();
                didScroll = false;
            }
        }, 250); // Check scroll position every 250ms

        function hasScrolled() {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

            // Make sure user scrolled more than delta
            if (Math.abs(lastScrollTop - scrollTop) <= delta) return;

            if (scrollTop > lastScrollTop && scrollTop > headerHeight){
                // Scroll Down - Hide header
                header.classList.add('header-hidden');
            } else {
                // Scroll Up - Show header
                // Special check for top of page
                if(scrollTop <= delta) { 
                    header.classList.remove('header-hidden');
                } else if(scrollTop + window.innerHeight < document.documentElement.scrollHeight) {
                    header.classList.remove('header-hidden');
                }
            }

            // Add/remove 'scrolled' class for background change
            if (scrollTop > 50) { // Add class after scrolling 50px
                header.classList.add('scrolled');
            } else {
                header.classList.remove('scrolled');
            }

            lastScrollTop = scrollTop <= 0 ? 0 : scrollTop; // For Mobile or negative scrolling
        }
    } // end if(header)

    // --- Placeholder for Advanced Animations --- 
    // Integration code for libraries like GSAP, Three.js, Lottie would go here.
    // Example: Initialize a 3D scene, load a Lottie animation for the logo, 
    // or create complex GSAP timelines for elements.

    // Example (pseudo-code for GSAP):
    // gsap.from('.hero-content h1', { duration: 1, y: -50, opacity: 0, ease: 'power3.out', delay: 0.5 });
    // gsap.from('.hero-content p', { duration: 1, y: -30, opacity: 0, ease: 'power3.out', delay: 0.8 });
    // gsap.from('.cta-button', { duration: 1, scale: 0.8, opacity: 0, ease: 'back.out(1.7)', delay: 1.1 });

    console.log('Add specific animation library initializations and control logic here.');

});
