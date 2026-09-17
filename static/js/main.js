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

    // 3. Mobile Menu Toggle (with hamburger/X icon swap)
    const mobileBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');
    const mobileMenuIcon = document.getElementById('mobile-menu-icon');
    if (mobileBtn && mobileMenu) {
        mobileBtn.addEventListener('click', () => {
            const isOpen = !mobileMenu.classList.contains('hidden');
            mobileMenu.classList.toggle('hidden');
            if (mobileMenuIcon) {
                if (isOpen) {
                    mobileMenuIcon.classList.remove('fa-xmark');
                    mobileMenuIcon.classList.add('fa-bars');
                } else {
                    mobileMenuIcon.classList.remove('fa-bars');
                    mobileMenuIcon.classList.add('fa-xmark');
                }
            }
        });
    }

    // 4. Floating Action Button (FAB) Toggle for Mobile
    const fabToggle = document.getElementById('fab-toggle');
    const fabMenu = document.getElementById('fab-menu');
    const fabOverlay = document.getElementById('fab-overlay');
    const fabIcon = document.getElementById('fab-icon');

    function closeFab() {
        if (fabToggle) fabToggle.classList.remove('active');
        if (fabMenu) fabMenu.classList.remove('open');
        if (fabOverlay) fabOverlay.classList.remove('open');
    }

    function openFab() {
        if (fabToggle) fabToggle.classList.add('active');
        if (fabMenu) fabMenu.classList.add('open');
        if (fabOverlay) fabOverlay.classList.add('open');
    }

    if (fabToggle) {
        fabToggle.addEventListener('click', () => {
            const isOpen = fabToggle.classList.contains('active');
            if (isOpen) {
                closeFab();
            } else {
                openFab();
            }
        });
    }

    if (fabOverlay) {
        fabOverlay.addEventListener('click', closeFab);
    }

    // Close FAB menu on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeFab();
        }
    });

    // 5. Filterable Gallery Logic
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

    // 6. Interactive Question Paper Semester Filter Tabs
    const qpTabs = document.querySelectorAll('.qp-filter-tab');
    if (qpTabs.length > 0) {
        qpTabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                const targetSem = tab.getAttribute('data-sem');
                if (typeof window.filterQpSemester === 'function') {
                    window.filterQpSemester(tab, targetSem);
                }
            });
        });
    }

    // 7. Toast Notification Helper
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

    // 8. Hide floating sidebar when scrolled to footer to avoid overlap
    const sidebar = document.getElementById('floating-sidebar');
    const footer = document.querySelector('footer');
    if (sidebar && footer) {
        const sidebarObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    sidebar.style.opacity = '0';
                    sidebar.style.pointerEvents = 'none';
                } else {
                    sidebar.style.opacity = '1';
                    sidebar.style.pointerEvents = 'auto';
                }
            });
        }, { threshold: 0.1 });
        sidebarObserver.observe(footer);
    }
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

// ============ QUESTION PAPERS SEMESTER FILTER ============
window.filterQpSemester = function(btn, selectedSem) {
    try {
        const tabs = document.querySelectorAll('.qp-filter-tab');
        const cards = document.querySelectorAll('.qp-sem-card, .qp-item-card');
        const emptyMsg = document.getElementById('qp-empty-filter');

        // Resolve target button accurately
        let targetBtn = btn;
        if (!targetBtn || !(targetBtn instanceof Element)) {
            targetBtn = document.querySelector('.qp-filter-tab[data-sem="' + selectedSem + '"]');
        } else if (!targetBtn.classList.contains('qp-filter-tab')) {
            targetBtn = targetBtn.closest('.qp-filter-tab');
        }

        // 1. Reset ALL tabs cleanly: remove active classes, attributes, and inline styles
        tabs.forEach(t => {
            t.classList.remove('active-tab', 'active');
            t.setAttribute('aria-selected', 'false');
            t.setAttribute('data-active', 'false');
            t.style.removeProperty('background');
            t.style.removeProperty('color');
            t.style.removeProperty('border-color');
            t.style.removeProperty('box-shadow');
            t.style.removeProperty('transform');
            if (typeof t.blur === 'function') t.blur();
        });

        // 2. Mark the selected button as ACTIVE with class, attribute, and guaranteed inline style
        if (targetBtn) {
            targetBtn.classList.add('active-tab', 'active');
            targetBtn.setAttribute('aria-selected', 'true');
            targetBtn.setAttribute('data-active', 'true');
            targetBtn.style.setProperty('background', 'linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%)', 'important');
            targetBtn.style.setProperty('color', '#ffffff', 'important');
            targetBtn.style.setProperty('border-color', '#1e3a8a', 'important');
            targetBtn.style.setProperty('box-shadow', '0 4px 14px rgba(30, 58, 138, 0.38)', 'important');
            if (typeof targetBtn.blur === 'function') targetBtn.blur();
        }

        // 3. Helper to extract digit from semester strings
        function getDigit(str) {
            if (!str) return '';
            const m = String(str).match(/\d+/);
            return m ? m[0] : String(str).trim().toLowerCase();
        }

        const semStr = String(selectedSem || (targetBtn ? targetBtn.getAttribute('data-sem') : 'all')).trim();
        const targetNum = getDigit(semStr);
        const isAll = (!semStr || semStr.toLowerCase() === 'all');
        let visibleCount = 0;

        // 4. Filter question paper semester cards
        cards.forEach(card => {
            const cardSem = (card.getAttribute('data-semester') || '').trim();
            const cardNum = getDigit(cardSem);

            let match = false;
            if (isAll) {
                match = true;
            } else if (targetNum && cardNum && targetNum === cardNum) {
                match = true;
            } else if (cardSem.toLowerCase() === semStr.toLowerCase()) {
                match = true;
            }

            if (match) {
                card.style.setProperty('display', 'flex', 'important');
                card.classList.remove('hidden');
                visibleCount++;
            } else {
                card.style.setProperty('display', 'none', 'important');
                card.classList.add('hidden');
            }
        });

        // 5. Update empty state visibility
        if (emptyMsg) {
            if (visibleCount === 0) {
                emptyMsg.style.setProperty('display', 'block', 'important');
                emptyMsg.classList.remove('hidden');
            } else {
                emptyMsg.style.setProperty('display', 'none', 'important');
                emptyMsg.classList.add('hidden');
            }
        }
    } catch (e) {
        console.error('filterQpSemester error:', e);
    }
};

// Auto-blur on mouseup so no focus state or color sticks after clicking
document.addEventListener('mouseup', function(e) {
    const el = e.target.closest('.qp-filter-tab, .qp-download-btn');
    if (el && typeof el.blur === 'function') {
        el.blur();
    }
});

