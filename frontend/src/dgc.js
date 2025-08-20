#!/usr/bin/env node

/**
 * React D2 Diagram Generator
 * Generates technical and stakeholder diagrams for React frontend
 */

const fs = require('fs').promises;
const path = require('path');
const { parse } = require('@babel/parser');
const traverse = require('@babel/traverse').default;

class ReactAnalyzer {
  constructor(basePath) {
    this.basePath = basePath;
    this.components = new Map();
    this.pages = new Map();
    this.hooks = new Map();
    this.apiCalls = new Set();
    this.routes = [];
  }

  async analyzeComponent(filePath) {
    try {
      const content = await fs.readFile(filePath, 'utf-8');
      const ast = parse(content, {
        sourceType: 'module',
        plugins: ['jsx', 'typescript']
      });

      const componentInfo = {
        name: path.basename(filePath, path.extname(filePath)),
        imports: [],
        exports: [],
        hooks: [],
        apiCalls: [],
        childComponents: [],
        props: []
      };

      traverse(ast, {
        ImportDeclaration(path) {
          const source = path.node.source.value;
          const specifiers = path.node.specifiers.map(spec => {
            if (spec.type === 'ImportDefaultSpecifier') {
              return { name: spec.local.name, type: 'default', source };
            } else if (spec.type === 'ImportSpecifier') {
              return { name: spec.imported.name, type: 'named', source };
            }
            return { name: spec.local.name, type: 'namespace', source };
          });
          componentInfo.imports.push(...specifiers);
        },

        FunctionDeclaration(path) {
          if (this.isReactComponent(path.node.id.name)) {
            componentInfo.exports.push(path.node.id.name);
            this.extractPropsFromFunction(path.node, componentInfo);
          }
        },

        ArrowFunctionExpression(path) {
          if (path.parent.type === 'VariableDeclarator' && 
              this.isReactComponent(path.parent.id.name)) {
            componentInfo.exports.push(path.parent.id.name);
            this.extractPropsFromFunction(path.node, componentInfo);
          }
        },

        CallExpression(path) {
          const callee = path.node.callee;
          
          // Detect React hooks
          if (callee.name && callee.name.startsWith('use')) {
            componentInfo.hooks.push(callee.name);
          }
          
          // Detect API calls
          if (this.isApiCall(path.node)) {
            const apiCall = this.extractApiCall(path.node);
            if (apiCall) {
              componentInfo.apiCalls.push(apiCall);
              this.apiCalls.add(apiCall);
            }
          }
        },

        JSXElement(path) {
          // Extract child components
          if (path.node.openingElement.name.type === 'JSXIdentifier') {
            const componentName = path.node.openingElement.name.name;
            if (this.isCustomComponent(componentName)) {
              componentInfo.childComponents.push(componentName);
            }
          }
        }
      });

      return componentInfo;
    } catch (error) {
      console.error(`Error analyzing component ${filePath}:`, error.message);
      return null;
  }

  isSideEffect(node) {
    const callee = node.callee;
    const sideEffectHooks = ['useEffect', 'useLayoutEffect'];
    return callee.name && sideEffectHooks.includes(callee.name);
  }

  extractSideEffect(node) {
    return {
      hook: node.callee.name,
      dependencies: this.extractDependencyArray(node)
    };
  }

  extractDependencyArray(node) {
    if (node.arguments.length > 1) {
      const depsArg = node.arguments[1];
      if (depsArg.type === 'ArrayExpression') {
        return depsArg.elements.map(el => 
          el.type === 'Identifier' ? el.name : 'unknown'
        );
      }
    }
    return [];
  }

  extractReturnType(node) {
    if (node.type === 'ObjectExpression') {
      return 'object';
    } else if (node.type === 'ArrayExpression') {
      return 'array';
    } else if (node.type === 'Identifier') {
      return node.name;
    }
    return 'unknown';
  }

  extractPropsFromFunction(node, componentInfo) {
    if (node.params.length > 0) {
      const propsParam = node.params[0];
      if (propsParam.type === 'ObjectPattern') {
        componentInfo.props = propsParam.properties.map(prop => 
          prop.key.name
        );
      } else if (propsParam.type === 'Identifier') {
        componentInfo.props = [propsParam.name];
      }
    }
  }

  async pathExists(filePath) {
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  }
}

class ReactD2DiagramGenerator {
  constructor() {
    this.colors = {
      page: '#4CAF50',
      component: '#2196F3',
      hook: '#FF9800',
      api: '#9C27B0',
      router: '#607D8B',
      state: '#795548'
    };
  }

