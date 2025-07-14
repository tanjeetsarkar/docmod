/**
 * Pivot Table JavaScript Implementation
 * Pure JavaScript pivot table functionality with drag-and-drop zones
 */

class PivotTable {
    constructor(data) {
        this.data = data;
        this.availableColumns = [];
        this.columnDrop = [];
        this.rowsDrop = [];
        this.filterDrop = [];
        this.valuesDrop = [];
        this.aggregateFunction = 'sum'; // default aggregate function
        
        // Extract column names from data
        if (data && data.length > 0) {
            this.availableColumns = Object.keys(data[0]);
        }
    }

    // Set drop zone contents
    setColumnDrop(columns) {
        this.columnDrop = Array.isArray(columns) ? columns : [columns];
    }

    setRowsDrop(rows) {
        this.rowsDrop = Array.isArray(rows) ? rows : [rows];
    }

    setFilterDrop(filters) {
        this.filterDrop = Array.isArray(filters) ? filters : [filters];
    }

    setValuesDrop(values) {
        this.valuesDrop = Array.isArray(values) ? values : [values];
    }

    setAggregateFunction(func) {
        this.aggregateFunction = func;
    }

    // Apply filters to data
    applyFilters(data, filters) {
        if (!filters || filters.length === 0) return data;
        
        return data.filter(row => {
            return filters.every(filter => {
                const { column, operator, value } = filter;
                const cellValue = row[column];
                
                switch (operator) {
                    case 'equals':
                        return cellValue == value;
                    case 'not_equals':
                        return cellValue != value;
                    case 'greater_than':
                        return parseFloat(cellValue) > parseFloat(value);
                    case 'less_than':
                        return parseFloat(cellValue) < parseFloat(value);
                    case 'contains':
                        return String(cellValue).toLowerCase().includes(String(value).toLowerCase());
                    default:
                        return true;
                }
            });
        });
    }

    // Aggregate functions
    aggregateFunctions = {
        sum: (values) => values.reduce((acc, val) => acc + (parseFloat(val) || 0), 0),
        avg: (values) => {
            const sum = values.reduce((acc, val) => acc + (parseFloat(val) || 0), 0);
            return sum / values.length;
        },
        count: (values) => values.length,
        min: (values) => Math.min(...values.map(v => parseFloat(v) || 0)),
        max: (values) => Math.max(...values.map(v => parseFloat(v) || 0)),
        first: (values) => values[0],
        last: (values) => values[values.length - 1]
    };

    // Create pivot table
    createPivot(filterConditions = []) {
        // Apply filters first
        let filteredData = this.applyFilters(this.data, filterConditions);

        // If no rows or columns specified, return empty result
        if (this.rowsDrop.length === 0 && this.columnDrop.length === 0) {
            return { headers: [], data: [] };
        }

        // Group data by row and column combinations
        const grouped = this.groupData(filteredData);
        
        // Generate pivot table structure
        return this.generatePivotTable(grouped);
    }

    // Group data by row and column combinations
    groupData(data) {
        const groups = {};

        data.forEach(row => {
            // Create row key
            const rowKey = this.rowsDrop.length > 0 
                ? this.rowsDrop.map(col => row[col]).join('|') 
                : 'Total';

            // Create column key
            const colKey = this.columnDrop.length > 0 
                ? this.columnDrop.map(col => row[col]).join('|') 
                : 'Total';

            // Initialize group if it doesn't exist
            if (!groups[rowKey]) {
                groups[rowKey] = {};
            }
            if (!groups[rowKey][colKey]) {
                groups[rowKey][colKey] = [];
            }

            // Add row to appropriate group
            groups[rowKey][colKey].push(row);
        });

        return groups;
    }

