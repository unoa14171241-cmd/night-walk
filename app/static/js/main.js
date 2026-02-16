/**
 * Night-Walk MVP - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize components
    initFlashMessages();
    initVacancyButtons();
    initVacancyRefresh();
    initAdminSidebar();
});

/**
 * Auto-dismiss flash messages
 */
function initFlashMessages() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
}

/**
 * Vacancy status button handling
 */
function initVacancyButtons() {
    const vacancyButtons = document.querySelectorAll('.vacancy-btn');
    
    vacancyButtons.forEach(button => {
        button.addEventListener('click', function() {
            const status = this.dataset.status;
            const form = document.getElementById('vacancy-form');
            const input = document.getElementById('vacancy-status-input');
            
            if (form && input) {
                input.value = status;
                
                // Visual feedback
                vacancyButtons.forEach(btn => btn.classList.remove('active'));
                this.classList.add('active');
                
                // Submit form
                form.submit();
            }
        });
    });
}

/**
 * Auto-refresh vacancy status on public pages
 */
function initVacancyRefresh() {
    const shopCards = document.querySelectorAll('[data-shop-id]');
    
    if (shopCards.length === 0) return;
    
    // Refresh every 30 seconds
    setInterval(() => {
        shopCards.forEach(card => {
            const shopId = card.dataset.shopId;
            refreshVacancy(shopId, card);
        });
    }, 30000);
}

/**
 * Refresh vacancy status for a shop
 */
async function refreshVacancy(shopId, element) {
    try {
        const response = await fetch(`/api/vacancy/${shopId}`);
        if (!response.ok) return;
        
        const data = await response.json();
        
        const badge = element.querySelector('.vacancy-badge');
        if (badge) {
            badge.textContent = data.label;
            badge.className = `vacancy-badge vacancy-${data.color}`;
        }
    } catch (error) {
        console.error('Failed to refresh vacancy:', error);
    }
}

/**
 * Update vacancy via API (for AJAX updates)
 */
async function updateVacancy(shopId, status) {
    try {
        const response = await fetch(`/api/vacancy/${shopId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({ status })
        });
        
        if (!response.ok) {
            throw new Error('Update failed');
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Failed to update vacancy:', error);
        throw error;
    }
}

/**
 * Get CSRF token from meta tag or cookie
 */
function getCSRFToken() {
    // Try meta tag first
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.content;
    
    // Try cookie
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrf_token') return value;
    }
    
    return '';
}

/**
 * Format time ago
 */
function timeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    if (seconds < 60) return `${seconds}秒前`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}分前`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}時間前`;
    return `${Math.floor(seconds / 86400)}日前`;
}

/**
 * Initialize phone booking button
 */
function initPhoneBooking() {
    const phoneBtn = document.querySelector('.phone-btn');
    
    if (!phoneBtn) return;
    
    phoneBtn.addEventListener('click', function(e) {
        const shopId = this.dataset.shopId;
        const shopPhone = this.dataset.phone;
        
        // If direct phone call is available
        if (shopPhone && !this.dataset.twilioEnabled) {
            window.location.href = `tel:${shopPhone}`;
            return;
        }
        
        // Twilio automated call flow
        if (this.dataset.twilioEnabled === 'true') {
            e.preventDefault();
            initiateCall(shopId);
        }
    });
}

/**
 * Initiate Twilio call (placeholder for future implementation)
 */
async function initiateCall(shopId) {
    // This would trigger the Twilio call flow
    // For MVP, we might just show a confirmation modal
    alert('電話予約機能は準備中です。直接店舗にお電話ください。');
}
/**
 * Admin Sidebar Toggle for Mobile
 */
function initAdminSidebar() {
    const showBtn = document.getElementById('showSidebar');
    const hideBtn = document.getElementById('hideSidebar');
    const sidebar = document.getElementById('adminSidebar');
    const overlay = document.getElementById('adminSidebarOverlay');
    
    // Check if we are on an admin page with a sidebar
    if (!sidebar || !overlay) {
        // Automatically inject mobile header if admin layout exists
        const adminContent = document.querySelector('.admin-content');
        if (adminContent && !document.querySelector('.admin-mobile-header')) {
            const mobileHeader = document.createElement('div');
            mobileHeader.className = 'admin-mobile-header';
            mobileHeader.innerHTML = `
                <button class="sidebar-toggle-btn" id="showSidebar">☰</button>
                <span style="font-weight: 700; color: var(--color-primary);">MENU</span>
            `;
            adminContent.prepend(mobileHeader);
            
            // Re-call init after injection
            setTimeout(initAdminSidebar, 0);
        }
        return;
    }
    
    if (showBtn) {
        showBtn.addEventListener('click', () => {
            sidebar.classList.add('active');
            overlay.classList.add('active');
            document.body.style.overflow = 'hidden'; // Prevent scroll
        });
    }
    
    if (hideBtn) {
        hideBtn.addEventListener('click', () => {
            sidebar.classList.remove('active');
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        });
    }
    
    if (overlay) {
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('active');
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        });
    }
}
