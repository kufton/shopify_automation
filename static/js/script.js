// Custom JavaScript for Product Manager

document.addEventListener('DOMContentLoaded', function() {
    // Implement lazy loading for images
    const lazyImages = document.querySelectorAll('img[loading="lazy"]');
    
    // Add lazy-load class to all lazy-loaded images
    lazyImages.forEach(function(img) {
        img.classList.add('lazy-load');
        
        // When image loads, add the loaded class for the fade-in effect
        img.addEventListener('load', function() {
            this.classList.add('loaded');
        });
    });
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Toggle all checkboxes in product list
    const selectAllCheckbox = document.getElementById('select-all-products');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const checkboxes = document.querySelectorAll('.product-checkbox');
            checkboxes.forEach(function(checkbox) {
                checkbox.checked = selectAllCheckbox.checked;
            });
        });
    }

    // Update tag selection in collection form
    const tagSelectors = document.querySelectorAll('.tag-selector');
    if (tagSelectors.length > 0) {
        tagSelectors.forEach(function(selector) {
            selector.addEventListener('click', function() {
                const tagId = this.getAttribute('data-tag-id');
                const tagName = this.getAttribute('data-tag-name');
                document.getElementById('tag_id').value = tagId;
                document.getElementById('selected-tag').textContent = tagName;
            });
        });
    }

    // Toggle password visibility for environment variables
    const toggleButtons = document.querySelectorAll('.toggle-password');
    if (toggleButtons.length > 0) {
        toggleButtons.forEach(function(button) {
            button.addEventListener('click', function() {
                const valueElement = document.getElementById(this.getAttribute('data-target'));
                const type = valueElement.getAttribute('type');
                
                if (type === 'password') {
                    valueElement.setAttribute('type', 'text');
                    this.innerHTML = '<i class="fas fa-eye-slash"></i>';
                } else {
                    valueElement.setAttribute('type', 'password');
                    this.innerHTML = '<i class="fas fa-eye"></i>';
                }
            });
        });
    }

    // Confirm deletion
    const deleteButtons = document.querySelectorAll('.delete-confirm');
    if (deleteButtons.length > 0) {
        deleteButtons.forEach(function(button) {
            button.addEventListener('click', function(e) {
                if (!confirm('Are you sure you want to delete this item? This action cannot be undone.')) {
                    e.preventDefault();
                }
            });
        });
    }

    // Filter products by tag
    const tagFilters = document.querySelectorAll('.tag-filter');
    if (tagFilters.length > 0) {
        tagFilters.forEach(function(filter) {
            filter.addEventListener('click', function(e) {
                e.preventDefault();
                const tagName = this.getAttribute('data-tag');
                const products = document.querySelectorAll('.product-card');
                
                if (tagName === 'all') {
                    products.forEach(function(product) {
                        product.style.display = 'block';
                    });
                } else {
                    products.forEach(function(product) {
                        const productTags = product.getAttribute('data-tags').split(',');
                        if (productTags.includes(tagName)) {
                            product.style.display = 'block';
                        } else {
                            product.style.display = 'none';
                        }
                    });
                }
                
                // Update active filter
                tagFilters.forEach(function(f) {
                    f.classList.remove('active');
                });
                this.classList.add('active');
            });
        });
    }

    // Copy environment variable value to clipboard
    const copyButtons = document.querySelectorAll('.copy-to-clipboard');
    if (copyButtons.length > 0) {
        copyButtons.forEach(function(button) {
            button.addEventListener('click', function() {
                const valueElement = document.getElementById(this.getAttribute('data-target'));
                const textArea = document.createElement('textarea');
                textArea.value = valueElement.textContent || valueElement.value;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                
                // Show copied tooltip
                const tooltip = document.createElement('div');
                tooltip.className = 'position-absolute bg-dark text-white p-1 rounded';
                tooltip.style.top = '-25px';
                tooltip.style.left = '0';
                tooltip.textContent = 'Copied!';
                this.style.position = 'relative';
                this.appendChild(tooltip);
                
                setTimeout(function() {
                    tooltip.remove();
                }, 1000);
            });
        });
    }
});
