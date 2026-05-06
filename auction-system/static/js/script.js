document.addEventListener('DOMContentLoaded', function() {
    // Initialize countdown timers
    initCountdowns();
    
    // Initialize bid form validation
    initBidForm();
    
    // Initialize charts for admin dashboard
    if (document.getElementById('userChart')) {
        initAdminCharts();
    }
    
    // Auto-dismiss flash messages
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(function(alert) {
            const closeButton = alert.querySelector('.btn-close');
            if (closeButton) {
                closeButton.click();
            }
        });
    }, 5000);
});

// Initialize countdown timers
function initCountdowns() {
    const countdownElements = document.querySelectorAll('[data-end]');
    
    countdownElements.forEach(function(element) {
        updateCountdown(element);
        
        // Update every second
        setInterval(function() {
            updateCountdown(element);
        }, 1000);
    });
}

// Update countdown timer
function updateCountdown(element) {
    const endTime = new Date(element.dataset.end).getTime();
    const now = new Date().getTime();
    const distance = endTime - now;
    
    if (distance < 0) {
        element.innerHTML = 'Auction Ended';
        element.classList.add('text-danger');
        return;
    }
    
    // Calculate days, hours, minutes, seconds
    const days = Math.floor(distance / (1000 * 60 * 60 * 24));
    const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((distance % (1000 * 60)) / 1000);
    
    // Display countdown
    let countdownText = '';
    if (days > 0) {
        countdownText += `${days}d `;
    }
    
    countdownText += `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    element.innerHTML = countdownText;
}

// Bid form validation
function initBidForm() {
    const bidForm = document.querySelector('form[action*="bid"]');
    if (!bidForm) return;
    
    bidForm.addEventListener('submit', function(e) {
        const bidAmount = document.getElementById('bid_amount');
        const minBid = parseFloat(bidAmount.getAttribute('min'));
        
        if (parseFloat(bidAmount.value) < minBid) {
            e.preventDefault();
            alert(`Your bid must be at least ₹${minBid}`);
            return false;
        }
    });
}

// Admin dashboard charts
function initAdminCharts() {
    // User distribution chart
    new Chart(document.getElementById('userChart'), {
        type: 'pie',
        data: {
            labels: ['Admin', 'Regular Users'],
            datasets: [{
                data: [1, 2], // Sample data
                backgroundColor: ['#3498db', '#e74c3c']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: 'User Distribution'
                }
            }
        }
    });
    
    // Auction status chart
    new Chart(document.getElementById('auctionChart'), {
        type: 'bar',
        data: {
            labels: ['Open', 'Closed'],
            datasets: [{
                label: 'Auctions',
                data: [1, 0], // Sample data
                backgroundColor: ['#27ae60', '#95a5a6']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: 'Auction Status'
                }
            }
        }
    });
}
// Initialize shipping tracking display
function initShippingTracking() {
    const trackingProgress = document.querySelector('.shipping-progress');
    if (!trackingProgress) return;
    
    const status = trackingProgress.getAttribute('data-status');
    let width = 0;
    
    if (status === 'Processing') {
        width = 33;
    } else if (status === 'Shipped') {
        width = 66;
    } else if (status === 'Delivered') {
        width = 100;
    }
    
    trackingProgress.style.width = width + '%';
}

// Function to highlight active tab based on URL
function setActiveTab() {
    const currentPath = window.location.pathname;
    
    if (currentPath.includes('/payment/')) {
        document.getElementById('payments-tab').click();
    } else if (currentPath.includes('/shipping/')) {
        document.getElementById('shipping-tab').click();
    } else if (currentPath.includes('/won/')) {
        document.getElementById('won-tab').click();
    }
}

// Call functions on page load
document.addEventListener('DOMContentLoaded', function() {
    initShippingTracking();
    setActiveTab();
    
    // Add any other existing initialization functions here
    initCountdowns();
});