  generateTechnicalDiagram(analyzer) {
    const timestamp = new Date().toISOString().slice(0, 19).replace('T', ' ');
    
    let d2Content = `# React Frontend Technical Architecture
# Generated on ${timestamp}

direction: down

# Application Structure
app: {
  label: "React Application\\n(Vite)"
  style.fill: "#61DAFB"
  
  router: {
    label: "Router\\n(React Router)"
    style.fill: "${this.colors.router}"
  }
  
  pages: {
    label: "Pages\\n(Route Components)"
    style.fill: "${this.colors.page}"
  }
  
  components: {
    label: "Components\\n(Reusable UI)"
    style.fill: "${this.colors.component}"
  }
  
  hooks: {
    label: "Custom Hooks\\n(Logic Layer)"
    style.fill: "${this.colors.hook}"
  }
}

# Backend Integration
api_layer: {
  label: "API Integration"
  style.fill: "#f5f5f5"
  
`;

    // Add API endpoints discovered
    const uniqueApis = new Set();
    analyzer.components.forEach(comp => {
      comp.apiCalls.forEach(api => uniqueApis.add(api.url));
    });
    analyzer.pages.forEach(page => {
      page.apiCalls.forEach(api => uniqueApis.add(api.url));
    });

    Array.from(uniqueApis).forEach((apiUrl, index) => {
      const cleanUrl = apiUrl.replace(/[^a-zA-Z0-9]/g, '_');
      d2Content += `  api_${index}: {
    label: "${apiUrl}"
    style.fill: "${this.colors.api}"
  }
  
`;
    });

    d2Content += `}

# Page Components Detail
pages_detail: {
  label: "Application Pages"
  style.fill: "#e8f5e8"
  
`;

    // Add pages
    analyzer.pages.forEach((page, name) => {
      const safeName = name.replace(/[^a-zA-Z0-9]/g, '_');
      d2Content += `  ${safeName}: {
    label: "${name}"
    style.fill: "${this.colors.page}"
  }
  
`;
    });

    d2Content += `}

# Component Hierarchy
components_detail: {
  label: "Component Library"
  style.fill: "#e3f2fd"
  
`;

    // Add components
    analyzer.components.forEach((component, name) => {
      const safeName = name.replace(/[^a-zA-Z0-9]/g, '_');
      d2Content += `  ${safeName}: {
    label: "${name}"
    style.fill: "${this.colors.component}"
  }
  
`;
    });

    d2Content += `}

# Custom Hooks
hooks_detail: {
  label: "Custom Hooks"
  style.fill: "#fff3e0"
  
`;

    // Add hooks
    analyzer.hooks.forEach((hook, name) => {
      const safeName = name.replace(/[^a-zA-Z0-9]/g, '_');
      d2Content += `  ${safeName}: {
    label: "${name}"
    style.fill: "${this.colors.hook}"
  }
  
`;
    });

    d2Content += `}

# Data Flow Connections
app.router -> app.pages: "routes to"
app.pages -> app.components: "renders"
app.components -> app.hooks: "uses"
app.hooks -> api_layer: "calls"

# Page to Component relationships
`;

    // Add page-component relationships
    analyzer.pages.forEach((page, pageName) => {
      const safePageName = pageName.replace(/[^a-zA-Z0-9]/g, '_');
      page.childComponents.forEach(componentName => {
        const safeComponentName = componentName.replace(/[^a-zA-Z0-9]/g, '_');
        if (analyzer.components.has(componentName)) {
          d2Content += `pages_detail.${safePageName} -> components_detail.${safeComponentName}: "renders"\\n`;
        }
      });
    });

    // Add component relationships
    analyzer.components.forEach((component, componentName) => {
      const safeComponentName = componentName.replace(/[^a-zA-Z0-9]/g, '_');
      component.childComponents.forEach(childName => {
        const safeChildName = childName.replace(/[^a-zA-Z0-9]/g, '_');
        if (analyzer.components.has(childName)) {
          d2Content += `components_detail.${safeComponentName} -> components_detail.${safeChildName}: "uses"\\n`;
        }
      });
    });

    return d2Content;
  }