    // Generate the final pivot table structure
    generatePivotTable(grouped) {
        // Get all unique row keys and column keys
        const rowKeys = Object.keys(grouped);
        const columnKeys = new Set();
        
        Object.values(grouped).forEach(rowGroup => {
            Object.keys(rowGroup).forEach(colKey => {
                columnKeys.add(colKey);
            });
        });

        const sortedColumnKeys = Array.from(columnKeys).sort();

        // Create headers
        const headers = [...this.rowsDrop];
        
        // Add column headers for each value field
        this.valuesDrop.forEach(valueField => {
            sortedColumnKeys.forEach(colKey => {
                headers.push(`${valueField}_${colKey}`);
            });
        });

        // Create data rows
        const data = rowKeys.map(rowKey => {
            const row = {};
            
            // Add row dimension values
            if (this.rowsDrop.length > 0) {
                const rowValues = rowKey.split('|');
                this.rowsDrop.forEach((col, index) => {
                    row[col] = rowValues[index];
                });
            }

            // Add aggregated values for each column
            this.valuesDrop.forEach(valueField => {
                sortedColumnKeys.forEach(colKey => {
                    const cellData = grouped[rowKey] && grouped[rowKey][colKey] 
                        ? grouped[rowKey][colKey] 
                        : [];
                    
                    const values = cellData.map(item => item[valueField]).filter(v => v !== undefined && v !== null);
                    const aggregateFunc = this.aggregateFunctions[this.aggregateFunction];
                    
                    row[`${valueField}_${colKey}`] = values.length > 0 
                        ? aggregateFunc(values) 
                        : 0;
                });
            });

            return row;
        });

        return {
            headers,
            data,
            rowKeys,
            columnKeys: sortedColumnKeys
        };
    }

    // Helper method to convert pivot result to array of arrays format
    toArrayOfArrays(pivotResult) {
        const { headers, data } = pivotResult;
        const result = [headers];
        
        data.forEach(row => {
            const rowArray = headers.map(header => row[header] || '');
            result.push(rowArray);
        });

        return result;
    }

    // Helper method to get unique values for a column (useful for filters)
    getUniqueValues(column) {
        const values = new Set();
        this.data.forEach(row => {
            if (row[column] !== undefined && row[column] !== null) {
                values.add(row[column]);
            }
        });
        return Array.from(values).sort();
    }

    // Helper method to validate drop zones
    validateDropZones() {
        const errors = [];
        
        if (this.valuesDrop.length === 0) {
            errors.push('At least one value field is required');
        }

        if (this.rowsDrop.length === 0 && this.columnDrop.length === 0) {
            errors.push('At least one row or column field is required');
        }

        // Check if all dropped fields exist in data
        const allDropped = [...this.rowsDrop, ...this.columnDrop, ...this.valuesDrop];
        allDropped.forEach(field => {
            if (!this.availableColumns.includes(field)) {
                errors.push(`Field '${field}' does not exist in data`);
            }
        });

        return errors;
    }
}

// Example usage:
/*
// Sample data
const sampleData = [
    { region: 'North', product: 'A', sales: 100, quantity: 10 },
    { region: 'North', product: 'B', sales: 200, quantity: 20 },
    { region: 'South', product: 'A', sales: 150, quantity: 15 },
    { region: 'South', product: 'B', sales: 250, quantity: 25 },
    { region: 'East', product: 'A', sales: 120, quantity: 12 },
    { region: 'East', product: 'B', sales: 180, quantity: 18 }
];

// Create pivot table instance
const pivot = new PivotTable(sampleData);

// Configure drop zones
pivot.setRowsDrop(['region']);
pivot.setColumnDrop(['product']);
pivot.setValuesDrop(['sales', 'quantity']);
pivot.setAggregateFunction('sum');

// Create pivot table
const result = pivot.createPivot();
console.log('Pivot Result:', result);

// Convert to array of arrays format
const arrayFormat = pivot.toArrayOfArrays(result);
console.log('Array Format:', arrayFormat);

// Example with filters
const filterConditions = [
    { column: 'region', operator: 'not_equals', value: 'East' }
];
const filteredResult = pivot.createPivot(filterConditions);
console.log('Filtered Result:', filteredResult);
*/