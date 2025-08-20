# D2 Diagram Generation for FastAPI + React Applications

This guide provides Python and JavaScript scripts to automatically generate D2 diagrams for your FastAPI backend and React frontend applications.

## Features

### Backend (Python Script)
- **Technical Diagrams**: Detailed architecture showing modules, endpoints, services, databases
- **Stakeholder Diagrams**: Simplified business flow diagrams
- **Full System Diagrams**: Complete system architecture overview
- Analyzes FastAPI router, service, schema, and utility files
- Detects database calls, external services, and dependencies

### Frontend (JavaScript Script)
- **Technical Diagrams**: Component hierarchy, hooks usage, API integration
- **Stakeholder Diagrams**: User journey and business features
- **Component Flow Diagrams**: Individual component analysis
- Analyzes React components, pages, custom hooks, and routing

## Prerequisites

### Python Script Dependencies
```bash
pip install ast pathlib dataclasses
```

### JavaScript Script Dependencies
```bash
npm install @babel/parser @babel/traverse
# or
yarn add @babel/parser @babel/traverse
```

### D2 Installation
Install D2 for rendering diagrams:
```bash
# macOS
brew install d2

# Linux
curl -fsSL https://d2lang.com/install.sh | sh -

# Windows
# Download from https://github.com/terrastruct/d2/releases
```

## Setup

1. **Save the Python script** as `fastapi_d2_generator.py`
2. **Save the JavaScript script** as `react_d2_generator.js`
3. **Make scripts executable**:
   ```bash
   chmod +x fastapi_d2_generator.py
   chmod +x react_d2_generator.js
   ```

## Usage

### Backend Diagram Generation

#### Generate diagrams for all modules:
```bash
# Technical diagrams for all modules
python fastapi_d2_generator.py --backend-path ./backend --type technical

# Stakeholder diagrams for all modules  
python fastapi_d2_generator.py --backend-path ./backend --type stakeholder

# Full system architecture
python fastapi_d2_generator.py --backend-path ./backend --type full
```

#### Generate diagrams for specific module:
```bash
# Technical diagram for user module
python fastapi_d2_generator.py --backend-path ./backend --module users --type technical

# Stakeholder diagram for user module
python fastapi_d2_generator.py --backend-path ./backend --module users --type stakeholder
```

#### Custom output directory:
```bash
python fastapi_d2_generator.py --backend-path ./backend --output-dir ./docs/diagrams
```

### Frontend Diagram Generation

#### Generate application-wide diagrams:
```bash
# Technical architecture diagram
node react_d2_generator.js --frontend-path ./frontend --type technical

# Stakeholder flow diagram
node react_d2_generator.js --frontend-path ./frontend --type stakeholder

# Generate both types
node react_d2_generator.js --frontend-path ./frontend --type all
```

#### Generate component-specific diagram:
```bash
# Analyze specific component
node react_d2_generator.js --frontend-path ./frontend --component UserProfile

# With custom output directory
node react_d2_generator.js --frontend-path ./frontend --component UserDashboard --output-dir ./docs/diagrams
```

### Rendering D2 Diagrams

Convert `.d2` files to images:
```bash
# Generate SVG
d2 diagram.d2 diagram.svg

# Generate PNG
d2 diagram.d2 diagram.png

# Generate PDF
d2 diagram.d2 diagram.pdf

# Batch convert all diagrams
for file in *.d2; do
    d2 "$file" "${file%.d2}.svg"
done
```

## Expected Project Structure

### Backend Structure
```
backend/
├── module1/
│   ├── router.py
│   ├── service.py
│   ├── schema.py
│   ├── utils.py
│   └── store.py
├── module2/
│   ├── router.py
│   ├── service.py
│   └── schema.py
└── ...
```

### Frontend Structure
```
frontend/
├── src/
│   ├── components/
│   │   ├── UserProfile/
│   │   │   └── index.jsx
│   │   └── Dashboard/
│   │       └── index.jsx
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── Dashboard.jsx
│   │   └── Users.jsx
│   ├── hooks/
│   │   ├── useAuth.js
│   │   ├── useApi.js
│   │   └── useLocalStorage.js
│   ├── App.jsx
│   └── routes.jsx
```

## Diagram Types Generated

### Backend Diagrams

1. **Technical Diagrams** (`module_technical.d2`)
   - Module structure (router, service, schema, utils)
   - API endpoints with HTTP methods
   - Service functions and business logic
   - Database connections (PostgreSQL, Redis, BigQuery)
   - External service integrations (Celery)
   - Data flow between components

2. **Stakeholder Diagrams** (`module_stakeholder.d2`)
   - Simplified business operations
   - User journey flows
   - High-level feature groupings
   - Business process overview