  generateStakeholderDiagram(analyzer) {
    const timestamp = new Date().toISOString().slice(0, 19).replace('T', ' ');
    
    let d2Content = `# React Frontend User Journey
# Generated on ${timestamp}

direction: right

# User Interface Flow
user: {
  label: "User"
  style.fill: "#4CAF50"
}

browser: {
  label: "Web Browser"
  style.fill: "#FF9800"
}

app: {
  label: "React Application"
  style.fill: "#61DAFB"
}

backend: {
  label: "Backend API"
  style.fill: "#2196F3"
}

# User Journey Steps
journey: {
  label: "User Journey"
  style.fill: "#f5f5f5"
  
`;

    // Add main user flows based on pages
    const pageCategories = this.categorizePages(analyzer.pages);
    
    Object.entries(pageCategories).forEach(([category, pages]) => {
      const safeCategoryName = category.replace(/[^a-zA-Z0-9]/g, '_');
      d2Content += `  ${safeCategoryName}: {
    label: "${category}"
    style.fill: "#e8f5e8"
  }
  
`;
    });

    d2Content += `}

# Main Features
features: {
  label: "Application Features"
  style.fill: "#f5f5f5"
  
`;

    // Add features based on API calls and components
    const features = this.extractFeatures(analyzer);
    features.forEach(feature => {
      const safeFeatureName = feature.replace(/[^a-zA-Z0-9]/g, '_');
      d2Content += `  ${safeFeatureName}: {
    label: "${feature}"
    style.fill: "#e3f2fd"
  }
  
`;
    });

    d2Content += `}

# User Flow
user -> browser: "opens application"
browser -> app: "loads React app"
app -> backend: "fetches data"
backend -> app: "returns data"
app -> browser: "renders UI"
browser -> user: "displays interface"

# Feature Access
`;

    Object.keys(pageCategories).forEach(category => {
      const safeCategoryName = category.replace(/[^a-zA-Z0-9]/g, '_');
      d2Content += `app -> journey.${safeCategoryName}: "provides"\\n`;
    });

    features.forEach(feature => {
      const safeFeatureName = feature.replace(/[^a-zA-Z0-9]/g, '_');
      d2Content += `app -> features.${safeFeatureName}: "enables"\\n`;
    });

    return d2Content;
  }

  generateComponentFlowDiagram(analyzer, componentName) {
    const component = analyzer.components.get(componentName);
    if (!component) {
      throw new Error(`Component ${componentName} not found`);
    }

    const timestamp = new Date().toISOString().slice(0, 19).replace('T', ' ');
    const safeName = componentName.replace(/[^a-zA-Z0-9]/g, '_');
    
    let d2Content = `# Component Flow - ${componentName}
# Generated on ${timestamp}

direction: down

# Component Details
${safeName}: {
  label: "${componentName}\\nComponent"
  style.fill: "${this.colors.component}"
  
  props: {
    label: "Props"
    style.fill: "#e8f5e8"
  }
  
  state: {
    label: "Internal State"
    style.fill: "#fff3e0"
  }
  
  effects: {
    label: "Side Effects"
    style.fill: "#fce4ec"
  }
}

# Props Detail
`;

    if (component.props.length > 0) {
      d2Content += `props_detail: {
  label: "Component Props"
  style.fill: "#f5f5f5"
  
`;
      component.props.forEach(prop => {
        d2Content += `  ${prop}: {
    label: "${prop}"
    style.fill: "#e8f5e8"
  }
  
`;
      });
      d2Content += `}

`;
    }

    // Hooks used
    if (component.hooks.length > 0) {
      d2Content += `hooks_used: {
  label: "Hooks Used"
  style.fill: "#f5f5f5"
  
`;
      [...new Set(component.hooks)].forEach(hook => {
        const safeHookName = hook.replace(/[^a-zA-Z0-9]/g, '_');
        d2Content += `  ${safeHookName}: {
    label: "${hook}"
    style.fill: "${this.colors.hook}"
  }
  
`;
      });
      d2Content += `}

`;
    }

    // Child components
    if (component.childComponents.length > 0) {
      d2Content += `child_components: {
  label: "Child Components"
  style.fill: "#f5f5f5"
  
`;
      [...new Set(component.childComponents)].forEach(child => {
        const safeChildName = child.replace(/[^a-zA-Z0-9]/g, '_');
        d2Content += `  ${safeChildName}: {
    label: "${child}"
    style.fill: "${this.colors.component}"
  }
  
`;
      });
      d2Content += `}

`;
    }

    // API calls
    if (component.apiCalls.length > 0) {
      d2Content += `api_calls: {
  label: "API Integration"
  style.fill: "#f5f5f5"
  
`;
      component.apiCalls.forEach((api, index) => {
        d2Content += `  api_${index}: {
    label: "${api.method?.toUpperCase() || 'API'} ${api.url}"
    style.fill: "${this.colors.api}"
  }
  
`;
      });
      d2Content += `}

`;
    }

    // Connections
    d2Content += `# Component Flow
`;

    if (component.props.length > 0) {
      d2Content += `props_detail -> ${safeName}.props: "passes"\\n`;
    }

    if (component.hooks.length > 0) {
      component.hooks.forEach(hook => {
        const safeHookName = hook.replace(/[^a-zA-Z0-9]/g, '_');
        d2Content += `hooks_used.${safeHookName} -> ${safeName}.state: "manages"\\n`;
      });
    }

    if (component.childComponents.length > 0) {
      component.childComponents.forEach(child => {
        const safeChildName = child.replace(/[^a-zA-Z0-9]/g, '_');
        d2Content += `${safeName} -> child_components.${safeChildName}: "renders"\\n`;
      });
    }

    if (component.apiCalls.length > 0) {
      component.apiCalls.forEach((api, index) => {
        d2Content += `${safeName}.effects -> api_calls.api_${index}: "calls"\\n`;
      });
    }

    return d2Content;
  }

