/**
 * vendors/deployment_portfolio.js
 * Export functionality for the vendor deployment portfolio page.
 * Reads portfolio data from window.__PORTFOLIO_DATA__ set by the template.
 */

function exportPortfolio(format) {
    const portfolioData = window.__PORTFOLIO_DATA__;
    if (!portfolioData) {
        console.error('[deployment_portfolio] __PORTFOLIO_DATA__ not set');
        return;
    }

    const vendorName = (portfolioData.vendor?.name || 'vendor').replace(/\s+/g, '_');
    const dateStr = new Date().toISOString().slice(0, 10);

    if (format === 'json') {
        const dataStr = JSON.stringify(portfolioData, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(dataBlob);
        link.download = `${vendorName}_deployment_portfolio_${dateStr}.json`;
        link.click();

    } else if (format === 'csv') {
        let csvContent = 'Vendor Deployment Portfolio\n';
        csvContent += `Vendor: ${portfolioData.vendor.name}\n`;
        csvContent += `Generated: ${new Date().toISOString()}\n\n`;

        csvContent += 'Statistics\n';
        csvContent += 'Metric,Value\n';
        csvContent += `Total Applications,${portfolioData.statistics.total_applications}\n`;
        csvContent += `Products Deployed,${portfolioData.statistics.products_deployed}\n`;
        csvContent += `Total ArchiMate Elements,${portfolioData.statistics.total_archimate_elements}\n\n`;

        if (portfolioData.applications && portfolioData.applications.length > 0) {
            csvContent += 'Applications\n';
            csvContent += 'Name,Description,Status,Deployment Type,Criticality,Hosting Model,Business Owner,Product Name,ArchiMate Elements,Created At\n';
            portfolioData.applications.forEach(app => {
                const row = [
                    `"${app.name || ''}"`,
                    `"${(app.description || '').replace(/"/g, '""')}"`,
                    `"${app.deployment_status || ''}"`,
                    `"${app.deployment_type || ''}"`,
                    `"${app.criticality || ''}"`,
                    `"${app.hosting_model || ''}"`,
                    `"${app.business_owner || ''}"`,
                    `"${app.product_name || ''}"`,
                    `${app.archimate_elements_count || 0}`,
                    `"${app.created_at || ''}"`
                ];
                csvContent += row.join(',') + '\n';
            });
        }

        const dataBlob = new Blob([csvContent], { type: 'text/csv' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(dataBlob);
        link.download = `${vendorName}_deployment_portfolio_${dateStr}.csv`;
        link.click();
    }
}

window.exportPortfolio = exportPortfolio;
