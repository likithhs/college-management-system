// Seshadripuram College Main JavaScript - Animations & Interactivity

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize AOS (Animate on Scroll)
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 800,
            easing: 'ease-out-cubic',
            once: true,
            offset: 80
        });
    }

    // 2. Dynamic Stat Counter Animation
    const stats = document.querySelectorAll('.counter-value');
    let animated = false;

    function animateCounters() {
        if (animated) return;
        stats.forEach(counter => {
            const target = +counter.getAttribute('data-target');
            const suffix = counter.getAttribute('data-suffix') || '';
            const duration = 2000;
            const stepTime = 20;
            const steps = duration / stepTime;
            const increment = target / steps;
            let current = 0;

            const timer = setInterval(() => {
                current += increment;
                if (current >= target) {
                    counter.innerText = target.toLocaleString() + suffix;
                    clearInterval(timer);
                } else {
                    counter.innerText = Math.floor(current).toLocaleString() + suffix;
                }
            }, stepTime);
        });
        animated = true;
    }

    // Scroll Observer for Counter
    const counterSection = document.getElementById('stats-section');
    if (counterSection) {
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) {
                animateCounters();
            }
        }, { threshold: 0.3 });
        observer.observe(counterSection);
    }

    // 3. Mobile Menu Toggle
    const mobileBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');
    if (mobileBtn && mobileMenu) {
        mobileBtn.addEventListener('click', () => {
            mobileMenu.classList.toggle('hidden');
        });
    }

    // 4. Filterable Gallery Logic
    const filterBtns = document.querySelectorAll('.gallery-filter-btn');
    const galleryItems = document.querySelectorAll('.gallery-item');

    if (filterBtns.length > 0) {
        filterBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                // Remove active styling from all
                filterBtns.forEach(b => {
                    b.classList.remove('bg-blue-900', 'text-white');
                    b.classList.add('bg-white', 'text-slate-700', 'hover:bg-slate-100');
                });
                // Add active styling to clicked
                btn.classList.remove('bg-white', 'text-slate-700', 'hover:bg-slate-100');
                btn.classList.add('bg-blue-900', 'text-white');

                const filter = btn.getAttribute('data-filter');

                galleryItems.forEach(item => {
                    const category = item.getAttribute('data-category');
                    if (filter === 'all' || category === filter) {
                        item.style.display = 'block';
                        item.classList.add('animate-fade-in');
                    } else {
                        item.style.display = 'none';
                    }
                });
            });
        });
    }

    // 5. Download Question Paper Simulation
    const downloadBtns = document.querySelectorAll('.download-paper-btn');
    downloadBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const fileName = btn.getAttribute('data-file');
            showToast(`📥 Downloading sample question paper: ${fileName}`);
        });
    });

    // 6. Toast Notification Helper
    window.showToast = function(message, type = 'info') {
        let toastBox = document.getElementById('toast-container');
        if (!toastBox) {
            toastBox = document.createElement('div');
            toastBox.id = 'toast-container';
            toastBox.className = 'fixed bottom-5 right-5 z-50 flex flex-col gap-3';
            document.body.appendChild(toastBox);
        }

        const toast = document.createElement('div');
        toast.className = `px-5 py-4 rounded-xl shadow-2xl text-white font-medium flex items-center gap-3 transition-all duration-300 transform translate-y-5 opacity-0 ${
            type === 'success' ? 'bg-emerald-600' : 'bg-blue-900 border border-blue-700'
        }`;
        toast.innerHTML = `
            <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <span>${message}</span>
        `;
        toastBox.appendChild(toast);

        setTimeout(() => {
            toast.classList.remove('translate-y-5', 'opacity-0');
        }, 10);

        setTimeout(() => {
            toast.classList.add('opacity-0', 'translate-y-5');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    };
});

// ============ DARK MODE TOGGLE ============
(function() {
    const html = document.documentElement;
    const toggle = document.getElementById('dark-mode-toggle');
    const icon = document.getElementById('dark-icon');
    
    // Check saved preference or system preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        html.classList.add('dark');
        if (icon) {
            icon.classList.remove('fa-moon');
            icon.classList.add('fa-sun');
        }
    }
    
    if (toggle) {
        toggle.addEventListener('click', () => {
            html.classList.toggle('dark');
            const isDark = html.classList.contains('dark');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            if (icon) {
                if (isDark) {
                    icon.classList.remove('fa-moon');
                    icon.classList.add('fa-sun');
                } else {
                    icon.classList.remove('fa-sun');
                    icon.classList.add('fa-moon');
                }
            }
        });
    }
})();

// ============ FORUM FILTER & SEARCH ============
(function() {
    const filterBtns = document.querySelectorAll('.forum-filter-btn');
    const searchInput = document.getElementById('forum-search');
    const forumPosts = document.querySelectorAll('.forum-post-item');
    
    if (filterBtns.length === 0) return;
    
    let activeCategory = 'all';
    
    function filterPosts() {
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        
        forumPosts.forEach(post => {
            const category = post.getAttribute('data-category');
            const text = post.textContent.toLowerCase();
            const matchesCategory = activeCategory === 'all' || category === activeCategory;
            const matchesSearch = !searchTerm || text.includes(searchTerm);
            
            post.style.display = (matchesCategory && matchesSearch) ? 'block' : 'none';
        });
    }
    
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => {
                b.classList.remove('bg-blue-900', 'text-white');
                b.classList.add('bg-white', 'text-slate-700');
            });
            btn.classList.remove('bg-white', 'text-slate-700');
            btn.classList.add('bg-blue-900', 'text-white');
            activeCategory = btn.getAttribute('data-filter');
            filterPosts();
        });
    });
    
    if (searchInput) {
        searchInput.addEventListener('input', filterPosts);
    }
})();