  categorizePages(pages) {
    const categories = {
      'Authentication': [],
      'Dashboard': [],
      'Management': [],
      'Settings': [],
      'Other': []
    };

    pages.forEach((page, name) => {
      const lowerName = name.toLowerCase();
      if (lowerName.includes('login') || lowerName.includes('auth') || 
          lowerName.includes('register') || lowerName.includes('signin')) {
        categories['Authentication'].push(name);
      } else if (lowerName.includes('dashboard') || lowerName.includes('home')) {
        categories['Dashboard'].push(name);
      } else if (lowerName.includes('manage') || lowerName.includes('admin') || 
                 lowerName.includes('crud') || lowerName.includes('list')) {
        categories['Management'].push(name);
      } else if (lowerName.includes('setting') || lowerName.includes('config') || 
                 lowerName.includes('profile')) {
        categories['Settings'].push(name);
      } else {
        categories['Other'].push(name);
      }
    });

    // Remove empty categories
    return Object.fromEntries(
      Object.entries(categories).filter(([key, value]) => value.length > 0)
    );
  }

  extractFeatures(analyzer) {
    const features = new Set();

    // Extract from API calls
    analyzer.components.forEach(component => {
      component.apiCalls.forEach(api => {
        if (api.url.includes('user')) features.add('User Management');
        if (api.url.includes('auth')) features.add('Authentication');
        if (api.url.includes('product')) features.add('Product Management');
        if (api.url.includes('order')) features.add('Order Processing');
        if (api.url.includes('payment')) features.add('Payment Processing');
        if (api.url.includes('report')) features.add('Reporting');
        if (api.url.includes('dashboard')) features.add('Dashboard Analytics');
      });
    });

    analyzer.pages.forEach(page => {
      page.apiCalls.forEach(api => {
        if (api.url.includes('user')) features.add('User Management');
        if (api.url.includes('auth')) features.add('Authentication');
        if (api.url.includes('product')) features.add('Product Management');
        if (api.url.includes('order')) features.add('Order Processing');
        if (api.url.includes('payment')) features.add('Payment Processing');
        if (api.url.includes('report')) features.add('Reporting');
        if (api.url.includes('dashboard')) features.add('Dashboard Analytics');
      });
    });

    // Default features if none found
    if (features.size === 0) {
      features.add('Data Display');
      features.add('User Interaction');
      features.add('Navigation');
    }

    return Array.from(features);
  }
}

// CLI Interface
async function main() {
  const args = process.argv.slice(2);
  const config = parseArgs(args);

  if (!config.frontendPath) {
    console.error('Frontend path is required. Use --frontend-path <path>');
    process.exit(1);
  }

  try {
    const analyzer = new ReactAnalyzer(config.frontendPath);
    const generator = new ReactD2DiagramGenerator();

    console.log('Analyzing React application...');
    await analyzer.analyzeFullApplication();

    const outputDir = config.outputDir || './diagrams';
    await fs.mkdir(outputDir, { recursive: true });

    if (config.component) {
      // Generate component-specific diagram
      const content = generator.generateComponentFlowDiagram(analyzer, config.component);
      const filename = `${config.component}_component_flow.d2`;
      await fs.writeFile(path.join(outputDir, filename), content);
      console.log(`Generated ${filename}`);
    } else {
      // Generate application diagrams
      if (config.type === 'technical' || config.type === 'all') {
        const content = generator.generateTechnicalDiagram(analyzer);
        const filename = 'react_technical_architecture.d2';
        await fs.writeFile(path.join(outputDir, filename), content);
        console.log(`Generated ${filename}`);
      }

      if (config.type === 'stakeholder' || config.type === 'all') {
        const content = generator.generateStakeholderDiagram(analyzer);
        const filename = 'react_stakeholder_flow.d2';
        await fs.writeFile(path.join(outputDir, filename), content);
        console.log(`Generated ${filename}`);
      }
    }

    console.log('\\nAnalysis Summary:');
    console.log(`- Pages: ${analyzer.pages.size}`);
    console.log(`- Components: ${analyzer.components.size}`);
    console.log(`- Custom Hooks: ${analyzer.hooks.size}`);
    console.log(`- API Endpoints: ${analyzer.apiCalls.size}`);
    console.log(`- Routes: ${analyzer.routes.length}`);

  } catch (error) {
    console.error('Error generating diagrams:', error.message);
    process.exit(1);
  }
}

function parseArgs(args) {
  const config = {};
  
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--frontend-path':
        config.frontendPath = args[++i];
        break;
      case '--component':
        config.component = args[++i];
        break;
      case '--output-dir':
        config.outputDir = args[++i];
        break;
      case '--type':
        config.type = args[++i];
        break;
      case '--help':
        showHelp();
        process.exit(0);
        break;
    }
  }
  
  config.type = config.type || 'technical';
  
  return config;
}

