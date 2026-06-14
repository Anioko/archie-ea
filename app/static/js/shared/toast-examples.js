/**
 * Toast Notification System - Usage Examples
 *
 * This file demonstrates how to use the toast notification system
 * throughout the Flask-Shadcn platform.
 */

// ============================================================================
// BASIC USAGE
// ============================================================================

// Success notification
toast.success('Operation completed successfully!');

// Error notification (longer duration by default)
toast.error('Failed to save data');

// Warning notification
toast.warning('This action cannot be undone');

// Info notification
toast.info('Processing your request...');

// ============================================================================
// WITH DESCRIPTIONS
// ============================================================================

toast.success('Profile Updated', {
    description: 'Your profile information has been saved successfully.'
});

toast.error('Save Failed', {
    description: 'Unable to save changes. Please check your connection and try again.'
});

// ============================================================================
// WITH ACTION BUTTONS
// ============================================================================

toast.warning('Unsaved Changes', {
    description: 'You have unsaved changes that will be lost.',
    action: {
        label: 'Save Now',
        onClick: () => {
            saveChanges();
        }
    }
});

toast.error('Upload Failed', {
    description: 'The file could not be uploaded.',
    action: {
        label: 'Retry',
        onClick: () => {
            retryUpload();
        }
    }
});

// ============================================================================
// LOADING STATES
// ============================================================================

// Show loading toast (doesn't auto-dismiss)
const loadingToastId = toast.loading('Uploading file...');

// Later, dismiss it and show success
setTimeout(() => {
    toast.dismiss(loadingToastId);
    toast.success('File uploaded successfully!');
}, 3000);

// ============================================================================
// PROMISE-BASED OPERATIONS
// ============================================================================

// Automatically handles loading, success, and error states
toast.promise(
    fetch('/api/users', { method: 'POST' }),
    {
        loading: 'Saving data...',
        success: 'Data saved successfully!',
        error: 'Failed to save data'
    }
);

// With dynamic messages based on result
toast.promise(
    fetchUserData(userId),
    {
        loading: 'Loading user data...',
        success: (data) => `Loaded ${data.name}'s profile`,
        error: (err) => `Failed to load user: ${err.message}`
    }
);

// ============================================================================
// CUSTOM DURATIONS
// ============================================================================

// Show for 10 seconds
toast.info('Important message', { duration: 10000 });

// Never auto-dismiss (user must close manually)
toast.warning('Critical alert', { duration: 0 });

// ============================================================================
// CUSTOM ICONS
// ============================================================================

toast.info('Custom notification', {
    icon: 'zap',  // Any Lucide icon name
    description: 'With a custom icon'
});

// ============================================================================
// REPLACING OLD alert() CALLS
// ============================================================================

// OLD:
// alert('Success!');
// NEW:
toast.success('Operation completed!');

// OLD:
// alert('Error: ' + error.message);
// NEW:
toast.error('Operation failed', {
    description: error.message
});

// OLD:
// if (confirm('Are you sure?')) { doAction(); }
// NEW:
toast.warning('Confirm Action', {
    description: 'Are you sure you want to continue?',
    action: {
        label: 'Confirm',
        onClick: () => doAction()
    },
    duration: 0  // Don't auto-dismiss
});

// ============================================================================
// INTEGRATION WITH FETCH API
// ============================================================================

async function saveData(data) {
    try {
        const response = await fetch('/api/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const error = await response.json();
            toast.error('Save Failed', {
                description: error.message || 'An error occurred'
            });
            return;
        }

        const result = await response.json();
        toast.success('Saved Successfully', {
            description: `${result.count} items saved`
        });

    } catch (error) {
        toast.error('Network Error', {
            description: 'Unable to connect to the server. Please check your connection.'
        });
    }
}

// ============================================================================
// INTEGRATION WITH FLASK FLASH MESSAGES
// ============================================================================

// Flash messages are automatically converted to toasts via the toast-container.html component
// In Flask:
// flash('Operation successful', 'success')
// flash('An error occurred', 'error')
// flash('Please review', 'warning')
// flash('FYI: Something happened', 'info')

// ============================================================================
// HELPER FUNCTION FOR FORM VALIDATION
// ============================================================================

function validateForm(formData) {
    const errors = [];

    if (!formData.name) {
        errors.push('Name is required');
    }

    if (!formData.email) {
        errors.push('Email is required');
    } else if (!isValidEmail(formData.email)) {
        errors.push('Email is invalid');
    }

    if (errors.length > 0) {
        toast.error('Validation Failed', {
            description: errors.join('. ')
        });
        return false;
    }

    return true;
}

// ============================================================================
// DISMISSING TOASTS
// ============================================================================

// Dismiss a specific toast
const toastId = toast.info('Message');
toast.dismiss(toastId);

// Dismiss all toasts
toast.dismissAll();

// ============================================================================
// ADVANCED: STACKING BEHAVIOR
// ============================================================================

// Toasts automatically stack with a maximum of 5 visible at once
// Oldest toast is auto-dismissed when new ones arrive
toast.success('Message 1');
toast.success('Message 2');
toast.success('Message 3');
// ... up to 5 toasts will be visible

// ============================================================================
// ACCESSIBILITY
// ============================================================================

// All toasts have proper ARIA attributes:
// - role="alert"
// - aria-live="assertive"
// - Keyboard accessible close buttons
// - Screen reader friendly

// ============================================================================
// MOBILE RESPONSIVE
// ============================================================================

// On mobile devices (< 640px):
// - Toasts appear at bottom of screen
// - Slide up instead of slide from right
// - Full width for better readability
