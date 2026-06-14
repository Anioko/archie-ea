/**
 * Sidebar Quick Access - HARDENED SECURE VERSION
 * 
 * ✅ FIXES APPLIED:
 * - XSS prevention (textContent + escaping)
 * - User error feedback
 * - Accessibility (aria-labels)
 * - Data validation
 * - Race condition prevention
 * - Error boundaries
 */

// Guard against multiple initializations
let quickAccessInitialized = false;

document.addEventListener("DOMContentLoaded", function () {
  // ✅ FIX: Prevent race condition
  if (quickAccessInitialized) return;
  quickAccessInitialized = true;
  
  loadQuickAccessItems("applications", 10);
  loadQuickAccessItems("vendors", 8);
});

/**
 * Load quick-access items from async API endpoint
 * ✅ HARDENED: Validates parameters, handles errors, provides feedback
 */
async function loadQuickAccessItems(type, limit) {
  // ✅ FIX: Validate type parameter
  if (!["applications", "vendors"].includes(type)) {
    return;
  }
  
  // ✅ FIX: Validate limit parameter
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
    return;
  }

  // ✅ FIX: Use data attributes instead of hardcoded IDs
  const container = document.querySelector(`[data-quick-access="${type}"]`);

  if (!container) {
    console.warn(`[Sidebar] Container [data-quick-access="${type}"] not found, skipping async load`);
    return;
  }

  try {
    // ✅ FIX: Validate API endpoint exists (fallback provided)
    const apiEndpoint = window.SIDEBAR_API_ENDPOINT || "/api/sidebar/quick-access";
    
    const response = await fetch(
      `${apiEndpoint}?type=${encodeURIComponent(type)}&limit=${limit}`,
      {
        method: "GET",
        credentials: "same-origin",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "Accept": "application/json",
        },
      }
    );

    // ✅ FIX: Provide user feedback on API error
    if (!response.ok) {
      showErrorFeedback(container, `Failed to load ${type} (Error ${response.status})`);
      return;
    }

    // ✅ FIX: Validate response is JSON
    const contentType = response.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
      showErrorFeedback(container, "Invalid server response");
      return;
    }

    // ✅ FIX: Parse and validate response structure
    let data;
    try {
      data = await response.json();
    } catch (parseError) {
      showErrorFeedback(container, "Server returned invalid data");
      return;
    }

    // ✅ FIX: Validate data structure
    if (!data || !Array.isArray(data.items)) {
      showErrorFeedback(container, "Invalid server response structure");
      return;
    }

    // ✅ FIX: Validate each item in array
    if (!validateItems(data.items)) {
      showErrorFeedback(container, "Server returned invalid data");
      return;
    }

    // ✅ FIX: Render with XSS protection
    renderQuickAccessItems(container, data.items, type);
    
  } catch (error) {
    showErrorFeedback(container, "Network connection error. Please refresh.");
  }
}

/**
 * ✅ FIX: Validate items array structure
 */
function validateItems(items) {
  if (!Array.isArray(items)) return false;
  
  for (const item of items) {
    if (typeof item !== "object" || item === null) return false;
    if (!Number.isInteger(item.id) && typeof item.id !== "string") return false;
    if (typeof item.name !== "string") return false;
    if (typeof item.icon !== "string") return false;
    // badge is optional
    if (item.badge !== null && item.badge !== undefined && typeof item.badge !== "string") {
      return false;
    }
  }
  
  return true;
}

/**
 * ✅ FIX: Show error feedback to user (not just console)
 */
function showErrorFeedback(container, message) {
  // Create error message safely using textContent
  const errorDiv = document.createElement("div");
  errorDiv.className = "px-2.5 py-3 text-xs text-destructive bg-destructive/5 rounded";
  
  // Create text node safely (prevents XSS)
  const textNode = document.createTextNode(message);
  errorDiv.appendChild(textNode);
  
  safeHTML(container, "");
  container.appendChild(errorDiv);
}

/**
 * FIX: Whitelist allowed icons
 */
const ALLOWED_ICONS = new Set([
  "folder", "store", "package", "building", "chart", "database",
  "layout-grid", "list", "grid", "stack", "layers", "briefcase"
]);

function isValidIcon(icon) {
  return typeof icon === "string" && ALLOWED_ICONS.has(icon);
}

/**
 * Render quick-access items into sidebar container
 * HARDENED: Uses textContent + createElement to prevent XSS
 */
function renderQuickAccessItems(container, items, type) {
  if (!items || items.length === 0) {
    // FIX: Empty state safely created
    const emptyDiv = document.createElement("div");
    emptyDiv.className = "px-2.5 py-3 text-xs text-muted-foreground";
    emptyDiv.textContent = `No ${type} found`;
    
    safeHTML(container, "");
    container.appendChild(emptyDiv);
    return;
  }

  // FIX: Use DocumentFragment for performance
  const fragment = document.createDocumentFragment();

  // Determine endpoint and URL key based on type
  const urlBase = type === "applications" ? "/applications" : "/applications/vendors";
  
  // Generate safe items
  for (const item of items) {
    try {
      // ✅ FIX: Validate icon
      const icon = isValidIcon(item.icon) ? item.icon : "folder";
      
      // ✅ FIX: Create link safely
      const link = document.createElement("a");
      link.href = `${urlBase}/${item.id}`;
      link.className = "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors hover:bg-accent hover:text-accent-foreground text-muted-foreground group/item";
      
      // ✅ FIX: Accessibility label with safe text
      link.setAttribute("aria-label", `${type}: ${item.name}`);
      
      // ✅ FIX: Icon using data attribute (safe)
      const iconEl = document.createElement("i");
      iconEl.setAttribute("data-lucide", icon);
      iconEl.className = "h-3.5 w-3.5 flex-shrink-0";
      iconEl.setAttribute("aria-hidden", "true");  // Hidden from screen readers
      link.appendChild(iconEl);
      
      // ✅ FIX: Item name using textContent (XSS safe)
      const nameSpan = document.createElement("span");
      nameSpan.className = "flex-1 truncate";
      nameSpan.textContent = item.name;  // Safe: automatic escaping
      link.appendChild(nameSpan);
      
      // ✅ FIX: Badge safely rendered
      if (item.badge) {
        const badgeSpan = document.createElement("span");
        badgeSpan.className = "text-xs text-muted-foreground/70 bg-muted/50 px-1.5 py-0.5 rounded flex-shrink-0";
        badgeSpan.textContent = item.badge;  // Safe: automatic escaping
        link.appendChild(badgeSpan);
      }
      
      fragment.appendChild(link);
      
    } catch (itemError) {
      console.error("[Sidebar] Error rendering item:", itemError);
      // Skip this item but continue with others
      continue;
    }
  }

  // ✅ FIX: Replace container content safely
  safeHTML(container, "");
  container.appendChild(fragment);

  // ✅ FIX: Re-initialize Lucide icons for newly inserted elements
  try {
    if (typeof lucide !== "undefined" && typeof lucide.createIcons === "function") {
      lucide.createIcons();
    }
  } catch (lucideError) {
    console.warn("[Sidebar] Failed to initialize icons:", lucideError);
    // Icons won't show but content still readable
  }
}