function showHelp() {
  console.log(`
React D2 Diagram Generator

Usage: node react-d2-generator.js [options]

Options:
  --frontend-path <path>    Path to React frontend directory (required)
  --component <name>        Generate diagram for specific component
  --output-dir <path>       Output directory for diagrams (default: ./diagrams)
  --type <type>             Diagram type: technical, stakeholder, all (default: technical)
  --help                    Show this help message

Examples:
  # Generate technical diagram for entire app
  node react-d2-generator.js --frontend-path ./frontend

  # Generate stakeholder diagram
  node react-d2-generator.js --frontend-path ./frontend --type stakeholder

  # Generate component-specific diagram
  node react-d2-generator.js --frontend-path ./frontend --component UserProfile

  # Generate all diagram types
  node react-d2-generator.js --frontend-path ./frontend --type all
  `);
}

if (require.main === module) {
  main().catch(console.error);
}

module.exports = { ReactAnalyzer, ReactD2DiagramGenerator };
    }
  }

  async analyzePage(filePath) {
    const componentInfo = await this.analyzeComponent(filePath);
    if (componentInfo) {
      // Additional page-specific analysis
      const content = await fs.readFile(filePath, 'utf-8');
      
      // Look for route definitions or navigation patterns
      const routePatterns = [
        /useNavigate/g,
        /useLocation/g,
        /useParams/g,
        /<Route/g,
        /navigate\(/g
      ];

      componentInfo.hasNavigation = routePatterns.some(pattern => 
        pattern.test(content)
      );
    }
    
    return componentInfo;
  }

  async analyzeHook(filePath) {
    const content = await fs.readFile(filePath, 'utf-8');
    const hookName = path.basename(filePath, path.extname(filePath));
    
    const hookInfo = {
      name: hookName,
      dependencies: [],
      returns: [],
      sideEffects: []
    };

    try {
      const ast = parse(content, {
        sourceType: 'module',
        plugins: ['jsx', 'typescript']
      });

      traverse(ast, {
        CallExpression(path) {
          const callee = path.node.callee;
          
          if (callee.name && callee.name.startsWith('use')) {
            hookInfo.dependencies.push(callee.name);
          }
          
          // Check for side effects
          if (this.isSideEffect(path.node)) {
            hookInfo.sideEffects.push(this.extractSideEffect(path.node));
          }
        },

        ReturnStatement(path) {
          if (path.node.argument) {
            hookInfo.returns.push(this.extractReturnType(path.node.argument));
          }
        }
      });
    } catch (error) {
      console.error(`Error analyzing hook ${filePath}:`, error.message);
    }

    return hookInfo;
  }

  async analyzeDirectory(dirPath, type = 'components') {
    const items = new Map();
    
    try {
      const files = await fs.readdir(dirPath, { withFileTypes: true });
      
      for (const file of files) {
        const filePath = path.join(dirPath, file.name);
        
        if (file.isFile() && this.isReactFile(file.name)) {
          let analysis;
          
          switch (type) {
            case 'components':
              analysis = await this.analyzeComponent(filePath);
              break;
            case 'pages':
              analysis = await this.analyzePage(filePath);
              break;
            case 'hooks':
              analysis = await this.analyzeHook(filePath);
              break;
          }
          
          if (analysis) {
            items.set(analysis.name, analysis);
          }
        } else if (file.isDirectory() && !file.name.startsWith('.')) {
          // Recursively analyze subdirectories
          const subItems = await this.analyzeDirectory(filePath, type);
          subItems.forEach((value, key) => {
            items.set(`${file.name}/${key}`, value);
          });
        }
      }
    } catch (error) {
      console.error(`Error analyzing directory ${dirPath}:`, error.message);
    }
    
    return items;
  }

  async analyzeFullApplication() {
    const componentsPath = path.join(this.basePath, 'src', 'components');
    const pagesPath = path.join(this.basePath, 'src', 'pages');
    const hooksPath = path.join(this.basePath, 'src', 'hooks');
    
    if (await this.pathExists(componentsPath)) {
      this.components = await this.analyzeDirectory(componentsPath, 'components');
    }
    
    if (await this.pathExists(pagesPath)) {
      this.pages = await this.analyzeDirectory(pagesPath, 'pages');
    }
    
    if (await this.pathExists(hooksPath)) {
      this.hooks = await this.analyzeDirectory(hooksPath, 'hooks');
    }

    // Analyze routing
    await this.analyzeRouting();
  }

  async analyzeRouting() {
    const routeFiles = [
      'src/App.jsx',
      'src/App.tsx',
      'src/router/index.js',
      'src/routes.js',
      'src/routes.jsx'
    ];

    for (const routeFile of routeFiles) {
      const filePath = path.join(this.basePath, routeFile);
      if (await this.pathExists(filePath)) {
        await this.extractRoutes(filePath);
        break;
      }
    }
  }

  async extractRoutes(filePath) {
    try {
      const content = await fs.readFile(filePath, 'utf-8');
      const routes = [];
      
      // Simple regex-based route extraction
      const routePattern = /<Route[^>]*path=["']([^"']*)["'][^>]*element={[^}]*<([^/>]*).*?}/g;
      let match;
      
      while ((match = routePattern.exec(content)) !== null) {
        routes.push({
          path: match[1],
          component: match[2]
        });
      }
      
      this.routes = routes;
    } catch (error) {
      console.error(`Error extracting routes from ${filePath}:`, error.message);
    }
  }

  // Helper methods
  isReactComponent(name) {
    return name && name[0] === name[0].toUpperCase();
  }

  isReactFile(filename) {
    return /\.(jsx?|tsx?)$/.test(filename) && !filename.includes('.test.');
  }

  isCustomComponent(name) {
    return name && name[0] === name[0].toUpperCase() && 
           !['div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(name.toLowerCase());
  }

  isApiCall(node) {
    const callee = node.callee;
    
    // Check for common API call patterns
    if (callee.property) {
      const methods = ['get', 'post', 'put', 'delete', 'patch'];
      return methods.includes(callee.property.name);
    }
    
    if (callee.name) {
      return ['fetch', 'axios', 'request'].includes(callee.name);
    }
    
    return false;
  }

  extractApiCall(node) {
    const callee = node.callee;
    
    if (node.arguments.length > 0) {
      const firstArg = node.arguments[0];
      if (firstArg.type === 'StringLiteral') {
        return {
          method: callee.property?.name || callee.name,
          url: firstArg.value
        };
      }
    }
    
    return null;