3. **Full System Diagrams** (`full_system_architecture.d2`)
   - Complete system overview
   - All modules and their interactions
   - Data layer architecture
   - Background processing flows

### Frontend Diagrams

1. **Technical Diagrams** (`react_technical_architecture.d2`)
   - Component hierarchy and relationships
   - Custom hooks usage
   - API integration points
   - Routing structure
   - State management flows

2. **Stakeholder Diagrams** (`react_stakeholder_flow.d2`)
   - User journey mapping
   - Business feature categorization
   - Application workflow
   - User interaction flows

3. **Component Flow Diagrams** (`ComponentName_component_flow.d2`)
   - Individual component analysis
   - Props and state management
   - Hook dependencies
   - Child component relationships
   - API call patterns

## Customization

### Adding Custom Analysis

#### Backend (Python)
Extend the `FastAPIAnalyzer` class to add custom analysis:
```python
def analyze_custom_pattern(self, file_path):
    # Add your custom analysis logic
    pass
```

#### Frontend (JavaScript)
Extend the `ReactAnalyzer` class:
```javascript
async analyzeCustomPattern(filePath) {
    // Add your custom analysis logic
}
```

### Custom Diagram Styling

Modify the `colors` dictionary in the generator classes:
```python
# Python
self.colors = {
    'endpoint': '#your_color',
    'service': '#your_color', 
    # ... more colors
}
```

```javascript
// JavaScript
this.colors = {
    page: '#your_color',
    component: '#your_color',
    // ... more colors
};
```

## Advanced Usage

### Batch Processing
```bash
#!/bin/bash
# Generate all diagrams for multiple modules

modules=("users" "products" "orders" "analytics")
types=("technical" "stakeholder")

for module in "${modules[@]}"; do
    for type in "${types[@]}"; do
        python fastapi_d2_generator.py \
            --backend-path ./backend \
            --module "$module" \
            --type "$type" \
            --output-dir "./docs/diagrams/$module"
        
        # Convert to SVG
        d2 "./docs/diagrams/$module/${module}_${type}.d2" \
           "./docs/diagrams/$module/${module}_${type}.svg"
    done
done

# Generate frontend diagrams
node react_d2_generator.js \
    --frontend-path ./frontend \
    --type all \
    --output-dir ./docs/diagrams/frontend

# Convert frontend diagrams
cd ./docs/diagrams/frontend
for file in *.d2; do
    d2 "$file" "${file%.d2}.svg"
done
```

### Integration with CI/CD
```yaml
# .github/workflows/generate-diagrams.yml
name: Generate Architecture Diagrams

on:
  push:
    branches: [main]
    paths: ['backend/**', 'frontend/**']

jobs:
  generate-diagrams:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
          
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          
      - name: Install D2
        run: curl -fsSL https://d2lang.com/install.sh | sh -
        
      - name: Install dependencies
        run: |
          npm install @babel/parser @babel/traverse
          
      - name: Generate backend diagrams
        run: |
          python fastapi_d2_generator.py \
            --backend-path ./backend \
            --type full \
            --output-dir ./docs/diagrams
            
      - name: Generate frontend diagrams
        run: |
          node react_d2_generator.js \
            --frontend-path ./frontend \
            --type all \
            --output-dir ./docs/diagrams
            
      - name: Convert to images
        run: |
          cd ./docs/diagrams
          for file in *.d2; do
            d2 "$file" "${file%.d2}.svg"
          done
          
      - name: Commit diagrams
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add docs/diagrams/
          git diff --staged --quiet || git commit -m "Update architecture diagrams"
          git push
```

## Troubleshooting

### Common Issues

1. **Module not found errors**
   ```bash
   # Ensure correct path structure
   ls -la backend/  # Should show module directories
   ls -la frontend/src/  # Should show components, pages, hooks
   ```

2. **Parsing errors in React files**
   ```bash
   # Install missing Babel plugins
   npm install @babel/plugin-syntax-jsx @babel/plugin-syntax-typescript
   ```

3. **Permission denied when executing scripts**
   ```bash
   chmod +x fastapi_d2_generator.py
   chmod +x react_d2_generator.js
   ```

4. **D2 command not found**
   ```bash
   # Verify D2 installation
   which d2
   d2 --version
   
   # Reinstall if necessary
   curl -fsSL https://d2lang.com/install.sh | sh -
   ```

### Debug Mode

Add debug logging to scripts:

#### Python Debug
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Add to analyzer methods
logging.debug(f"Analyzing file: {file_path}")
logging.debug(f"Found endpoints: {len(endpoints)}")
```

#### JavaScript Debug
```javascript
// Add debug flag
const DEBUG = process.env.DEBUG === 'true';

function debugLog(message, data = null) {
  if (DEBUG) {
    console.log(`[DEBUG] ${message}`, data || '');
  }
}

// Usage
debugLog('Analyzing component', componentPath);
```

### Performance Optimization

For large applications:

1. **Selective Analysis**
   ```bash
   # Analyze only specific modules
   python fastapi_d2_generator.py --backend-path ./backend --module users
   
   # Analyze only specific components
   node react_d2_generator.js --frontend-path ./frontend --component UserDashboard
   ```

2. **Parallel Processing**
   ```python
   # Python: Use multiprocessing for large codebases
   from multiprocessing import Pool
   
   def analyze_module_parallel(module_path):
       return analyzer.analyze_module(module_path)
   
   with Pool() as pool:
       results = pool.map(analyze_module_parallel, module_paths)
   ```

## Integration Examples

### Documentation Generation

Create a comprehensive documentation generator:

```python
#!/usr/bin/env python3
"""
Documentation Generator with D2 Diagrams
"""

import os
from pathlib import Path
import subprocess

def generate_full_documentation(backend_path, frontend_path, output_path):
    """Generate complete project documentation with diagrams"""
    
    docs_path = Path(output_path)
    diagrams_path = docs_path / "diagrams"
    
    # Create directories
    docs_path.mkdir(exist_ok=True)
    diagrams_path.mkdir(exist_ok=True)
    
    # Generate backend diagrams
    print("Generating backend diagrams...")
    subprocess.run([
        "python", "fastapi_d2_generator.py",
        "--backend-path", backend_path,
        "--type", "full",
        "--output-dir", str(diagrams_path)
    ])
    
    # Generate frontend diagrams
    print("Generating frontend diagrams...")
    subprocess.run([
        "node", "react_d2_generator.js",
        "--frontend-path", frontend_path,
        "--type", "all",
        "--output-dir", str(diagrams_path)
    ])
    
    # Convert diagrams to images
    print("Converting diagrams to images...")
    for d2_file in diagrams_path.glob("*.d2"):
        svg_file = d2_file.with_suffix(".svg")
        subprocess.run(["d2", str(d2_file), str(svg_file)])
    
    # Generate markdown documentation
    generate_markdown_docs(docs_path, diagrams_path)

def generate_markdown_docs(docs_path, diagrams_path):
    """Generate markdown documentation with embedded diagrams"""
    
    readme_content = f"""# Project Architecture Documentation

## System Overview

![Full System Architecture](diagrams/full_system_architecture.svg)

## Backend Architecture

### Technical Architecture
![Backend Technical](diagrams/backend_technical_architecture.svg)

### Business Flow
![Backend Stakeholder](diagrams/backend_stakeholder_flow.svg)

## Frontend Architecture

### Technical Architecture
![Frontend Technical](diagrams/react_technical_architecture.svg)

### User Journey
![Frontend Stakeholder](diagrams/react_stakeholder_flow.svg)

## Module Diagrams

"""
    
    # Add module-specific diagrams
    for svg_file in diagrams_path.glob("*_technical.svg"):
        module_name = svg_file.stem.replace("_technical", "")
        readme_content += f"""
### {module_name.title()} Module
![{module_name} Technical](diagrams/{svg_file.name})
![{module_name} Business Flow](diagrams/{module_name}_stakeholder.svg)
"""
    
    # Write documentation
    with open(docs_path / "README.md", "w") as f:
        f.write(readme_content)
    
    print(f"Documentation generated at {docs_path}/README.md")

if __name__ == "__main__":
    generate_full_documentation(
        backend_path="./backend",
        frontend_path="./frontend", 
        output_path="./docs"
    )
```

### Pre-commit Hook

Automatically update diagrams on code changes:

```bash
#!/bin/sh
# .git/hooks/pre-commit

# Check if backend files changed
if git diff --cached --name-only | grep -q "backend/"; then
    echo "Backend files changed, updating diagrams..."
    python fastapi_d2_generator.py --backend-path ./backend --type full --output-dir ./docs/diagrams
fi

# Check if frontend files changed  
if git diff --cached --name-only | grep -q "frontend/"; then
    echo "Frontend files changed, updating diagrams..."
    node react_d2_generator.js --frontend-path ./frontend --type all --output-dir ./docs/diagrams
fi

# Convert updated diagrams
cd ./docs/diagrams
for file in *.d2; do
    if [ "$file" -nt "${file%.d2}.svg" ]; then
        d2 "$file" "${file%.d2}.svg"
        git add "${file%.d2}.svg"
    fi
done

exit 0
```

## Advanced Features

### Custom Themes

Create custom D2 themes for your organization:

```d2
# themes/company-theme.d2
vars: {
  primary-color: #1E3A8A
  secondary-color: #3B82F6  
  accent-color: #10B981
  neutral-color: #6B7280
  danger-color: #EF4444
}

# Apply theme to specific elements
*.style.fill: ${primary-color}
*.components.*.style.fill: ${secondary-color}
*.api.*.style.fill: ${accent-color}
*.database.*.style.fill: ${neutral-color}
```

Use theme in generated diagrams:
```python
def apply_theme(d2_content, theme_path):
    """Apply custom theme to D2 diagram"""
    with open(theme_path, 'r') as f:
        theme_content = f.read()
    
    return theme_content + "\n\n" + d2_content
```

### Interactive Diagrams

Generate interactive HTML diagrams:

```bash
# Generate interactive SVG with D2
d2 --theme=200 --sketch diagram.d2 diagram.svg

# Or use D2's built-in server mode
d2 --watch diagram.d2 --port 8080
```

### Automated Diagram Validation

Validate diagram consistency:

```python
def validate_diagrams(backend_path, frontend_path, diagrams_path):
    """Validate that diagrams are up-to-date with code"""
    
    # Check if source files are newer than diagrams
    backend_modified = get_latest_modification_time(backend_path)
    frontend_modified = get_latest_modification_time(frontend_path)
    
    for diagram_file in Path(diagrams_path).glob("*.d2"):
        diagram_modified = diagram_file.stat().st_mtime
        
        if backend_modified > diagram_modified or frontend_modified > diagram_modified:
            print(f"Warning: {diagram_file.name} may be out of date")
            return False
    
    return True

def get_latest_modification_time(directory):
    """Get the latest modification time of files in directory"""
    latest = 0
    for file_path in Path(directory).rglob("*.py"):
        latest = max(latest, file_path.stat().st_mtime)
    return latest
```

## Best Practices

### 1. Diagram Organization
```
docs/
├── diagrams/
│   ├── system/
│   │   ├── full_architecture.d2
│   │   └── data_flow.d2
│   ├── backend/
│   │   ├── modules/
│   │   │   ├── users_technical.d2
│   │   │   ├── users_stakeholder.d2
│   │   │   └── products_technical.d2
│   │   └── services/
│   │       ├── auth_service.d2
│   │       └── payment_service.d2
│   └── frontend/
│       ├── components/
│       ├── pages/
│       └── flows/
└── images/
    └── diagrams/  # Generated SVG/PNG files
```

### 2. Naming Conventions
- Technical diagrams: `{module}_technical.d2`
- Stakeholder diagrams: `{module}_stakeholder.d2`
- Component flows: `{component}_flow.d2`
- System overviews: `{system}_architecture.d2`

### 3. Version Control
```gitignore
# .gitignore
*.d2~  # D2 backup files
diagrams/*.svg  # Generated images (optional)
diagrams/*.png
diagrams/*.pdf
```

Keep `.d2` files in version control, optionally exclude generated images.

### 4. Documentation Integration
- Embed diagrams in README files
- Link to interactive versions
- Include generation timestamps
- Provide context and explanations

### 5. Maintenance Schedule
```yaml
# .github/workflows/diagram-maintenance.yml
name: Weekly Diagram Update
on:
  schedule:
    - cron: '0 2 * * 1'  # Every Monday at 2 AM
  workflow_dispatch:

jobs:
  update-diagrams:
    runs-on: ubuntu-latest
    steps:
      - name: Generate fresh diagrams
        run: |
          # Full regeneration of all diagrams
          python fastapi_d2_generator.py --backend-path ./backend --type full
          node react_d2_generator.js --frontend-path ./frontend --type all
      
      - name: Check for changes
        run: |
          if git diff --quiet docs/diagrams/; then
            echo "No changes detected"
          else
            echo "Diagrams updated, creating PR"
            # Create PR with updated diagrams
          fi
```

## Conclusion

This comprehensive D2 diagram generation system provides:

- **Automated Analysis**: Intelligent parsing of FastAPI and React codebases
- **Multiple Perspectives**: Technical and stakeholder-focused diagrams
- **Scalable Architecture**: Works with large, complex applications  
- **Integration Ready**: CI/CD, documentation, and workflow integration
- **Customizable Output**: Themes, layouts, and styling options

The scripts automatically detect:
- API endpoints and HTTP methods
- Database interactions and external services
- Component hierarchies and data flows
- Business logic and user journeys
- Dependencies and relationships

This enables teams to maintain up-to-date architectural documentation with minimal manual effort, improving code understanding, onboarding, and stakeholder communication.